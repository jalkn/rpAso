import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io

st.set_page_config(page_title="RPA Asocebu - Sniper v3.0", layout="wide")
st.title("🐄 Auditoría Asocebu: Sniper v3.0 (Hybrid Net-UI)")

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

async def run_hybrid_audit(df, num_rows):
    results = []
    progress_bar = st.progress(0)
    status = st.empty()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=500)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        page = await context.new_page()

        try:
            await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="networkidle", timeout=60000)
        except Exception:
            st.error("Error al cargar el portal. Reintenta.")
            return

        df_proc = df.head(num_rows).copy()
        for index, row in df_proc.iterrows():
            animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
            status.info(f"Procesando: **{animal_id}** ({index+1}/{num_rows})")
            
            try:
                # 1. Localizar frame principal
                f = next((fr for fr in page.frames if "mainFrame" in fr.name or "Genealogias" in fr.url), None)
                
                if f:
                    # Limpiar e ingresar datos
                    await f.fill("input[name='txtBusqueda']", "")
                    await f.type("input[name='txtBusqueda']", animal_id, delay=100)
                    
                    # 2. Clic con espera de red Y selectores
                    async with page.expect_response(lambda r: ".aspx" in r.url, timeout=15000) as response_info:
                        await f.click("input[name='btnConsultar']")
                    
                    # Espera corta para que el DOM se asiente
                    await asyncio.sleep(2)
                    
                    # 3. Intentar extraer nombre (vía UI para mayor seguridad)
                    nombre_elem = f.locator("#lblNombreAnimal")
                    if await nombre_elem.is_visible():
                        row["NOMBRE_WEB"] = await nombre_elem.inner_text()
                        row["RESULTADO_RPA"] = "✅ EXITOSO"
                    else:
                        # Si no está el nombre, quizás hay una lupa de resultados
                        lupa = f.locator("input[src*='lupa']").first
                        if await lupa.is_visible():
                            await lupa.click()
                            await asyncio.sleep(2)
                            row["NOMBRE_WEB"] = await f.locator("#lblNombreAnimal").inner_text()
                            row["RESULTADO_RPA"] = "✅ EXITOSO (Lupa)"
                        else:
                            row["RESULTADO_RPA"] = "⚠️ NO ENCONTRADO"
                    
                    # Reset para la siguiente consulta
                    reset_btn = f.locator("input[value*='Nueva']").first
                    if await reset_btn.is_visible():
                        await reset_btn.click()
                else:
                    row["RESULTADO_RPA"] = "❌ ERROR FRAME"

            except Exception as e:
                row["RESULTADO_RPA"] = "❌ ERROR DE FLUJO"
                # Si falla, refrescamos para limpiar el estado de ASP.NET
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="load")
            
            results.append(row)
            progress_bar.progress((index + 1) / len(df_proc))

        await browser.close()
        return pd.DataFrame(results)

# --- INTERFAZ ---
file = st.file_uploader("📂 Sube el Excel", type=["xlsx"])
if file:
    df_clean = robust_read_excel(file)
    cant = st.number_input("Cantidad", 1, len(df_clean), 10)
    if st.button("🚀 INICIAR AUDITORÍA V3"):
        res = asyncio.run(run_hybrid_audit(df_clean, cant))
        st.dataframe(res)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            res.to_excel(writer, index=False)
        st.download_button("📥 Descargar Reporte", output.getvalue(), "auditoria_asocebu.xlsx")