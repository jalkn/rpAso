import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os

st.set_page_config(page_title="RPA Asocebu Pro", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría de Inventario (Limpieza de Cabeceras)")

with st.sidebar:
    st.header("Configuración")
    user_select = st.selectbox("Usuario:", ["1307", "2306"])
    limit_rows = st.number_input("Cantidad de registros a auditar:", min_value=1, value=50)
    st.info("Nota: Para 163k registros, usa un límite bajo para probar primero.")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    all_dfs = []
    
    for sheet in xl.sheet_names:
        # 1. Leemos la hoja completa
        df_raw = pd.read_excel(file, sheet_name=sheet)
        
        # 2. BUSQUEDA DE LA TABLA REAL:
        # Buscamos en qué fila está la palabra "ANIMAL" o "REGISTRO"
        header_row = 0
        found = False
        for i in range(min(len(df_raw), 20)): # Revisamos las primeras 20 filas
            row_values = [str(val).upper() for val in df_raw.iloc[i].values]
            if any("ANIMAL" in v or "REGISTRO" in v for v in row_values):
                header_row = i + 1
                found = True
                break
        
        # 3. Re-leemos la hoja desde la fila correcta
        if found:
            df_clean = pd.read_excel(file, sheet_name=sheet, skiprows=header_row)
        else:
            df_clean = df_raw # Si no encontramos nada, usamos lo que hay
            
        # 4. Normalizar nombres de columnas
        df_clean.columns = [str(c).strip().upper().replace('°', '').replace(' ', '_') for c in df_clean.columns]
        df_clean = df_clean.dropna(how='all', axis=0) # Quitar filas vacías
        df_clean['ORIGEN_POTRERO'] = sheet
        all_dfs.append(df_clean)
        
    return pd.concat(all_dfs, ignore_index=True)

async def run_web_automation(df, user_code, max_rows):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Identificar columna ID de forma flexible
    col_id = next((c for c in df.columns if any(p in c for p in ['ANIMAL', 'REGISTRO', 'IDENTI'])), None)
    
    if not col_id:
        st.error(f"❌ Columnas detectadas: {list(df.columns)}. No encontré ninguna que diga 'ANIMAL'.")
        return pd.DataFrame()

    st.success(f"🔍 Columna identificada: **{col_id}**")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://sir.asocebu.com.co/Genealogias/", timeout=60000)

        df_to_process = df.head(max_rows)
        for index, row in df_to_process.iterrows():
            animal_id = str(row[col_id]).strip().replace('.0', '')
            
            if not animal_id or animal_id.lower() in ['nan', 'none', 'total', '0']:
                continue

            status_text.text(f"Auditando: {animal_id}...")
            
            res_row = row.to_dict()
            try:
                await page.fill('input[name="txtBusqueda"]', animal_id)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1800)
                
                nombre_web = await page.inner_text('#lblNombreAnimal')
                res_row.update({"RESULTADO_RPA": "OK", "NOMBRE_WEB": nombre_web})
            except:
                res_row.update({"RESULTADO_RPA": "NO ENCONTRADO", "NOMBRE_WEB": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_to_process))
            
        await browser.close()
        return pd.DataFrame(results)

uploaded_file = st.file_uploader("Suba el archivo Excel", type=["xlsx"])

if uploaded_file:
    df_consolidado = procesar_archivo_cliente(uploaded_file)
    st.write("### Vista previa de los datos detectados:")
    st.dataframe(df_consolidado.head(5))

    if st.button("🚀 Iniciar Proceso"):
        df_final = asyncio.run(run_web_automation(df_consolidado, user_select, limit_rows))
        
        if not df_final.empty:
            st.success("Auditoría parcial completada.")
            st.dataframe(df_final)
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar Resultados", csv, "reporte.csv", "text/csv")