import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io
import subprocess
import os

# --- INSTALACIÓN FORZADA DE BINARIOS ---
# Usamos una variable de estado para que solo intente instalar una vez por sesión
if 'playwright_ready' not in st.session_state:
    try:
        # Intentamos instalar el navegador solo si no detecta el ejecutable
        subprocess.run(["playwright", "install", "chromium"], check=True)
        st.session_state.playwright_ready = True
    except Exception as e:
        st.error(f"Aviso de sistema (Navegador): {e}")
        st.session_state.playwright_ready = False

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="Zenergy RPA - Cloud", layout="wide")
st.title("🐄 Auditoría Asocebu (Cloud Engine)")

def robust_read_excel(file):
    df = pd.read_excel(file)
    df.columns = [str(c).upper().strip() for c in df.columns]
    for col in df.columns:
        if "REGISTRO" in col:
            df = df.rename(columns={col: "REGISTRO"})
            break
    return df

async def run_cloud_audit(df, num_rows):
    results = []
    progress_bar = st.progress(0)
    
    async with async_playwright() as p:
        # Modo 'headless' estricto para la nube
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # Esperamos que cargue lo básico
            await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", 
                            wait_until="domcontentloaded", 
                            timeout=100000)
            
            df_proc = df.head(num_rows).copy()
            for index, row in df_proc.iterrows():
                animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
                
                # Inyección JS Maestra (Bypass de frames)
                injection_js = f"""
                (function() {{
                    function findAndAction(root, val) {{
                        let sel = root.querySelector('select');
                        if (sel) {{ sel.value = '1'; sel.dispatchEvent(new Event('change', {{bubbles:true}})); }}
                        
                        let inp = root.querySelector('input[type="text"]');
                        if (inp) {{
                            inp.value = val;
                            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            let btn = Array.from(root.querySelectorAll('input')).find(i => i.value && i.value.toUpperCase().includes('CONSULTAR'));
                            if (btn) {{ btn.click(); return true; }}
                        }}
                        let frames = root.querySelectorAll('iframe');
                        for (let f of frames) {{
                            try {{ if (findAndAction(f.contentDocument || f.contentWindow.document, val)) return true; }} catch(e) {{}}
                        }}
                        return false;
                    }}
                    return findAndAction(document, '{animal_id}');
                }})();
                """
                await page.evaluate(injection_js)
                await asyncio.sleep(8) # La nube necesita más tiempo de espera

                # Resultado básico para validar el flujo en la nube
                row["RESULTADO_RPA"] = "✅ PROCESADO"
                results.append(row)
                progress_bar.progress((index + 1) / len(df_proc))

        except Exception as e:
            st.error(f"Error en proceso: {e}")
        finally:
            await browser.close()
            
        return pd.DataFrame(results)

# --- FLUJO DE UI ---
file = st.file_uploader("Sube la base de datos", type=["xlsx"])
if file:
    df_data = robust_read_excel(file)
    cant = st.number_input("Cantidad", 1, len(df_data), 5)
    
    if st.button("🚀 INICIAR SNIPER"):
        if st.session_state.playwright_ready:
            with st.spinner("Procesando en la nube..."):
                res = asyncio.run(run_cloud_audit(df_data, cant))
                st.dataframe(res)
        else:
            st.warning("El navegador no está listo todavía. Por favor, espera un momento y presiona de nuevo.")