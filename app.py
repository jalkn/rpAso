import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os
import io

st.set_page_config(page_title="RPA Asocebu Pro", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría Integral: Número, Grupo, Sexo y Color")

with st.sidebar:
    st.header("Configuración de Auditoría")
    user_select = st.selectbox("Seleccione Usuario:", ["1307", "2306"])
    limit_rows = st.number_input("Cantidad de registros a validar:", min_value=1, value=100, step=50)
    st.info("El bot comparará los datos del Excel contra la ficha técnica oficial de Asocebu.")
    st.warning("Nota: Procesar volúmenes masivos (163k) requiere ejecución por lotes.")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    all_dfs = []
    for sheet in xl.sheet_names:
        df_raw = pd.read_excel(file, sheet_name=sheet, header=None)
        header_row = 0
        found = False
        for i, row in df_raw.iterrows():
            if i > 50: break 
            row_str = " ".join([str(val).upper() for val in row.values if pd.notna(val)])
            # Buscamos la fila donde inicia la tabla real basándonos en palabras clave
            if any(k in row_str for k in ["ANIMAL", "REGISTRO", "IDENTIFICACION", "N°"]):
                header_row = i
                found = True
                break
        
        df_clean = pd.read_excel(file, sheet_name=sheet, skiprows=header_row) if found else df_raw
        # Normalizamos nombres de columnas (quitar espacios, puntos, grados)
        df_clean.columns = [str(c).strip().upper().replace('°', '').replace(' ', '_').replace('.', '') for c in df_clean.columns]
        df_clean = df_clean.loc[:, ~df_clean.columns.str.contains('UNNAMED')]
        df_clean = df_clean.dropna(how='all', axis=0)
        
        if not df_clean.empty:
            df_clean['HOJA_ORIGEN'] = sheet
            all_dfs.append(df_clean)
            
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

async def run_web_automation(df, max_rows):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Mapeo dinámico de columnas del Excel de Argos
    col_id = next((c for c in df.columns if any(p in c for p in ['ANIMAL', 'REGISTRO', 'ID', 'NUMERO'])), None)
    col_raza = next((c for c in df.columns if any(p in c for p in ['RAZA', 'GRUPO'])), 'RAZA')
    col_sexo = next((c for c in df.columns if 'SEXO' in c), 'SEXO')
    col_color = next((c for c in df.columns if any(p in c for p in ['COLOR', 'PELAJE'])), 'COLOR')

    if not col_id:
        st.error(f"❌ No se encontró columna de identificación. Columnas detectadas: {list(df.columns)}")
        return pd.DataFrame()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # URL de inicio para Genealogías
        await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", timeout=60000)

        df_proc = df.head(max_rows).copy()
        for index, row in df_proc.iterrows():
            # Limpiamos el ID (ej. 1307.0 -> 1307)
            animal_id = str(row[col_id]).strip().split('.')[0]
            if not animal_id or animal_id.lower() in ['nan', 'none', '0', '']: continue

            status_text.text(f"🔍 Validando {index+1}/{len(df_proc)}: ID {animal_id}")
            res_row = row.to_dict()

            try:
                # 1. Selección de categoría y búsqueda (Requerimiento TI)
                await page.select_option('select[id*="ddlTipoBusqueda"]', value="1") # 1 = Registro
                await page.fill('input[id*="txtBusqueda"]', animal_id)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2500) # Espera carga dinámica
                
                # 2. Extracción de datos fenotípicos desde la web
                nombre_web = await page.inner_text('#lblNombreAnimal')
                raza_web = (await page.inner_text('#lblRaza')).upper()
                sexo_web = (await page.inner_text('#lblSexo')).upper()
                color_web = (await page.inner_text('#lblColor')).upper()

                # 3. Lógica de Comparación Cuádruple contra el Excel
                raza_ex = str(row.get(col_raza, '')).upper()
                sexo_ex = str(row.get(col_sexo, '')).upper()
                color_ex = str(row.get(col_color, '')).upper()

                # Validaciones (coincidencia parcial para mayor flexibilidad)
                m_raza = raza_web in raza_ex or raza_ex in raza_web
                m_sexo = sexo_web[0] == sexo_ex[0] if sexo_web and sexo_ex else False
                m_color = color_web in color_ex or color_ex in color_web

                if m_raza and m_sexo and m_color:
                    res_row.update({"RESULTADO_RPA": "✅ COINCIDENCIA TOTAL", 
                                   "DETALLE": f"Web: {raza_web}, {sexo_web}, {color_web}"})
                else:
                    dif = []
                    if not m_raza: dif.append("Grupo/Raza")
                    if not m_sexo: dif.append("Sexo")
                    if not m_color: dif.append("Color")
                    res_row.update({"RESULTADO_RPA": "⚠️ DISCREPANCIA", 
                                   "DETALLE": f"Difiere en: {', '.join(dif)} | Web: {raza_web}/{sexo_web}/{color_web}"})
                
                res_row.update({"NOMBRE_OFICIAL": nombre_web})
            except:
                res_row.update({"RESULTADO_RPA": "❌ NO ENCONTRADO", "DETALLE": "No hallado en SIR Asocebu", "NOMBRE_OFICIAL": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# --- INTERFAZ USUARIO ---
file = st.file_uploader("Suba el archivo de Inventario (Excel)", type=["xlsx"])
if file:
    df_consolidado = procesar_archivo_cliente(file)
    if not df_consolidado.empty:
        st.write("### Datos detectados en el archivo:")
        st.dataframe(df_consolidado.head(5))

        if st.button("🚀 Iniciar Auditoría Fenotípica"):
            df_final = asyncio.run(run_web_automation(df_consolidado, limit_rows))
            st.success("✅ Auditoría completada.")
            st.dataframe(df_final)
            
            # Exportación de reporte final
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte Final", buffer.getvalue(), file_name=f"Resultado_Auditoria_{user_select}.xlsx")