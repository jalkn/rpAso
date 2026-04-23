import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os
import io

st.set_page_config(page_title="RPA Asocebu Maestro", layout="wide")
st.title("🐄 Auditoría de Registros (Versión de Alta Precisión)")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

async def run_web_automation(df, max_rows):
    results = []
    progress_bar = st.progress(0)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        df_proc = df.head(max_rows).copy()
        for index, row in df_proc.iterrows():
            animal_id = str(row["REGISTRO"]).strip().split('.')[0].upper()
            res_row = row.to_dict()

            try:
                # 1. Entrar directamente a la página
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="networkidle")
                
                # 2. Localizar el frame principal (donde Asocebu guarda sus scripts)
                frame = page.frame_locator('iframe[id*="Principal"]')
                
                # 3. Forzar la selección y el llenado usando JavaScript (más rápido y seguro)
                await frame.locator('select').evaluate('(el, val) => el.value = val', "1")
                await frame.locator('input[type="text"]').fill(animal_id)
                
                # 4. Disparar el evento de búsqueda
                await page.keyboard.press("Enter")
                
                # 5. Intentar hacer clic en la lupa con reintento agresivo
                lupa = frame.locator('input[src*="lupa"], .btn-ver, input[type="image"]').first
                await lupa.wait_for(state="visible", timeout=15000)
                await lupa.click()
                
                # 6. Esperar la etiqueta de Raza (que confirma que cargó la ficha)
                raza_lbl = frame.locator('#lblRaza')
                await raza_lbl.wait_for(state="visible", timeout=15000)
                
                # 7. Extracción de los 4 datos clave
                raza = (await raza_lbl.inner_text()).strip()
                sexo = (await frame.locator('#lblSexo').inner_text()).strip()
                color = (await frame.locator('#lblColor').inner_text()).strip()
                nombre = (await frame.locator('#lblNombreAnimal').inner_text()).strip()

                res_row.update({
                    "RESULTADO_RPA": "✅ ENCONTRADO", 
                    "INFO_WEB": f"{raza} | {sexo} | {color}",
                    "NOMBRE_OFICIAL": nombre
                })
            except:
                res_row.update({"RESULTADO_RPA": "❌ NO ENCONTRADO", "INFO_WEB": "N/A", "NOMBRE_OFICIAL": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# --- INTERFAZ ---
file = st.file_uploader("Cargar Inventario", type=["xlsx"])
if file:
    df_c = pd.read_excel(file) # El bot buscará la columna 'REGISTRO'
    if st.button("🚀 Iniciar Validación"):
        df_f = asyncio.run(run_web_automation(df_c, 50))
        st.dataframe(df_f)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer) as writer: df_f.to_excel(writer, index=False)
        st.download_button("📥 Descargar Reporte", buffer.getvalue(), "Auditoria_Asocebu.xlsx")