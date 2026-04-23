import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os
import io

# 1. CONFIGURACIÓN DE PÁGINA Y UI
st.set_page_config(page_title="RPA Asocebu Pro", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría Integral: Registro, Grupo, Sexo y Color")

with st.sidebar:
    st.header("Configuración de Auditoría")
    user_select = st.selectbox("Seleccione Usuario:", ["1307", "2306"])
    limit_rows = st.number_input("Cantidad de registros a validar:", min_value=1, value=100, step=50)
    st.info("El bot comparará 'REGISTRO' y 'GRUPO' contra la ficha técnica oficial de Asocebu.")
    st.warning("Nota: Procesar volúmenes masivos (163k) requiere ejecución por lotes.")

# 2. INSTALACIÓN DE DEPENDENCIAS
@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

# 3. PROCESAMIENTO DE ARCHIVOS EXCEL
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
            if "N° ANIMAL" in row_str and "REGISTRO" in row_str:
                header_row = i
                found = True
                break
        
        if found:
            df_clean = pd.read_excel(file, sheet_name=sheet, skiprows=header_row)
            df_clean.columns = [str(c).strip().upper().replace('°', '').replace(' ', '_').replace('.', '') for c in df_clean.columns]
            df_clean = df_clean.loc[:, ~df_clean.columns.str.contains('UNNAMED')]
            df_clean = df_clean.dropna(subset=['REGISTRO'], how='any')
            if not df_clean.empty:
                df_clean['HOJA_ORIGEN'] = sheet
                all_dfs.append(df_clean)
            
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

# 4. MOTOR DE AUTOMATIZACIÓN (LOGICA DE CLIC EN LUPA INTEGRADA)
async def run_web_automation(df, max_rows):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    col_id = "REGISTRO" 
    col_grupo = "GRUPO" 
    col_sexo = next((c for c in df.columns if 'SEXO' in c), None)
    col_color = next((c for c in df.columns if any(p in c for p in ['COLOR', 'PELAJE'])), None)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        df_proc = df.head(max_rows).copy()
        for index, row in df_proc.iterrows():
            animal_id = str(row[col_id]).strip().upper()
            if not animal_id or animal_id in ['NAN', 'NONE', '']: continue

            status_text.text(f"🔍 Validando {index+1}/{len(df_proc)}: {animal_id}")
            res_row = row.to_dict()

            try:
                # Navegar al inicio en cada consulta para limpiar estados
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", timeout=60000)
                
                # Búsqueda por Registro
                await page.select_option('select[id*="ddlTipoBusqueda"]', value="1")
                await page.fill('input[id*="txtBusqueda"]', animal_id)
                await page.keyboard.press("Enter")
                
                # ESPERA Y CLIC EN LA LUPA: Crucial para entrar a la ficha técnica
                lupa_selector = 'input[type="image"], a.btn-ver, .lupa, img[src*="lupa"]'
                await page.wait_for_selector(lupa_selector, timeout=10000)
                await page.click(lupa_selector)
                
                # Esperar a que cargue la ficha técnica
                await page.wait_for_selector('#lblRaza', timeout=10000)
                
                # Extracción de datos fenotípicos
                raza_w = (await page.inner_text('#lblRaza')).upper()
                sexo_w = (await page.inner_text('#lblSexo')).upper()
                color_w = (await page.inner_text('#lblColor')).upper()
                nombre_w = await page.inner_text('#lblNombreAnimal')

                # Validación contra el Excel
                m_raza = raza_w in str(row.get(col_grupo, '')).upper() or str(row.get(col_grupo, '')).upper() in raza_w
                m_sexo = True if not col_sexo else (sexo_w[0] == str(row[col_sexo])[0].upper())
                m_color = True if not col_color else (color_w in str(row[col_color]).upper())

                if m_raza and m_sexo and m_color:
                    res_row.update({"RESULTADO_RPA": "✅ COINCIDE", "INFO_WEB": f"{raza_w} | {sexo_w} | {color_w}"})
                else:
                    res_row.update({"RESULTADO_RPA": "⚠️ DISCREPANCIA", "INFO_WEB": f"{raza_w}/{sexo_w}/{color_w}"})
                res_row.update({"NOMBRE_OFICIAL": nombre_w})
                
            except:
                res_row.update({"RESULTADO_RPA": "❌ NO ENCONTRADO", "INFO_WEB": "N/A", "NOMBRE_OFICIAL": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# 5. UI FINAL
file = st.file_uploader("Suba el archivo de Inventario (Excel)", type=["xlsx"])
if file:
    df_c = procesar_archivo_cliente(file)
    if not df_c.empty:
        st.write(f"### Datos detectados ({len(df_c)} registros):")
        st.dataframe(df_c.head(5))
        if st.button("🚀 Iniciar Auditoría de Inventario"):
            df_f = asyncio.run(run_web_automation(df_c, limit_rows))
            st.success("✅ Auditoría Completada")
            st.dataframe(df_f)
            
            # Preparación de descarga
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_f.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte de Resultados", buffer.getvalue(), "Auditoria_Inventario_Final.xlsx")