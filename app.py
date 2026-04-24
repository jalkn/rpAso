import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io

st.set_page_config(page_title="RPA Asocebu - Backend Edition", layout="wide")
st.title("🐄 Auditoría Asocebu: Modo Interceptor")

def robust_read_excel(file):
    df_raw = pd.read_excel(file, header=None)
    header_row = 0
    for i, row in df_raw.iterrows():
        if i > 30: break
        row_str = " ".join([str(x).upper() for x in row.values if pd.notna(x)])
        if "REGISTRO" in row_str:
            header_row = i
            break
    file.seek(0)
    df = pd.read_excel(file, skiprows=header_row)
    df.columns = [str(c).strip().upper().replace(' ', '_') for c in df.columns]
    return df

async def run_backend_audit(df, num_rows):
    results = []
    progress_bar = st.progress(0)
    status = st.empty()
    
    async with async_playwright() as p:
        # Launch en modo headless para Streamlit Cloud
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0...")
        page = await context.new_page()

        await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="networkidle")

        df_proc = df.head(num_rows).copy()
        for index, row in df_proc.iterrows():
            animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
            status.info(f"Analizando flujo de red para: **{animal_id}**")
            
            try:
                # Identificamos el frame de trabajo
                frame = next((f for f in page.frames if "mainFrame" in f.name or "Genealogias" in f.url), None)
                
                if frame:
                    # Acción: Llenar y Consultar
                    await frame.fill("input[name='txtBusqueda']", animal_id)
                    
                    # Preparamos la escucha de la respuesta de red (POST)
                    async with page.expect_response(lambda response: ".aspx" in response.url and response.status == 200) as response_info:
                        await frame.click("input[name='btnConsultar']")
                    
                    # Obtenemos el cuerpo de la respuesta (HTML)
                    response = await response_info.value
                    html_content = await response.text()
                    
                    # Extracción rápida: Buscamos el nombre entre los tags que vimos en tus fotos
                    if "lblNombreAnimal" in html_content:
                        # Una forma ruda pero efectiva de extraer sin lxml en la nube
                        nombre = html_content.split('lblNombreAnimal">')[1].split('</span>')[0]
                        row["NOMBRE_WEB"] = nombre
                        row["RESULTADO_RPA"] = "✅ EXITOSO (Red)"
                    else:
                        row["RESULTADO_RPA"] = "⚠️ NO EN RED"
                
                # Pequeña pausa para no saturar el socket
                await asyncio.sleep(1)

            except Exception as e:
                row["RESULTADO_RPA"] = "❌ ERROR DE FLUJO"
                await page.reload()
            
            results.append(row)
            progress_bar.progress((index + 1) / len(df_proc))

        await browser.close()
        return pd.DataFrame(results)

# --- UI INTERFAZ ---
file = st.file_uploader("📂 Sube el Excel", type=["xlsx"])
if file:
    df_clean = robust_read_excel(file)
    cant = st.number_input("Cantidad", 1, len(df_clean), 5)
    if st.button("🚀 INICIAR EXTRACCIÓN BACKEND"):
        res = asyncio.run(run_backend_audit(df_clean, cant))
        st.dataframe(res)