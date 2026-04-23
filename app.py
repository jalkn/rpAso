import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os
import io

st.set_page_config(page_title="RPA Asocebu Pro", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría de Registros Asocebu")

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
            # Limpieza total del registro (quita .0 y espacios)
            animal_id = str(row["REGISTRO"]).strip().split('.')[0].upper()
            status_text.text(f"🔍 Validando {index+1}/{len(df_proc)}: {animal_id}")
            res_row = row.to_dict()

            try:
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="networkidle", timeout=30000)
                
                # BUSCADOR DE CONTENIDO EN TODOS LOS FRAMES
                target_frame = None
                for frame in page.frames:
                    if await frame.query_selector('select') is not None:
                        target_frame = frame
                        break
                
                if target_frame:
                    # 1. Configurar búsqueda
                    await target_frame.select_option('select', value="1")
                    await target_frame.fill('input[type="text"]', animal_id)
                    await page.keyboard.press("Enter")
                    
                    # 2. Esperar y hacer clic en la lupa
                    lupa = target_frame.locator('input[src*="lupa"], .btn-ver, input[type="image"]').first
                    await lupa.wait_for(state="visible", timeout=10000)
                    await lupa.click()
                    
                    # 3. Extraer datos (esperar a que aparezca la raza)
                    raza_el = target_frame.locator('#lblRaza')
                    await raza_el.wait_for(state="visible", timeout=10000)
                    
                    res_row.update({
                        "RESULTADO_RPA": "✅ ENCONTRADO", 
                        "INFO_WEB": f"{await raza_el.inner_text()} | {await target_frame.locator('#lblSexo').inner_text()}",
                        "NOMBRE_OFICIAL": await target_frame.locator('#lblNombreAnimal').inner_text()
                    })
                else:
                    res_row.update({"RESULTADO_RPA": "❌ ERROR FRAME", "INFO_WEB": "N/A"})

            except:
                res_row.update({"RESULTADO_RPA": "❌ NO ENCONTRADO", "INFO_WEB": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# --- UI ---
file = st.file_uploader("Cargar Excel", type=["xlsx"])
if file:
    df_c = procesar_archivo_cliente(file)
    if not df_c.empty:
        st.dataframe(df_c.head(3))
        if st.button("🚀 Iniciar Validación"):
            df_f = asyncio.run(run_web_automation(df_c, 50))
            st.success("✅ Proceso terminado")
            st.dataframe(df_f)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer) as writer: df_f.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte", buffer.getvalue(), "Auditoria_Asocebu.xlsx")
