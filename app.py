import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="RPA Asocebu - Sniper v3.1", layout="wide")
st.title("🐄 Auditoría Asocebu: Sniper v3.1 (Aislamiento Total)")

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
    # Asegurar que la columna REGISTRO sea identificada
    for col in df.columns:
        if "REGISTRO" in col:
            df = df.rename(columns={col: "REGISTRO"})
            break
    return df

async def run_isolated_audit(df, num_rows):
    results = []
    progress_bar = st.progress(0)
    status = st.empty()
    
    async with async_playwright() as p:
        # headless=True es obligatorio en la nube
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        
        df_proc = df.head(num_rows).copy()
        
        for index, row in df_proc.iterrows():
            animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
            if not animal_id or animal_id.lower() == "nan": continue
            
            status.info(f"🧬 Procesando en entorno limpio: **{animal_id}** ({index+1}/{num_rows})")
            
            # PASO CLAVE: Crear contexto y página nuevos para cada registro
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # Navegación con timeout generoso
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="networkidle", timeout=45000)
                
                # Localización del frame
                f = next((fr for fr in page.frames if "mainFrame" in fr.name or "Genealogias" in fr.url), None)
                
                if f:
                    # Inyección de datos
                    await f.wait_for_selector("input[name='txtBusqueda']", timeout=10000)
                    await f.fill("input[name='txtBusqueda']", "")
                    await f.type("input[name='txtBusqueda']", animal_id, delay=150)
                    
                    # Espera de la respuesta del servidor tras el click
                    async with page.expect_response(lambda r: ".aspx" in r.url, timeout=20000):
                        await f.click("input[name='btnConsultar']")
                    
                    # Tiempo de renderizado
                    await asyncio.sleep(3)
                    
                    # Extracción de información
                    nombre_lbl = f.locator("#lblNombreAnimal")
                    if await nombre_lbl.count() > 0:
                        row["NOMBRE_WEB"] = await nombre_lbl.inner_text()
                        row["RESULTADO_RPA"] = "✅ EXITOSO"
                    else:
                        # Intento por Lupa si hay tabla de resultados
                        lupa = f.locator("input[src*='lupa']").first
                        if await lupa.count() > 0:
                            await lupa.click()
                            await asyncio.sleep(2)
                            row["NOMBRE_WEB"] = await f.locator("#lblNombreAnimal").inner_text() if await f.locator("#lblNombreAnimal").count() > 0 else "N/A"
                            row["RESULTADO_RPA"] = "✅ EXITOSO (Detalle)"
                        else:
                            row["RESULTADO_RPA"] = "⚠️ NO ENCONTRADO"
                else:
                    row["RESULTADO_RPA"] = "❌ ERROR: FRAME NO CARGÓ"

            except Exception as e:
                row["RESULTADO_RPA"] = "❌ ERROR DE FLUJO"
            
            # Limpieza absoluta de la sesión
            await context.close()
            results.append(row)
            progress_bar.progress((index + 1) / len(df_proc))

        await browser.close()
        return pd.DataFrame(results)

# --- UI STREAMLIT ---
file = st.file_uploader("📂 Sube tu archivo Excel", type=["xlsx"])
if file:
    df_clean = robust_read_excel(file)
    st.success(f"Registros listos: {len(df_clean)}")
    cant = st.number_input("Cantidad a procesar", 1, len(df_clean), 10)
    
    if st.button("🚀 INICIAR SNIPER V3.1"):
        res = asyncio.run(run_isolated_audit(df_clean, cant))
        if res is not None:
            st.dataframe(res)
            
            # Exportación final
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                res.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte Final", output.getvalue(), "auditoria_final.xlsx")