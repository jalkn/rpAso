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
            df_clean['HOJA_ORIGEN'] = sheet
            all_dfs.append(df_clean)
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

async def run_web_automation(df, max_rows):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    async with async_playwright() as p:
        # Usamos un agente de usuario real para evitar bloqueos del servidor
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        df_proc = df.head(max_rows).copy()
        for index, row in df_proc.iterrows():
            # Limpiamos el ID: solo números y letras, sin decimales
            animal_id = str(row["REGISTRO"]).strip().split('.')[0].upper()
            status_text.text(f"🔍 Buscando Registro: {animal_id} ({index+1}/{len(df_proc)})")
            res_row = row.to_dict()

            try:
                # 1. Ir al inicio y esperar que cargue el selector de búsqueda
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="networkidle")
                
                # 2. Seleccionar 'Registro' por texto para evitar IDs dinámicos
                await page.select_option("select", label="Registro")
                
                # 3. Llenar el campo de búsqueda
                await page.fill("input[type='text']", animal_id)
                await page.keyboard.press("Enter")
                
                # 4. ESPERA DE RESULTADOS: Buscamos el botón 'Ver' o la lupa
                # Usamos una espera con reintento para la tabla
                lupa = await page.wait_for_selector("input[type='image'], .btn-ver, text='Ver'", timeout=10000)
                await lupa.click()
                
                # 5. ESPERA DE FICHA TÉCNICA: Buscamos las etiquetas de los datos
                await page.wait_for_selector("text='Raza:'", timeout=10000)
                
                # Extracción robusta por proximidad de texto
                # Buscamos el elemento que está al lado de la etiqueta 'Raza:', 'Sexo:', etc.
                raza_w = await page.locator("td:has-text('Raza:') + td").inner_text()
                sexo_w = await page.locator("td:has-text('Sexo:') + td").inner_text()
                color_w = await page.locator("td:has-text('Color:') + td").inner_text()
                nombre_w = await page.locator("#lblNombreAnimal").inner_text()

                res_row.update({
                    "RESULTADO_RPA": "✅ ENCONTRADO", 
                    "INFO_WEB": f"{raza_w.strip()} | {sexo_w.strip()} | {color_w.strip()}",
                    "NOMBRE_OFICIAL": nombre_w.strip()
                })

            except Exception:
                res_row.update({"RESULTADO_RPA": "❌ NO ENCONTRADO", "INFO_WEB": "N/A", "NOMBRE_OFICIAL": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# --- INTERFAZ ---
file = st.file_uploader("Cargar Inventario", type=["xlsx"])
if file:
    df_c = procesar_archivo_cliente(file)
    if not df_c.empty:
        st.dataframe(df_c.head(3))
        if st.button("🚀 Ejecutar Auditoría"):
            df_f = asyncio.run(run_web_automation(df_c, 100))
            st.success("✅ Proceso terminado")
            st.dataframe(df_f)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer) as writer: df_f.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte", buffer.getvalue(), "Auditoria_Final.xlsx")