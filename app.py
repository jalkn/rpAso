import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os
import io

st.set_page_config(page_title="RPA Asocebu Pro", layout="wide")
st.title("🐄 Auditoría de Registros Asocebu")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

def robust_read_excel(file):
    # 1. Leer el Excel sin asumir cabeceras primero
    df_raw = pd.read_excel(file, header=None)
    
    # 2. Buscar la fila donde realmente están los títulos
    header_row = 0
    for i, row in df_raw.iterrows():
        row_values = [str(x).upper() for x in row.values if pd.notna(x)]
        if any("REGISTRO" in val for val in row_values):
            header_row = i
            break
    
    # 3. Re-leer desde esa fila
    file.seek(0)
    df = pd.read_excel(file, skiprows=header_row)
    
    # 4. Limpieza agresiva de nombres de columnas (quitar espacios, puntos, etc.)
    df.columns = [str(c).strip().upper().replace(' ', '_').replace('.', '').replace('N°', 'N') for c in df.columns]
    
    # 5. Mapeo inteligente: Si no se llama 'REGISTRO' exacto, buscar la mejor opción
    col_map = {col: "REGISTRO" for col in df.columns if "REGISTRO" in col}
    df = df.rename(columns=col_map)
    
    return df

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
            # Manejo seguro del ID del animal
            val_reg = row.get("REGISTRO", "")
            animal_id = str(val_reg).strip().split('.')[0].upper()
            
            status_text.text(f"🔍 Validando {index+1}/{len(df_proc)}: {animal_id}")
            res_row = row.to_dict()

            if not animal_id or animal_id == "NAN":
                res_row.update({"RESULTADO_RPA": "❌ DATO VACÍO"})
                results.append(res_row)
                continue

            try:
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="networkidle", timeout=30000)
                frame = page.frame_locator('iframe[id*="Principal"]')
                
                await frame.locator('select').select_option(value="1")
                await frame.locator('input[type="text"]').fill(animal_id)
                await page.keyboard.press("Enter")
                
                lupa = frame.locator('input[src*="lupa"], .btn-ver, input[type="image"]').first
                await lupa.wait_for(state="visible", timeout=12000)
                await lupa.click()
                
                await frame.locator('#lblRaza').wait_for(state="visible", timeout=12000)
                
                res_row.update({
                    "RESULTADO_RPA": "✅ ENCONTRADO", 
                    "INFO_WEB": f"{await frame.locator('#lblRaza').inner_text()} | {await frame.locator('#lblSexo').inner_text()}",
                    "NOMBRE_OFICIAL": await frame.locator('#lblNombreAnimal').inner_text()
                })
            except:
                res_row.update({"RESULTADO_RPA": "❌ NO ENCONTRADO", "INFO_WEB": "N/A", "NOMBRE_OFICIAL": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# --- INTERFAZ ---
file = st.file_uploader("Cargar Archivo de Inventario", type=["xlsx"])
if file:
    with st.spinner("Analizando estructura del Excel..."):
        df_c = robust_read_excel(file)
    
    st.write("### Datos detectados:")
    st.dataframe(df_c.head(5))
    
    if "REGISTRO" in df_c.columns:
        if st.button("🚀 Iniciar Validación de Datos"):
            df_f = asyncio.run(run_web_automation(df_c, 50))
            st.success("✅ Proceso finalizado")
            st.dataframe(df_f)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer) as writer: df_f.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte Final", buffer.getvalue(), "Auditoria_Asocebu_Corregida.xlsx")
    else:
        st.error("No se detectó la columna 'REGISTRO'. Verifique que el nombre esté escrito correctamente en el Excel.")