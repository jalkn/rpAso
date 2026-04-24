import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io

st.set_page_config(page_title="RPA Asocebu - Sniper v2.9", layout="wide")
st.title("🐄 Auditoría Asocebu: Sniper v2.9")

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
    for col in df.columns:
        if "REGISTRO" in col:
            df = df.rename(columns={col: "REGISTRO"})
            break
    return df

async def run_local_audit(df, num_rows):
    results = []
    progress_bar = st.progress(0)
    status = st.empty()
    monitor = st.empty() # Espacio para monitoreo en vivo
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=1500) 
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            status.text("🔗 Conectando con Asocebu...")
            await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="domcontentloaded")
        except Exception as e:
            st.error(f"Error de conexión inicial: {e}")
            await browser.close()
            return

        df_proc = df.head(num_rows).copy()
        
        for index, row in df_proc.iterrows():
            animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
            status.info(f"Procesando: **{animal_id}** ({index+1}/{num_rows})")
            
            try:
                # Monitoreo de pasos
                monitor.write(f"⚙️ Paso 1: Localizando frames...")
                f = next((fr for fr in page.frames if "mainFrame" in fr.name or "Genealogias" in fr.url), None)
                
                if f:
                    monitor.write(f"⚙️ Paso 2: Escribiendo registro...")
                    input_sel = "input[name='txtBusqueda']"
                    await f.wait_for_selector(input_sel, timeout=10000)
                    await f.type(input_sel, animal_id, delay=200)
                    
                    monitor.write(f"⚙️ Paso 3: Ejecutando consulta...")
                    await f.locator("input[name='btnConsultar']").click(force=True)
                    
                    await asyncio.sleep(2)
                    lupa = f.locator("input[src*='lupa']").first
                    if await lupa.is_visible():
                        await lupa.click()
                        await f.wait_for_selector("#lblNombreAnimal", timeout=8000)
                        row["NOMBRE_WEB"] = await f.locator("#lblNombreAnimal").inner_text()
                        row["RESULTADO_RPA"] = "✅ OK"
                        await f.locator("input[value*='Nueva']").first.click()
                    else:
                        row["RESULTADO_RPA"] = "⚠️ NO ENCONTRADO"
                else:
                    row["RESULTADO_RPA"] = "❌ ERROR FRAME"

            except Exception as e:
                # Monitoreo de error con captura
                row["RESULTADO_RPA"] = "❌ ERROR TÉCNICO"
                await page.screenshot(path="last_error.png")
                st.sidebar.image("last_error.png", caption=f"Error en {animal_id}")
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio")
            
            results.append(row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

file = st.file_uploader("📂 Sube tu Excel", type=["xlsx"])
if file:
    df_input = robust_read_excel(file)
    cant = st.number_input("Cantidad a auditar", 1, len(df_input), 5)
    
    if st.button("🚀 INICIAR SNIPER"):
        res = asyncio.run(run_local_audit(df_input, cant))
        if res is not None:
            st.dataframe(res)
            output = io.BytesIO()
            # Se usa el motor por defecto o xlsxwriter si está en requirements
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                res.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte", output.getvalue(), "resultado.xlsx")