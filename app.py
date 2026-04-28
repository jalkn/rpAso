import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io
import subprocess
import os

# --- INSTALACIÓN FORZADA (Solo se ejecuta una vez al desplegar) ---
@st.cache_resource
def install_browser():
    try:
        # Instalamos playwright y el navegador chromium de forma silenciosa
        subprocess.run(["pip", "install", "playwright"], check=True)
        subprocess.run(["playwright", "install", "chromium"], check=True)
        return True
    except Exception as e:
        st.error(f"Error de instalación: {e}")
        return False

st.set_page_config(page_title="Zenergy Sniper Cloud", layout="wide")
st.title("🐄 Auditoría Asocebu: Versión Híbrida")

# --- MOTOR DE BÚSQUEDA ---
async def run_audit(df, num_rows):
    results = []
    progress_bar = st.progress(0)
    
    async with async_playwright() as p:
        # Argumentos de bajo consumo de memoria
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-dev-shm-usage", "--single-process"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # Timeout generoso para la red de la nube
            await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", 
                            wait_until="domcontentloaded", 
                            timeout=120000)
            
            df_proc = df.head(num_rows).copy()
            for index, row in df_proc.iterrows():
                animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
                
                # Inyección JS para bypass de frames
                injection_js = f"""
                (function() {{
                    function find(root, val) {{
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
                            try {{ if (find(f.contentDocument || f.contentWindow.document, val)) return true; }} catch(e) {{}}
                        }}
                        return false;
                    }}
                    return find(document, '{animal_id}');
                }})();
                """
                await page.evaluate(injection_js)
                await asyncio.sleep(10) # Tiempo vital para el servidor de Asocebu

                row["RESULTADO_RPA"] = "✅ PROCESADO"
                results.append(row)
                progress_bar.progress((index + 1) / len(df_proc))

        except Exception as e:
            st.error(f"Error en ejecución: {e}")
        finally:
            await browser.close()
        return pd.DataFrame(results)

# --- UI ---
if install_browser():
    file = st.file_uploader("Sube el archivo Excel", type=["xlsx"])
    if file:
        df = pd.read_excel(file)
        df.columns = [str(c).upper().strip() for c in df.columns]
        cant = st.number_input("Cantidad", 1, len(df), 5)
        
        if st.button("🚀 INICIAR"):
            with st.spinner("Procesando..."):
                res = asyncio.run(run_audit(df, cant))
                st.dataframe(res)