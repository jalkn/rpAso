import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io

# =========================================================
# CONFIGURACIÓN DE INTERFAZ - Sniper v2.9 (Copia de rpa.py)
# =========================================================
st.set_page_config(page_title="RPA Asocebu - Sniper v2.9", layout="wide")
st.title("🐄 Auditoría Asocebu: Sniper v2.9 (Foco en Consulta)")

def robust_read_excel(file):
    # Lectura robusta identificando la cabecera 'REGISTRO'
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
    
    async with async_playwright() as p:
        # Lanzamos navegador. Headless=True es obligatorio en Streamlit Cloud.
        # Se mantiene slow_mo=1500 para estabilidad y evitar bloqueos.
        browser = await p.chromium.launch(
            headless=True, 
            slow_mo=1500,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        ) 
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            status.text("🔗 Cargando portal...")
            await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="domcontentloaded")
        except Exception as e:
            st.error(f"Error de conexión: {e}")
            await browser.close()
            return

        df_proc = df.head(num_rows).copy()
        
        for index, row in df_proc.iterrows():
            val = row.get("REGISTRO", "")
            animal_id = str(val).strip().split('.')[0] if pd.notna(val) else ""
            if not animal_id or animal_id.lower() == "nan": continue

            status.text(f"🚀 Procesando registro: {animal_id}")
            
            try:
                # 1. LOCALIZAR FRAME (Lógica de rpa.py)
                f = None
                for frame in page.frames:
                    if "mainFrame" in frame.name or "Genealogias" in frame.url:
                        f = frame
                        break
                
                if f:
                    # 2. DIGITACIÓN (Simulación humana verificada en rpa.py)
                    input_sel = "input[name='txtBusqueda']"
                    await f.wait_for_selector(input_sel, timeout=10000)
                    await f.click(input_sel)
                    await f.fill(input_sel, "")
                    await f.type(input_sel, animal_id, delay=200)
                    
                    # 3. ACCIÓN DE CONSULTA
                    btn_consultar = f.locator("input[name='btnConsultar']")
                    await btn_consultar.hover()
                    await btn_consultar.click(force=True)
                    
                    # 4. ESPERA DE CAMBIO DE PÁGINA
                    try:
                        await f.wait_for_function(
                            "document.body.innerText.includes('Resultados') || document.body.innerText.includes('Ejemplar')",
                            timeout=10000
                        )
                        
                        # 5. EXTRACCIÓN DE DATOS TRAS CLICK EN LUPA
                        lupa = f.locator("input[src*='lupa']").first
                        if await lupa.is_visible():
                            await lupa.click()
                            await f.wait_for_selector("#lblNombreAnimal", timeout=8000)
                            
                            row["NOMBRE_WEB"] = await f.locator("#lblNombreAnimal").inner_text()
                            row["RESULTADO_RPA"] = "✅ OK"
                            
                            # Clic en "Nueva Consulta" para resetear el flujo
                            await f.locator("input[value*='Nueva']").first.click()
                        else:
                            row["RESULTADO_RPA"] = "⚠️ REGISTRO NO ENCONTRADO"

                    except Exception:
                        # Reintento con Enter si el botón falla
                        await page.keyboard.press("Enter")
                        row["RESULTADO_RPA"] = "⏳ REINTENTO CON ENTER"
                else:
                    row["RESULTADO_RPA"] = "❌ ERROR: FRAME"

            except Exception:
                row["RESULTADO_RPA"] = "❌ ERROR TÉCNICO"
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="load")
            
            results.append(row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        status.success("✅ Auditoría completada")
        return pd.DataFrame(results)

# --- UI STREAMLIT ---
file = st.file_uploader("📂 Sube tu Excel", type=["xlsx"])
if file:
    df_input = robust_read_excel(file)
    st.write(f"Registros encontrados: {len(df_input)}")
    cant = st.number_input("Cantidad a auditar", 1, len(df_input), 5)
    
    if st.button("🚀 INICIAR SNIPER"):
        with st.spinner("Ejecutando auditoría..."):
            # Ejecución asíncrona compatible con Streamlit Cloud
            res = asyncio.run(run_local_audit(df_input, cant))
            if res is not None:
                st.dataframe(res)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    res.to_excel(writer, index=False)
                st.download_button("📥 Descargar Reporte", output.getvalue(), "resultado_asocebu.xlsx")