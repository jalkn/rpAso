import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os
import io

st.set_page_config(page_title="RPA Asocebu Pro", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría Integral: Registro Único")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

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
            if "REGISTRO" in row_str:
                header_row = i
                found = True
                break
        if found:
            df_clean = pd.read_excel(file, sheet_name=sheet, skiprows=header_row)
            df_clean.columns = [str(c).strip().upper().replace(' ', '_') for c in df_clean.columns]
            df_clean = df_clean.dropna(subset=['REGISTRO'], how='any')
            all_dfs.append(df_clean)
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

async def run_web_automation(df, max_rows):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        df_proc = df.head(max_rows).copy()
        for index, row in df_proc.iterrows():
            animal_id = str(row["REGISTRO"]).strip().split('.')[0].upper()
            status_text.text(f"🔍 Validando {index+1}/{len(df_proc)}: {animal_id}")
            res_row = row.to_dict()

            try:
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="networkidle")
                
                # BUSCAMOS EL IFRAME (Aquí es donde vive el contenido)
                frame = page.frame_locator('iframe[id*="Principal"], iframe[name*="Principal"]')
                
                # 1. Selección dentro del frame
                await frame.locator('select').select_option(value="1")
                
                # 2. Llenado y Enter
                await frame.locator('input[type="text"]').fill(animal_id)
                await page.keyboard.press("Enter")
                
                # 3. CLIC EN LA LUPA (Dentro del frame)
                lupa = frame.locator('input[src*="lupa"], .btn-ver, input[type="image"]').first
                await lupa.wait_for(timeout=10000)
                await lupa.click()
                
                # 4. ESPERA DE DATOS (Dentro del frame)
                raza_loc = frame.locator('#lblRaza')
                await raza_loc.wait_for(timeout=10000)
                
                raza_w = (await raza_loc.inner_text()).strip().upper()
                sexo_w = (await frame.locator('#lblSexo').inner_text()).strip().upper()
                color_w = (await frame.locator('#lblColor').inner_text()).strip().upper()
                nombre_w = (await frame.locator('#lblNombreAnimal').inner_text()).strip().upper()

                res_row.update({
                    "RESULTADO_RPA": "✅ ENCONTRADO", 
                    "INFO_WEB": f"{raza_w} | {sexo_w} | {color_w}",
                    "NOMBRE_OFICIAL": nombre_w
                })

            except:
                res_row.update({"RESULTADO_RPA": "❌ NO ENCONTRADO", "INFO_WEB": "N/A", "NOMBRE_OFICIAL": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# --- UI ---
file = st.file_uploader("Cargar Inventario", type=["xlsx"])
if file:
    df_c = procesar_archivo_cliente(file)
    if not df_c.empty:
        st.dataframe(df_c.head(3))
        if st.button("🚀 Iniciar Auditoría Final"):
            df_f = asyncio.run(run_web_automation(df_c, 100))
            st.success("✅ Completado")
            st.dataframe(df_f)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer) as writer: df_f.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte", buffer.getvalue(), "Auditoria_Asocebu.xlsx")