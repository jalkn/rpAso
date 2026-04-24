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
    df_raw = pd.read_excel(file, header=None)
    header_row = 0
    for i, row in df_raw.iterrows():
        row_values = [str(x).upper() for x in row.values if pd.notna(x)]
        if any("REGISTRO" in val for val in row_values):
            header_row = i
            break
    file.seek(0)
    df = pd.read_excel(file, skiprows=header_row)
    df.columns = [str(c).strip().upper().replace(' ', '_').replace('.', '').replace('N°', 'N') for c in df.columns]
    col_map = {col: "REGISTRO" for col in df.columns if "REGISTRO" in col}
    return df.rename(columns=col_map)

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
            # Limpieza profunda del ID
            val_reg = str(row.get("REGISTRO", "")).strip().split('.')[0]
            animal_id = "".join(filter(str.isalnum, val_reg)).upper() # Solo letras y números
            
            status_text.text(f"🔍 Validando {index+1}/{len(df_proc)}: {animal_id}")
            res_row = row.to_dict()

            if not animal_id or animal_id == "NAN":
                res_row.update({"RESULTADO_RPA": "❌ DATO VACÍO"})
                results.append(res_row)
                continue

            try:
                # 1. Carga con tiempo de gracia para scripts pesados
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="load", timeout=40000)
                frame = page.frame_locator('iframe[id*="Principal"]')
                
                # 2. Selección del tipo de búsqueda
                dropdown = frame.locator('select')
                await dropdown.wait_for(state="visible")
                await dropdown.select_option(value="1")
                
                # 3. Llenado con pausa (simula escritura humana)
                input_field = frame.locator('input[type="text"]')
                await input_field.click()
                await input_field.fill(animal_id)
                await asyncio.sleep(1) # Pausa crítica para que el sitio procese el input
                
                # 4. Clic en la lupa (usando el selector más específico posible)
                lupa = frame.locator('input[src*="lupa"], input[type="image"], .btn-ver').first
                await lupa.click()
                
                # 5. Espera de la ficha técnica (esperamos el label de la Raza)
                raza_lbl = frame.locator('#lblRaza')
                await raza_lbl.wait_for(state="visible", timeout=15000)
                
                # 6. Extracción
                raza = await raza_lbl.inner_text()
                sexo = await frame.locator('#lblSexo').inner_text()
                nombre = await frame.locator('#lblNombreAnimal').inner_text()

                res_row.update({
                    "RESULTADO_RPA": "✅ ENCONTRADO", 
                    "INFO_WEB": f"{raza.strip()} | {sexo.strip()}",
                    "NOMBRE_OFICIAL": nombre.strip()
                })
            except:
                res_row.update({"RESULTADO_RPA": "❌ NO ENCONTRADO", "INFO_WEB": "N/A", "NOMBRE_OFICIAL": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# --- UI ---
file = st.file_uploader("Subir Inventario", type=["xlsx"])
if file:
    df_c = robust_read_excel(file)
    st.write("Registros detectados:", len(df_c))
    if st.button("🚀 Iniciar Auditoría"):
        df_f = asyncio.run(run_web_automation(df_c, 100))
        st.dataframe(df_f)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer) as writer: df_f.to_excel(writer, index=False)
        st.download_button("📥 Descargar Reporte", buffer.getvalue(), "Auditoria_Asocebu.xlsx")