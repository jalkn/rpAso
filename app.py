import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os

st.set_page_config(page_title="RPA Asocebu Cloud", page_icon="🐄")
st.title("🐄 Auditoría de Inventario Ganadería")

# 1. Selección de Cuenta en Sidebar
with st.sidebar:
    st.header("Configuración")
    user_select = st.selectbox("Seleccione Usuario Asocebu:", ["1307", "2306"])
    st.info(f"Modo: Cuenta {user_select}")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

# 2. Lógica para unir todos los potreros (pestañas)
def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    dfs = []
    for sheet in xl.sheet_names:
        df_sheet = pd.read_excel(file, sheet_name=sheet)
        df_sheet.columns = [str(c).strip() for c in df_sheet.columns]
        df_sheet['Potrero_Original'] = sheet 
        dfs.append(df_sheet)
    return pd.concat(dfs, ignore_index=True)

async def run_web_automation(df, user_code):
    results = []
    progress_bar = st.progress(0)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # URL de consulta pública para Auditoría
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

# 3. Interfaz de Usuario
uploaded_file = st.file_uploader("Suba el archivo con las pestañas de Potreros", type=["xlsx"])

if uploaded_file:
    # Protección contra el error 0.0B
    if uploaded_file.size == 0:
        st.error("⚠️ El archivo subido no contiene datos (0.0B).")
    else:
        uploaded_file.seek(0)
        df_consolidado = procesar_archivo_cliente(uploaded_file)
        st.success(f"✅ Se han cargado {len(df_consolidado)} registros de todos los potreros.")

        if st.button("🚀 Iniciar Automatización"):
            with st.spinner(f"El Bot está trabajando con la cuenta {user_select}..."):
                df_final = asyncio.run(run_web_automation(df_consolidado, user_select))
                st.dataframe(df_final)
                
                # Botón de descarga del reporte final
                output = "reporte_auditoria_consolidado.xlsx"
                df_final.to_excel(output, index=False)
                with open(output, "rb") as f:
                    st.download_button("📥 Descargar Reporte Excel", f, output)