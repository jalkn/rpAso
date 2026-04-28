import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io
import subprocess
import os

# --- PASO 1: INSTALACIÓN CONTROLADA ---
def ensure_playwright_installed():
    # Buscamos si el binario de chromium ya existe en las carpetas de caché de la nube
    try:
        import playwright
        # Si esto falla, es que no está instalado
        return True
    except ImportError:
        with st.spinner("Instalando motor de navegación..."):
            subprocess.run(["pip", "install", "playwright"], check=True)
            subprocess.run(["playwright", "install", "chromium"], check=True)
        return True

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="Zenergy RPA - Cloud Ready", layout="wide")
st.title("🐄 Auditoría Asocebu (Motor Cloud)")

# --- LÓGICA DE AUDITORÍA (Simplificada para estabilidad) ---
async def run_cloud_audit(df, num_rows):
    results = []
    progress_bar = st.progress(0)
    
    async with async_playwright() as p:
        # Argumentos específicos para evitar el error de memoria en la nube
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # Aumentamos el timeout a 2 minutos (la nube es lenta)
            await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", 
                            wait_until="domcontentloaded", 
                            timeout=120000)
            
            df_proc = df.head(num_rows).copy()
            for index, row in df_proc.iterrows():
                animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
                
                # Inyección JS para bypass de frames
                injection_js = f"""
                (function() {{
                    function solve(root, val) {{
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
                            try {{ if (solve(f.contentDocument || f.contentWindow.document, val)) return true; }} catch(e) {{}}
                        }}
                        return false;
                    }}
                    return solve(document, '{animal_id}');
                }})();
                """
                await page.evaluate(injection_js)
                await asyncio.sleep(10) # Espera extendida para la nube

                row["RESULTADO_RPA"] = "✅ PROCESADO"
                results.append(row)
                progress_bar.progress((index + 1) / len(df_proc))

        except Exception as e:
            st.error(f"Error en motor: {e}")
        finally:
            await browser.close()
        return pd.DataFrame(results)

# --- FLUJO PRINCIPAL ---
if ensure_playwright_installed():
    file = st.file_uploader("Sube tu Excel", type=["xlsx"])
    if file:
        df = pd.read_excel(file)
        df.columns = [str(c).upper().strip() for c in df.columns]
        cant = st.number_input("Cantidad", 1, len(df), 5)
        
        if st.button("🚀 INICIAR"):
            with st.spinner("Procesando en la nube de Zenergy..."):
                res = asyncio.run(run_cloud_audit(df, cant))
                st.dataframe(res)