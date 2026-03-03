import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os

# Configuración de la página
st.set_page_config(page_title="RPA Asocebu Cloud", page_icon="🐄")
st.title("🐄 Auditoría de Inventario Asocebu")
st.markdown("Suba su archivo Excel para iniciar la conciliación automática.")

# 1. Subida de archivo
uploaded_file = st.file_uploader("Seleccione su archivo database.xlsx", type=["xlsx"])

async def run_web_automation(df):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    async with async_playwright() as p:
        # Nota: En la nube usamos 'headless=True'
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://sir.asocebu.com.co/Genealogias/")

        total = len(df)
        for index, row in df.iterrows():
            animal_id = str(row.get('Registration_Number', ''))
            status_text.text(f"Consultando animal {index+1} de {total}: {animal_id}")
            
            try:
                await page.fill('input[name="txtBusqueda"]', animal_id)
                await page.click('#btnConsultar')
                await page.wait_for_timeout(1500)
                
                # Ejemplo de extracción
                nombre_web = await page.inner_text('#lblNombreAnimal')
                results.append({**row, "Estado": "Encontrado", "Nombre_Asocebu": nombre_web})
            except:
                results.append({**row, "Estado": "No Encontrado", "Nombre_Asocebu": "N/A"})
            
            progress_bar.progress((index + 1) / total)

        await browser.close()
        return pd.DataFrame(results)

# 2. Lógica de ejecución
if uploaded_file is not None:
    df_input = pd.read_excel(uploaded_file)
    
    if st.button("Iniciar Automatización"):
        with st.spinner("El Bot está trabajando en el portal de Asocebu..."):
            # Ejecutar el bot
            df_final = asyncio.run(run_web_automation(df_input))
            
            st.success("¡Conciliación completada!")
            
            # 3. Botón de descarga
            output_name = "reporte_conciliacion.xlsx"
            df_final.to_excel(output_name, index=False)
            
            with open(output_name, "rb") as f:
                st.download_button(
                    label="📥 Descargar Reporte Final",
                    data=f,
                    file_name=output_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )