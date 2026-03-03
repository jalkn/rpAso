import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os
import io

st.set_page_config(page_title="RPA Asocebu Pro", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría de Inventario Ganadería")

with st.sidebar:
    st.header("Configuración")
    user_select = st.selectbox("Usuario:", ["1307", "2306"])
    limit_rows = st.number_input("Cantidad de registros a auditar:", min_value=1, value=50)
    st.info("Nota: Se recomienda probar con 50 registros para verificar el formato.")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    all_dfs = []
    
    for sheet in xl.sheet_names:
        # Leemos la hoja completa para buscar la tabla real
        df_raw = pd.read_excel(file, sheet_name=sheet)
        
        # BUSQUEDA DINÁMICA DE CABECERA
        # Buscamos en las primeras 30 filas dónde empieza la tabla real
        header_row = 0
        found = False
        for i in range(min(len(df_raw), 30)):
            row_values = [str(val).upper() for val in df_raw.iloc[i].values]
            if any("ANIMAL" in v or "REGISTRO" in v or "ID" == v for v in row_values):
                header_row = i + 1
                found = True
                break
        
        # Re-leemos desde la fila detectada
        df_clean = pd.read_excel(file, sheet_name=sheet, skiprows=header_row) if found else df_raw
            
        # Limpieza de nombres de columnas
        df_clean.columns = [str(c).strip().upper().replace('°', '').replace(' ', '_') for c in df_clean.columns]
        df_clean = df_clean.dropna(how='all', axis=0)
        df_clean['HOJA_ORIGEN'] = sheet
        all_dfs.append(df_clean)
        
    return pd.concat(all_dfs, ignore_index=True)

async def run_web_automation(df, user_code, max_rows):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Identificar la columna que contiene los IDs de los animales
    col_id = next((c for c in df.columns if any(p in c for p in ['ANIMAL', 'REGISTRO', 'IDENTI'])), None)
    
    if not col_id:
        st.error(f"❌ No se encontró la columna de identificación. Columnas detectadas: {list(df.columns)}")
        return pd.DataFrame()

    st.success(f"🔍 Auditando mediante columna: **{col_id}**")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://sir.asocebu.com.co/Genealogias/", timeout=60000)

        # Procesamos solo la muestra solicitada
        df_to_process = df.head(max_rows).copy()
        
        for index, row in df_to_process.iterrows():
            animal_id = str(row[col_id]).strip().replace('.0', '')
            
            if not animal_id or animal_id.lower() in ['nan', 'none', 'total', '0']:
                continue

            status_text.text(f"🚀 Procesando {index+1} de {len(df_to_process)}: {animal_id}...")
            
            res_row = row.to_dict()
            try:
                await page.fill('input[name="txtBusqueda"]', animal_id)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1500)
                
                nombre_web = await page.inner_text('#lblNombreAnimal')
                res_row.update({"RESULTADO_RPA": "OK", "NOMBRE_ASOCEBU": nombre_web})
            except:
                res_row.update({"RESULTADO_RPA": "NO ENCONTRADO", "NOMBRE_ASOCEBU": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_to_process))
            
        await browser.close()
        return pd.DataFrame(results)

# --- INTERFAZ DE USUARIO ---
uploaded_file = st.file_uploader("Suba el archivo de Inventario (Excel)", type=["xlsx"])

if uploaded_file:
    with st.spinner("Leyendo y limpiando archivo..."):
        df_consolidado = procesar_archivo_cliente(uploaded_file)
    
    st.write("### Vista previa de datos detectados:")
    st.dataframe(df_consolidado.head(10))

    if st.button("🚀 Iniciar Auditoría"):
        df_final = asyncio.run(run_web_automation(df_consolidado, user_select, limit_rows))
        
        if not df_final.empty:
            st.success("✅ Proceso finalizado.")
            st.dataframe(df_final)
            
            # GENERACIÓN DE EXCEL EN MEMORIA
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Auditoria_Asocebu')
            
            st.download_button(
                label="📥 Descargar Reporte Final en Excel",
                data=buffer.getvalue(),
                file_name=f"REPORTE_AUDITORIA_{user_select}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )