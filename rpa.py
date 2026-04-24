import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io

st.set_page_config(page_title="RPA Asocebu - Llave Maestra", layout="wide")
st.title("🐄 Auditoría Asocebu: Inyección y Flujo Circular")

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
    
    async with async_playwright() as p:
        # Abrimos navegador visible. slow_mo de 1 segundo para estabilidad.
        browser = await p.chromium.launch(headless=False, slow_mo=1000) 
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="load", timeout=90000)

        df_proc = df.head(num_rows).copy()
        for index, row in df_proc.iterrows():
            animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
            status.info(f"Procesando registro {index+1}/{num_rows}: **{animal_id}**")
            
            try:
                # 1. INYECCIÓN RECURSIVA: Busca el campo en todos los iframes y lo llena
                injection_js = f"""
                (function() {{
                    function fillDeep(root, val) {{
                        // Buscar select y ponerlo en 'Registro'
                        let sel = root.querySelector('select');
                        if (sel) {{ sel.value = '1'; sel.dispatchEvent(new Event('change', {{bubbles:true}})); }}
                        
                        // Buscar input de texto
                        let inp = root.querySelector('input[type="text"]');
                        if (inp) {{
                            inp.focus();
                            inp.value = val;
                            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            return true;
                        }}
                        // Buscar en iframes hijos
                        let frames = root.querySelectorAll('iframe');
                        for (let f of frames) {{
                            try {{
                                if (fillDeep(f.contentDocument || f.contentWindow.document, val)) return true;
                            }} catch(e) {{}}
                        }}
                        return false;
                    }}
                    return fillDeep(document, '{animal_id}');
                }})();
                """
                await page.evaluate(injection_js)
                await asyncio.sleep(1)

                # 2. CLIC EN CONSULTAR (Lupa)
                # Buscamos el botón en todos los frames posibles
                btn_clicked = False
                for f in page.frames:
                    btn = f.locator("input[src*='lupa'], input[type='image']").first
                    if await btn.count() > 0:
                        await btn.click()
                        btn_clicked = True
                        break
                
                # 3. ENTRAR A LA FICHA (Lupa de la tabla)
                await asyncio.sleep(2)
                for f in page.frames:
                    detalle = f.locator("input[src*='lupa']").nth(1)
                    if await detalle.count() > 0:
                        await detalle.click()
                        break

                # 4. CAPTURA DE DATOS
                await asyncio.sleep(2)
                found_data = False
                for f in page.frames:
                    nombre_lbl = f.locator("#lblNombreAnimal")
                    if await nombre_lbl.count() > 0:
                        row["RESULTADO_RPA"] = "✅ EXITOSO"
                        row["NOMBRE_WEB"] = await nombre_lbl.inner_text()
                        row["PROPIETARIO"] = await f.locator("#lblPropietarioActual").inner_text()
                        # CLIC EN "REALIZAR NUEVA CONSULTA" para cerrar el ciclo
                        await f.locator("input[value*='Nueva'], .btn-primary").first.click()
                        found_data = True
                        break
                
                if not found_data:
                    row["RESULTADO_RPA"] = "⚠️ NO SE ENCONTRÓ FICHA"

            except Exception as e:
                row["RESULTADO_RPA"] = f"❌ ERROR"
                # Si se pierde, refrescamos la página inicial
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="load")
            
            results.append(row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        status.success("✅ Proceso terminado")
        return pd.DataFrame(results)

# --- INTERFAZ ---
file = st.file_uploader("Subir base de datos (Excel)", type=["xlsx"])
if file:
    df_clean = robust_read_excel(file)
    st.write(f"Registros listos: {len(df_clean)}")
    cant = st.number_input("¿Cuántos registros validar?", 1, len(df_clean), 5)
    
    if st.button("🚀 INICIAR AUDITORÍA"):
        res = asyncio.run(run_local_audit(df_clean, cant))
        st.dataframe(res)
        
        # Descarga
        output = io.BytesIO()
        with pd.ExcelWriter(output) as writer: res.to_excel(writer, index=False)
        st.download_button("📥 Descargar Resultados", output.getvalue(), "Auditoria_Asocebu.xlsx")