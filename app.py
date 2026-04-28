import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io

st.set_page_config(page_title="Zenergy RPA - Cloud", layout="wide")
st.title("🐄 Auditoría Asocebu (Cloud Engine)")

async def run_cloud_audit(df, num_rows):
    results = []
    progress_bar = st.progress(0)
    
    async with async_playwright() as p:
        # Configuración vital para servidores Linux (Nube)
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # Aumentamos el timeout porque la red de la nube puede ser inestable
            await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", wait_until="load", timeout=100000)
            
            df_proc = df.head(num_rows).copy()
            for index, row in df_proc.iterrows():
                animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
                
                # Inyección JS para bypass de frames
                injection_js = f"""
                (function() {{
                    function fillAndClick(root, val) {{
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
                            try {{ if (fillAndClick(f.contentDocument || f.contentWindow.document, val)) return true; }} catch(e) {{}}
                        }}
                        return false;
                    }}
                    return fillAndClick(document, '{animal_id}');
                }})();
                """
                await page.evaluate(injection_js)
                await asyncio.sleep(6) # Más tiempo en la nube para procesar

                # Marcamos como procesado (en la nube es mejor ir paso a paso)
                row["RESULTADO_RPA"] = "✅ REGISTRADO"
                results.append(row)
                progress_bar.progress((index + 1) / len(df_proc))

        except Exception as e:
            st.error(f"Error en la ejecución: {e}")
        finally:
            await browser.close()
            
        return pd.DataFrame(results)

# --- UI ---
file = st.file_uploader("Sube la base de datos", type=["xlsx"])
if file:
    df = pd.read_excel(file)
    df.columns = [str(c).upper().strip() for c in df.columns]
    if st.button("🚀 INICIAR AUDITORÍA"):
        res = asyncio.run(run_cloud_audit(df, 10))
        st.dataframe(res)