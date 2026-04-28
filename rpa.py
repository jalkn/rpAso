import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io

# Configuración de la página
st.set_page_config(page_title="RPA Asocebu - Local Sniper", layout="wide")
st.title("🐄 Auditoría Asocebu: Ejecución Local")
st.markdown("---")

def robust_read_excel(file):
    """Lectura inteligente del Excel para encontrar la columna REGISTRO"""
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
    status_text = st.empty()
    
    async with async_playwright() as p:
        # headless=False: Abre la ventana para que veas el proceso
        # slow_mo: Da tiempo a la web de reaccionar
        browser = await p.chromium.launch(headless=False, slow_mo=1200) 
        context = await browser.new_context()
        page = await context.new_page()

        status_text.info("Conectando con el portal de Asocebu...")
        await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="domcontentloaded", timeout=90000)

        df_proc = df.head(num_rows).copy()
        
        for index, row in df_proc.iterrows():
            animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
            status_text.info(f"Procesando {index+1}/{num_rows}: **Registro {animal_id}**")
            
            try:
                # INYECCIÓN MAESTRA: Llena el campo y hace clic en 'Consultar'
                injection_js = f"""
                (function() {{
                    function solve(root, val) {{
                        let sel = root.querySelector('select');
                        if (sel) {{ sel.value = '1'; sel.dispatchEvent(new Event('change', {{bubbles:true}})); }}
                        
                        let inp = root.querySelector('input[type="text"]');
                        if (inp) {{
                            inp.focus();
                            inp.value = val;
                            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            
                            // Buscar el botón 'Consultar' por su valor de texto
                            let btns = Array.from(root.querySelectorAll('input[type="button"], input[type="submit"], input'));
                            let btn = btns.find(b => b.value && b.value.toUpperCase().includes('CONSULTAR'));
                            if (btn) {{ btn.click(); return "OK"; }}
                        }}
                        
                        let frames = root.querySelectorAll('iframe');
                        for (let f of frames) {{
                            try {{ if (solve(f.contentDocument || f.contentWindow.document, val)) return "OK"; }} catch(e) {{}}
                        }}
                        return null;
                    }}
                    return solve(document, '{animal_id}');
                }})();
                """
                await page.evaluate(injection_js)
                await asyncio.sleep(4) # Espera a que cargue la tabla de resultados

                # Clic en Detalle (La segunda lupa)
                detalle_js = """
                (function() {
                    function getLupa(root) {
                        let lupas = root.querySelectorAll('input[src*="lupa"], .btn-ver');
                        if (lupas.length > 1) { lupas[1].click(); return true; }
                        let frames = root.querySelectorAll('iframe');
                        for (let f of frames) {
                            try { if (getLupa(f.contentDocument)) return true; } catch(e) {}
                        }
                        return false;
                    }
                    return getLupa(document);
                })();
                """
                await page.evaluate(detalle_js)
                await asyncio.sleep(3)

                # Captura de datos en la Ficha Azul
                found_info = False
                for f in page.frames:
                    nombre_el = f.locator("#lblNombreAnimal")
                    if await nombre_el.count() > 0:
                        row["RESULTADO_RPA"] = "✅ REGISTRADO"
                        row["NOMBRE_WEB"] = await nombre_el.inner_text()
                        # Botón "Nueva Consulta" para resetear
                        await f.locator("input[value*='Nueva'], .btn-primary").first.click()
                        found_info = True
                        break
                
                if not found_info:
                    row["RESULTADO_RPA"] = "⚠️ EN TABLA (FALTA DETALLE)"

            except Exception:
                row["RESULTADO_RPA"] = "❌ ERROR EN FLUJO"
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="domcontentloaded")
            
            results.append(row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        status_text.success("¡Auditoría completada!")
        return pd.DataFrame(results)

# --- INTERFAZ ---
file = st.file_uploader("📂 Sube tu Excel", type=["xlsx"])
if file:
    df_input = robust_read_excel(file)
    st.write(f"Registros cargados: {len(df_input)}")
    cant = st.number_input("Cantidad a procesar", 1, len(df_input), 5)
    
    if st.button("🚀 EMPEZAR AUDITORÍA LOCAL"):
        res = asyncio.run(run_local_audit(df_input, cant))
        st.dataframe(res)
        
        # Descarga de resultados
        output = io.BytesIO()
        with pd.ExcelWriter(output) as writer: res.to_excel(writer, index=False)
        st.download_button("📥 Descargar Resultados", output.getvalue(), "Resultados_Asocebu.xlsx")