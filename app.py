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

# 4. MOTOR DE AUTOMATIZACIÓN CON LÓGICA DE PRECISIÓN
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
        await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", timeout=60000)

        df_proc = df.head(max_rows).copy()
        for index, row in df_proc.iterrows():
            animal_id = str(row[col_id]).strip().upper()
            if not animal_id or animal_id in ['NAN', 'NONE', '']: continue

            status_text.text(f"🔍 Validando {index+1}/{len(df_proc)}: {animal_id}")
            res_row = row.to_dict()

            try:
                # Búsqueda por Registro
                await page.select_option('select[id*="ddlTipoBusqueda"]', value="1")
                await page.fill('input[id*="txtBusqueda"]', animal_id)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(3000) # Tiempo de carga de tabla
                
                # --- AJUSTE DE PRECISIÓN PARA RESULTADOS MÚLTIPLES ---
                filas = await page.query_selector_all("tr")
                target_found = False
                for fila in filas:
                    texto = await fila.inner_text()
                    if animal_id in texto.upper():
                        lupa = await fila.query_selector('input[type="image"], a.btn-ver, .lupa')
                        if lupa:
                            await lupa.click()
                            target_found = True
                            break
                
                if not target_found: raise Exception("ID no coincide")
                await page.wait_for_timeout(2000)
                
                # Extracción de datos fenotípicos
                raza_w = (await page.inner_text('#lblRaza')).upper()
                sexo_w = (await page.inner_text('#lblSexo')).upper()
                color_w = (await page.inner_text('#lblColor')).upper()
                nombre_w = await page.inner_text('#lblNombreAnimal')

                # Validación
                m_raza = raza_w in str(row.get(col_grupo, '')).upper() or str(row.get(col_grupo, '')).upper() in raza_w
                m_sexo = True if not col_sexo else (sexo_w[0] == str(row[col_sexo])[0].upper())
                m_color = True if not col_color else (color_w in str(row[col_color]).upper())

                if m_raza and m_sexo and m_color:
                    res_row.update({"RESULTADO_RPA": "✅ COINCIDE", "INFO_WEB": f"{raza_w} | {sexo_w} | {color_w}"})
                else:
                    res_row.update({"RESULTADO_RPA": "⚠️ DISCREPANCIA", "INFO_WEB": f"{raza_w}/{sexo_w}/{color_w}"})
                res_row.update({"NOMBRE_OFICIAL": nombre_w})
                
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio") # Regresar para sig. consulta
            except:
                res_row.update({"RESULTADO_RPA": "❌ ERROR/NO HALLADO", "INFO_WEB": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# 5. UI FINAL
file = st.file_uploader("Suba el archivo de Inventario", type=["xlsx"])
if file:
    df_c = procesar_archivo_cliente(file)
    if not df_c.empty:
        st.dataframe(df_c.head(5))
        if st.button("🚀 Iniciar Auditoría"):
            df_f = asyncio.run(run_web_automation(df_c, limit_rows))
            st.success("✅ Completado")
            st.dataframe(df_f)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer) as w: df_f.to_excel(w, index=False)
            st.download_button("📥 Descargar Reporte", buffer.getvalue(), "Auditoria.xlsx")