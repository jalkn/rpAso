import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os

st.set_page_config(page_title="RPA Asocebu Pro", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría de Inventario de Alta Capacidad")

with st.sidebar:
    st.header("Configuración")
    user_select = st.selectbox("Usuario:", ["1307", "2306"])
    limit_rows = st.number_input("Límite de registros a auditar:", min_value=1, value=100, step=100)
    st.warning("Nota: Procesar 163k registros tomaría aprox. 40 horas. Se recomienda usar muestras.")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    dfs = []
    for sheet in xl.sheet_names:
        df_sheet = pd.read_excel(file, sheet_name=sheet)
        # Limpieza profunda de nombres de columnas
        df_sheet.columns = [str(c).strip().upper().replace(' ', '_').replace('°', '') for c in df_sheet.columns]
        df_sheet = df_sheet.dropna(how='all')
        df_sheet['POTRERO_ORIGEN'] = sheet 
        dfs.append(df_sheet)
    return pd.concat(dfs, ignore_index=True)

async def run_web_automation(df, user_code, max_rows):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Buscar columna de identificación
    col_id = next((c for c in df.columns if any(p in c for p in ['ANIMAL', 'REGISTRO', 'IDENTI', 'ID'])), None)
    
    if not col_id:
        st.error(f"❌ No encontré columna de identificación. Columnas: {list(df.columns)}")
        return pd.DataFrame()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://sir.asocebu.com.co/Genealogias/", timeout=60000)

        # Solo procesar hasta el límite configurado
        df_to_process = df.head(max_rows)
        total = len(df_to_process)

        for index, row in df_to_process.iterrows():
            animal_id = str(row[col_id]).strip().replace('.0', '')
            
            if not animal_id or animal_id.lower() in ['nan', 'none', 'total']:
                continue

            status_text.text(f"🔍 Auditando: {animal_id} ({index+1}/{total})")
            
            res_row = row.to_dict()
            try:
                await page.fill('input[name="txtBusqueda"]', animal_id)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1200) # Velocidad optimizada
                
                nombre_web = await page.inner_text('#lblNombreAnimal')
                res_row.update({"ESTADO_RPA": "OK", "NOMBRE_ASOCEBU": nombre_web})
            except:
                res_row.update({"ESTADO_RPA": "NO ENCONTRADO", "NOMBRE_ASOCEBU": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / total)
            
        await browser.close()
        return pd.DataFrame(results)

uploaded_file = st.file_uploader("Suba el archivo Excel", type=["xlsx"])

if uploaded_file:
    df_consolidado = procesar_archivo_cliente(uploaded_file)
    st.info(f"📋 Archivo cargado con {len(df_consolidado)} filas totales.")

    if st.button("🚀 Iniciar Auditoría"):
        df_final = asyncio.run(run_web_automation(df_consolidado, user_select, limit_rows))
        
        if not df_final.empty:
            st.success(f"¡Auditoría de {len(df_final)} registros completada!")
            st.dataframe(df_final)
            
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar Reporte (CSV)", csv, "reporte_auditoria.csv", "text/csv")
        else:
            st.error("No se generaron resultados. Verifique el formato de la columna 'N ANIMAL'.")