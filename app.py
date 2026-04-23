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

# NUEVA FUNCIÓN: Busca la cabecera correcta automáticamente
def robust_read_excel(file):
    # Intentamos leer el archivo completo primero
    df_raw = pd.read_excel(file, header=None)
    
    # Buscamos la fila que contiene la palabra "REGISTRO"
    header_row = 0
    for i, row in df_raw.iterrows():
        # Convertimos la fila a string y buscamos la palabra clave
        row_str = " ".join([str(x).upper() for x in row.values if pd.notna(x)])
        if "REGISTRO" in row_str:
            header_row = i
            break
            
    # Volvemos a leer desde esa fila
    file.seek(0)
    df = pd.read_excel(file, skiprows=header_row)
    
    # Limpieza extrema de nombres de columnas
    df.columns = [str(c).strip().upper().replace(' ', '_').replace('°', '') for c in df.columns]
    
    # Si aún no se llama "REGISTRO" exactamente, buscamos la columna que más se le parezca
    if "REGISTRO" not in df.columns:
        for col in df.columns:
            if "REGISTRO" in col:
                df = df.rename(columns={col: "REGISTRO"})
                break
                
    return df

async def run_web_automation(df, max_rows):
    results = []
    progress_bar = st.progress(0)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        # Asegurarnos de que tenemos la columna antes de empezar
        if "REGISTRO" not in df.columns:
            st.error(f"❌ No se encontró la columna 'REGISTRO'. Columnas detectadas: {list(df.columns)}")
            return pd.DataFrame()

        df_proc = df.head(max_rows).copy()
        for index, row in df_proc.iterrows():
            animal_id = str(row["REGISTRO"]).strip().split('.')[0].upper()
            res_row = row.to_dict()

            try:
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="networkidle", timeout=20000)
                frame = page.frame_locator('iframe[id*="Principal"]')
                
                await frame.locator('select').select_option(value="1")
                await frame.locator('input[type="text"]').fill(animal_id)
                await page.keyboard.press("Enter")
                
                lupa = frame.locator('input[src*="lupa"], .btn-ver, input[type="image"]').first
                await lupa.wait_for(state="visible", timeout=10000)
                await lupa.click()
                
                await frame.locator('#lblRaza').wait_for(state="visible", timeout=10000)
                
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

# --- UI ---
file = st.file_uploader("Cargar Inventario (Excel)", type=["xlsx"])
if file:
    with st.spinner("Leyendo archivo..."):
        df_c = robust_read_excel(file)
    
    st.write("### Vista previa de los datos cargados:")
    st.dataframe(df_c.head(5))
    
    if "REGISTRO" in df_c.columns:
        if st.button("🚀 Iniciar Auditoría"):
            df_f = asyncio.run(run_web_automation(df_c, 50))
            if not df_f.empty:
                st.success("✅ Proceso completado")
                st.dataframe(df_f)
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer) as writer: df_f.to_excel(writer, index=False)
                st.download_button("📥 Descargar Resultados", buffer.getvalue(), "Auditoria_Final.xlsx")
    else:
        st.error("⚠️ El bot no pudo encontrar una columna llamada 'REGISTRO'. Por favor revisa el formato del Excel.")