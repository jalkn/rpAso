import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os
import io

st.set_page_config(page_title="RPA Asocebu Cloud", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría Integral: Último Intento Cloud")

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
        # Usamos argumentos de sigilo para evitar bloqueos
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        df_proc = df.head(max_rows).copy()
        for index, row in df_proc.iterrows():
            animal_id = str(row["REGISTRO"]).strip().split('.')[0].upper()
            status_text.text(f"🔍 Validando {index+1}/{len(df_proc)}: {animal_id}")
            res_row = row.to_dict()

            try:
                # 1. Navegación con espera de carga completa
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="networkidle", timeout=45000)
                
                # 2. Identificar el Frame donde ocurre la magia
                # Asocebu suele usar 'iframePrincipal' o 'ctl00_iframePrincipal'
                frame_element = page.frame_locator('iframe[id*="Principal"]')
                
                # 3. Operar dentro del Frame
                # Seleccionar 'Registro'
                await frame_element.locator('select').select_option(value="1")
                # Escribir ID y presionar Enter
                input_field = frame_element.locator('input[type="text"]')
                await input_field.fill(animal_id)
                await page.keyboard.press("Enter")
                
                # 4. Espera forzada de la Lupa (selector múltiple)
                lupa = frame_element.locator('input[src*="lupa"], .btn-ver, input[type="image"]').first
                await lupa.wait_for(state="visible", timeout=12000)
                await lupa.click()
                
                # 5. Espera de la ficha técnica (el nombre del animal es el ID más estable)
                await frame_element.locator('#lblNombreAnimal').wait_for(state="visible", timeout=12000)
                
                # 6. Extracción de datos
                raza_w = await frame_element.locator('#lblRaza').inner_text()
                sexo_w = await frame_element.locator('#lblSexo').inner_text()
                color_w = await frame_element.locator('#lblColor').inner_text()
                nombre_w = await frame_element.locator('#lblNombreAnimal').inner_text()

                res_row.update({
                    "RESULTADO_RPA": "✅ ENCONTRADO", 
                    "INFO_WEB": f"{raza_w.strip()} | {sexo_w.strip()} | {color_w.strip()}",
                    "NOMBRE_OFICIAL": nombre_w.strip()
                })

            except Exception as e:
                res_row.update({"RESULTADO_RPA": "❌ NO ENCONTRADO", "INFO_WEB": "N/A", "NOMBRE_OFICIAL": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# --- INTERFAZ ---
file = st.file_uploader("Suba el archivo de Inventario", type=["xlsx"])
if file:
    df_c = procesar_archivo_cliente(file)
    if not df_c.empty:
        st.dataframe(df_c.head(3))
        if st.button("🚀 Ejecutar Validación Final"):
            df_f = asyncio.run(run_web_automation(df_c, 100))
            st.success("✅ Auditoría completada.")
            st.dataframe(df_f)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_f.to_excel(writer, index=False)
            st.download_button("📥 Descargar Resultados", buffer.getvalue(), "Reporte_Asocebu_Final.xlsx")