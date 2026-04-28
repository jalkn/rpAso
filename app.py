import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io
import subprocess
import os

# --- INSTALACIÓN DE BINARIOS ---
# En la nube, necesitamos asegurar que Playwright tenga su navegador instalado
@st.cache_resource
def install_playwright_binaries():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
        return True
    except Exception as e:
        st.error(f"Error instalando navegadores: {e}")
        return False

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="Zenergy RPA - Cloud", layout="wide")
st.title("🐄 Auditoría Asocebu (Cloud Engine)")
st.markdown("---")

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
    status_text = st.empty()
    
    async with async_playwright() as p:
        # Argumentos necesarios para ejecutar en contenedores Linux (Streamlit Cloud)
        browser = await p.chromium.launch(
            headless=True, 
            args=[
                "--no-sandbox", 
                "--disable-gpu", 
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox"
            ]
        )
        
        # Simulamos un usuario real para evitar bloqueos por headers
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            status_text.info("Conectando con el portal...")
            # En la nube usamos 'domcontentloaded' para mayor velocidad
            await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", 
                            wait_until="domcontentloaded", 
                            timeout=120000)
            
            df_proc = df.head(num_rows).copy()
            for index, row in df_proc.iterrows():
                animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
                status_text.info(f"Procesando {index+1}/{num_rows}: Registro {animal_id}")

                # Inyección JS para manejo de frames recursivos
                injection_js = f"""
                (function() {{
                    function fillSearch(root, val) {{
                        let sel = root.querySelector('select');
                        if (sel) {{ sel.value = '1'; sel.dispatchEvent(new Event('change', {{bubbles:true}})); }}
                        
                        let inp = root.querySelector('input[type="text"]');
                        if (inp) {{
                            inp.value = val;
                            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            let btn = Array.from(root.querySelectorAll('input')).find(i => i.value && i.value.toUpperCase().includes('CONSULTAR'));
                            if (btn) {{ btn.click(); return "CLICKED"; }}
                        }}
                        let frames = root.querySelectorAll('iframe');
                        for (let f of frames) {{
                            try {{ if (fillSearch(f.contentDocument || f.contentWindow.document, val)) return "CLICKED"; }} catch(e) {{}}
                        }}
                        return null;
                    }}
                    return fillSearch(document, '{animal_id}');
                }})();
                """
                await page.evaluate(injection_js)
                await asyncio.sleep(6) # Tiempo de procesamiento del servidor

                # Verificación de resultados y clic en Detalle (segunda lupa)
                detalle_js = """
                (function() {
                    function clickLupa(root) {
                        let lupas = root.querySelectorAll('input[src*="lupa"]');
                        if (lupas.length > 1) {
                            lupas[1].click();
                            return true;
                        }
                        let frames = root.querySelectorAll('iframe');
                        for (let f of frames) {
                            try { if (clickLupa(f.contentDocument)) return true; } catch(e) {}
                        }
                        return false;
                    }
                    return clickLupa(document);
                })();
                """
                await page.evaluate(detalle_js)
                await asyncio.sleep(4)

                # Captura de datos final
                found = False
                for f in page.frames:
                    nombre_animal = f.locator("#lblNombreAnimal")
                    if await nombre_animal.count() > 0:
                        row["RESULTADO_RPA"] = "✅ REGISTRADO"
                        row["NOMBRE_WEB"] = await nombre_animal.inner_text()
                        await f.locator("input[value*='Nueva']").first.click()
                        found = True
                        break
                
                if not found:
                    row["RESULTADO_RPA"] = "⚠️ RESULTADO NO ENCONTRADO"
                
                results.append(row)
                progress_bar.progress((index + 1) / len(df_proc))

        except Exception as e:
            st.error(f"Error de ejecución: {e}")
        finally:
            await browser.close()
            
        return pd.DataFrame(results)

# --- FLUJO DE UI ---
if install_playwright_binaries():
    file = st.file_uploader("📂 Sube tu base database (3).xlsx", type=["xlsx"])
    if file:
        df_input = robust_read_excel(file)
        st.success(f"Registros listos: {len(df_input)}")
        cant = st.number_input("Cantidad a procesar", 1, len(df_input), 10)
        
        if st.button("🚀 INICIAR SNIPER CLOUD"):
            res = asyncio.run(run_cloud_audit(df_input, cant))
            if res is not None:
                st.dataframe(res)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    res.to_excel(writer, index=False)
                st.download_button("📥 Descargar Resultados", output.getvalue(), "Auditoria_Asocebu.xlsx")
