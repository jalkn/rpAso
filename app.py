import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os

st.set_page_config(page_title="RPA Asocebu Cloud", page_icon="🐄")
st.title("🐄 Auditoría de Inventario Ganadería")

# 1. Configuración de Cuentas (Basado en el correo del cliente)
CUENTAS = {
    "1307": {"nombre": "General", "pass": "Heredada"}, # Aquí pondrás la clave real en secreto
    "2306": {"nombre": "Raza Particular", "pass": "Heredada"}
}

with st.sidebar:
    st.header("Configuración")
    user_select = st.selectbox("Seleccione Usuario Asocebu:", list(CUENTAS.keys()))
    st.info(f"Modo: {CUENTAS[user_select]['nombre']}")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

# 2. Procesamiento de Excel con Múltiples Pestañas
def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    dfs = []
    for sheet in xl.sheet_names:
        df = pd.read_excel(file, sheet_name=sheet)
        # Limpieza básica de nombres de columnas
        df.columns = [str(c).strip() for c in df.columns]
        # Agregamos el nombre del potrero (pestaña) como dato
        df['Potrero_Original'] = sheet
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

async def run_web_automation(df, user_code):
    results = []
    progress_bar = st.progress(0)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # El cliente mencionó dos URLs. Empezamos con la de consulta:
        await page.goto("https://sir.asocebu.com.co/Genealogias/", timeout=60000)

        total = len(df)
        for index, row in df.iterrows():
            # Buscamos la columna de registro (puede llamarse N° ANIMAL o similar)
            animal_id = str(row.get('N° ANIMAL', row.get('Registration_Number', ''))).strip()
            
            # Saltamos filas de "Total" o vacías
            if not animal_id or "total" in animal_id.lower():
                continue

            try:
                await page.fill('input[name="txtBusqueda"]', animal_id)
                await page.press('input[name="txtBusqueda"]', "Enter")
                await page.wait_for_timeout(1500)
                
                nombre_web = await page.inner_text('#lblNombreAnimal')
                results.append({**row, "Usuario": user_code, "Estado": "OK", "Nombre_Asocebu": nombre_web})
            except:
                results.append({**row, "Usuario": user_code, "Estado": "No Encontrado", "Nombre_Asocebu": "N/A"})
            
            progress_bar.progress((index + 1) / total)

        await browser.close()
        return pd.DataFrame(results)

# 3. Interfaz de Usuario
uploaded_file = st.file_uploader("Suba el archivo con las pestañas de Potreros", type=["xlsx"])

if uploaded_file:
    uploaded_file.seek(0)
    df_consolidado = procesar_archivo_cliente(uploaded_file)
    st.success(f"Detectados {len(df_consolidado)} registros en todas las pestañas.")

    if st.button("🚀 Iniciar Auditoría"):
        with st.spinner(f"Procesando con cuenta {user_select}..."):
            df_final = asyncio.run(run_web_automation(df_consolidado, user_select))
            st.dataframe(df_final)
            
            # Descarga
            df_final.to_excel("reporte_final.xlsx", index=False)
            with open("reporte_final.xlsx", "rb") as f:
                st.download_button("📥 Descargar Reporte Consolidado", f, "reporte_final.xlsx")