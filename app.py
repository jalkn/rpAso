import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io

st.set_page_config(page_title="RPA Asocebu - Sniper v3.0", layout="wide")
st.title("🐄 Auditoría Asocebu: Sniper v3.0 (Zero-Session Edition)")

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
    if "REGISTRO" not in df.columns:
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
        # headless=True es vital para Streamlit Cloud
        browser = await p.chromium.launch(headless=True, slow_mo=800)
        
        df_proc = df.head(num_rows).copy()
        
        for index, row in df_proc.iterrows():
            animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
            status.info(f"🚀 Procesando: **{animal_id}** ({index+1}/{num_rows})")
            
            # CREAMOS UN CONTEXTO NUEVO POR CADA ANIMAL (Borra cookies/caché)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # Navegación directa al frame de consulta si es posible
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="networkidle", timeout=45000)
                
                f = next((fr for fr in page.frames if "mainFrame" in fr.name or "Genealogias" in fr.url), None)
                
                if f:
                    # Llenado con delay humano
                    await f.fill("input[name='txtBusqueda']", "")
                    await f.type("input[name='txtBusqueda']", animal_id, delay=150)
                    
                    # Esperamos la respuesta del servidor ASPX
                    async with page.expect_response(lambda r: ".aspx" in r.url, timeout=20000):
                        await f.click("input[name='btnConsultar']")
                    
                    await asyncio.sleep(2.5)
                    
                    # Lógica de extracción de nombre
                    nombre_lbl = f.locator("#lblNombreAnimal")
                    if await nombre_lbl.count() > 0:
                        row["NOMBRE_WEB"] = await nombre_lbl.inner_text()
                        row["RESULTADO_RPA"] = "✅ EXITOSO"
                    else:
                        # Si hay tabla de resultados, click en la primera lupa
                        lupa = f.locator("input[src*='lupa']").first
                        if await lupa.count() > 0:
                            await lupa.click()
                            await asyncio.sleep(2)
                            row["NOMBRE_WEB"] = await f.locator("#lblNombreAnimal").inner_text() if await f.locator("#lblNombreAnimal").count() > 0 else "N/A"
                            row["RESULTADO_RPA"] = "✅ EXITOSO (Detalle)"
                        else:
                            row["RESULTADO_RPA"] = "⚠️ NO ENCONTRADO"
                else:
                    row["RESULTADO_RPA"] = "❌ ERROR: PORTAL CAÍDO"

            except Exception as e:
                row["RESULTADO_RPA"] = "❌ ERROR DE FLUJO"
            
            # CERRAMOS CONTEXTO (Limpieza total)
            await context.close()
            results.append(row)
            progress_bar.progress((index + 1) / len(df_proc))

        await browser.close()
        return pd.DataFrame(results)

# --- INTERFAZ ---
file = st.file_uploader("📂 Sube el Inventario (Excel)", type=["xlsx"])
if file:
    df_clean = robust_read_excel(file)
    cant = st.number_input("Cantidad de registros a auditar", 1, len(df_clean), 10)
    
    if st.button("🚀 INICIAR SNIPER V3.0"):
        res = asyncio.run(run_hybrid_audit(df_clean, cant))
        st.dataframe(res)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            res.to_excel(writer, index=False)
        st.download_button("📥 Descargar Resultados", output.getvalue(), "auditoria_asocebu.xlsx")