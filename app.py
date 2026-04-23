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
        # Contexto persistente con User Agent de humano
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        df_proc = df.head(max_rows).copy()
        for index, row in df_proc.iterrows():
            # Limpiamos el registro para que sea siempre texto
            animal_id = str(row["REGISTRO"]).strip().split('.')[0].upper()
            status_text.text(f"🔍 Validando Registro: {animal_id} ({index+1}/{len(df_proc)})")
            res_row = row.to_dict()

            try:
                # 1. Navegación directa
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="domcontentloaded", timeout=30000)
                
                # 2. Selección de tipo de búsqueda (Registro = 1)
                await page.wait_for_selector('select[id*="ddlTipoBusqueda"]', timeout=5000)
                await page.select_option('select[id*="ddlTipoBusqueda"]', value="1")
                
                # 3. Llenar búsqueda y presionar Enter
                input_busqueda = await page.query_selector('input[id*="txtBusqueda"]')
                await input_busqueda.fill(animal_id)
                await page.keyboard.press("Enter")
                
                # 4. Esperar la lupa o botón 'Ver' (múltiples selectores)
                btn_ver = await page.wait_for_selector('input[type="image"], .btn-ver, img[src*="lupa"]', timeout=10000)
                await btn_ver.click()
                
                # 5. Esperar la carga de la ficha técnica
                await page.wait_for_selector('#lblRaza', timeout=10000)
                
                # 6. Extracción de datos con limpieza de espacios
                raza_w = (await page.inner_text('#lblRaza')).strip().upper()
                sexo_w = (await page.inner_text('#lblSexo')).strip().upper()
                color_w = (await page.inner_text('#lblColor')).strip().upper()
                nombre_w = (await page.inner_text('#lblNombreAnimal')).strip().upper()

                res_row.update({
                    "RESULTADO_RPA": "✅ ENCONTRADO", 
                    "INFO_WEB": f"{raza_w} | {sexo_w} | {color_w}",
                    "NOMBRE_OFICIAL": nombre_w
                })

            except Exception:
                res_row.update({
                    "RESULTADO_RPA": "❌ NO ENCONTRADO", 
                    "INFO_WEB": "N/A", 
                    "NOMBRE_OFICIAL": "N/A"
                })
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# --- UI ---
file = st.file_uploader("Cargar Archivo Excel", type=["xlsx"])
if file:
    df_c = procesar_archivo_cliente(file)
    if not df_c.empty:
        st.dataframe(df_c.head(3))
        limit = st.slider("Registros a procesar", 1, 500, 20)
        if st.button("🚀 Iniciar Auditoría"):
            df_f = asyncio.run(run_web_automation(df_c, limit))
            st.success("✅ Auditoría finalizada")
            st.dataframe(df_f)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_f.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte", buffer.getvalue(), "Auditoria_Asocebu.xlsx")