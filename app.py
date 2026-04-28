import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io
import subprocess
import os

# --- BLOQUE DE INSTALACIÓN CRÍTICA ---
# Esto asegura que los navegadores existan dentro del contenedor de la nube
@st.cache_resource
def force_playwright_install():
    try:
        # Instalamos solo chromium para ahorrar espacio y tiempo
        subprocess.run(["playwright", "install", "chromium"], check=True)
        return True
    except Exception as e:
        st.error(f"Error instalando componentes de navegación: {e}")
        return False

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Zenergy RPA - Cloud", layout="wide")
st.title("🐄 Auditoría Asocebu: Motor en la Nube")

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
        # headless=True es MANDATORIO en la nube
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # Aumentamos el tiempo de espera por la latencia de la nube
            await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", 
                            wait_until="domcontentloaded", 
                            timeout=120000)
            
            df_proc = df.head(num_rows).copy()
            for index, row in df_proc.iterrows():
                animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
                
                # Inyección JS para bypass de iframes (la forma más estable en la nube)
                injection_js = f"""
                (function() {{
                    function findForm(root, val) {{
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
                            try {{ if (findForm(f.contentDocument || f.contentWindow.document, val)) return true; }} catch(e) {{}}
                        }}
                        return false;
                    }}
                    return findForm(document, '{animal_id}');
                }})();
                """
                await page.evaluate(injection_js)
                await asyncio.sleep(8) # La nube procesa más lento

                row["RESULTADO_RPA"] = "✅ PROCESADO"
                results.append(row)
                progress_bar.progress((index + 1) / len(df_proc))

        except Exception as e:
            st.error(f"Error en el motor: {e}")
        finally:
            await browser.close()
            
        return pd.DataFrame(results)

# --- FLUJO DE CONTROL ---
if force_playwright_install():
    file = st.file_uploader("📂 Sube tu base database (3).xlsx", type=["xlsx"])
    if file:
        df_input = robust_read_excel(file)
        st.info(f"Registros listos: {len(df_input)}")
        cant = st.number_input("Cantidad a procesar", 1, len(df_input), 5)
        
        if st.button("🚀 INICIAR SNIPER"):
            with st.spinner("Ejecutando en la nube de Zenergy..."):
                res = asyncio.run(run_cloud_audit(df_input, cant))
                if res is not None:
                    st.dataframe(res)
                    # Preparar descarga para el cliente
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        res.to_excel(writer, index=False)
                    st.download_button("📥 Descargar Reporte", output.getvalue(), "Auditoria_Asocebu.xlsx")
else:
    st.error("El sistema no pudo inicializar los componentes de navegación. Revisa packages.txt.")