import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os

st.set_page_config(page_title="RPA Asocebu Cloud", page_icon="🐄")
st.title("🐄 Auditoría de Inventario Multi-Cuenta")

# 1. Configuración de Cuentas (Basado en el correo del cliente)
CUENTAS = {
    "1307": {"nombre": "General"},
    "2306": {"nombre": "Raza Particular"}
}

with st.sidebar:
    st.header("Configuración")
    user_select = st.selectbox("Seleccione Usuario Asocebu:", list(CUENTAS.keys()))
    st.info(f"Modo: {CUENTAS[user_select]['nombre']}")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

# 2. Procesamiento de Excel con Múltiples Pestañas (Potreros)
def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    dfs = []
    for sheet in xl.sheet_names:
        df = pd.read_excel(file, sheet_name=sheet)
        df.columns = [str(c).strip() for c in df.columns]
        df['Potrero_Original'] = sheet 
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

async def run_web_automation(df, user_code):
    results = []
    progress_bar = st.progress(0)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://sir.asocebu.com.co/Genealogias/", timeout=60000)

        total = len(df)
        for index, row in df.iterrows():
            animal_id = str(row.get('N° ANIMAL', row.get('Registration_Number', ''))).strip()
            if not animal_id or "total" in animal_id.lower() or animal_id == 'nan':
                continue

            try:
                await page.fill('input[name="txtBusqueda"]', animal_id)
                await page.press('input[name="txtBusqueda"]', "Enter")
                await page.wait_for_timeout(2000)
                nombre_web = await page.inner_text('#lblNombreAnimal')
                results.append({**row, "Usuario_RPA": user_code, "Estado": "OK", "Nombre_Asocebu": nombre_web})
            except:
                results.append({**row, "Usuario_RPA": user_code, "Estado": "No Encontrado", "Nombre_Asocebu": "N/A"})
            
            progress_bar.progress((index + 1) / total)
        await browser.close()
        return pd.DataFrame(results)

# 3. Interfaz de Usuario con protección de archivo 0.0B
uploaded_file = st.file_uploader("Suba el archivo de Potreros", type=["xlsx"])

if uploaded_file:
    if uploaded_file.size == 0:
        st.error("⚠️ El archivo está vacío. Verifique su archivo local.")
    else:
        uploaded_file.seek(0)
        df_consolidado = procesar_archivo_cliente(uploaded_file)
        st.success(f"✅ {len(df_consolidado)} registros detectados en todas las pestañas.")

        if st.button("🚀 Iniciar Auditoría"):
            with st.spinner(f"Procesando con cuenta {user_select}..."):
                df_final = asyncio.run(run_web_automation(df_consolidado, user_select))
                st.dataframe(df_final)
                
                output = "reporte_consolidado.xlsx"
                df_final.to_excel(output, index=False)
                with open(output, "rb") as f:
                    st.download_button("📥 Descargar Reporte Final", f, output)