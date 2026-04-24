import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io
import os

# Configuración de interfaz profesional
st.set_page_config(page_title="RPA Asocebu - Desarrollo Consolidado", layout="wide")
st.title("🐄 Auditoría de Registros: Genealogía Asocebu")

# Función de lectura robusta identificada en chats previos
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

async def run_audit_flow(df, num_rows):
    results = []
    progress_bar = st.progress(0)
    status = st.empty()
    
    async with async_playwright() as p:
        # Configuración para Streamlit Cloud (Headless obligatorio)
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        ) 
        # Emulación de agente real para evitar bloqueos de IP/Bot
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # URL del portal de Genealogías
        url_inicio = "https://sir.asocebu.com.co/Genealogias/inicio"
        
        df_proc = df.head(num_rows).copy()
        for index, row in df_proc.iterrows():
            animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
            status.info(f"Procesando registro {index+1}/{num_rows}: **{animal_id}**")
            
            try:
                await page.goto(url_inicio, wait_until="networkidle", timeout=60000)
                
                # Lógica de Inyección y Selección de Frame (desarrollo rpa asocebu)
                # Se busca el selector de 'Registro' (value='1')
                injection_js = f"""
                (function() {{
                    function findAndFill(root, val) {{
                        let sel = root.querySelector('select');
                        if (sel) {{ 
                            sel.value = '1'; 
                            sel.dispatchEvent(new Event('change', {{bubbles:true}})); 
                        }}
                        let inp = root.querySelector('input[type="text"]');
                        if (inp) {{
                            inp.focus();
                            return inp;
                        }}
                        let frames = root.querySelectorAll('iframe');
                        for (let f of frames) {{
                            try {{
                                let found = findAndFill(f.contentDocument || f.contentWindow.document, val);
                                if (found) return found;
                            }} catch(e) {{}}
                        }}
                        return null;
                    }}
                    window._targetInput = findAndFill(document, '{animal_id}');
                }})();
                """
                await page.evaluate(injection_js)
                
                # Emulación de escritura física (tecleo real) para saltar validaciones JS
                await page.keyboard.type(animal_id, delay=100)
                await asyncio.sleep(1)

                # Clic en Consultar (Lupa) - Búsqueda en frames
                clicked = False
                for f in page.frames:
                    lupa = f.locator("input[src*='lupa'], input[type='image']").first
                    if await lupa.count() > 0:
                        await lupa.click()
                        clicked = True
                        break
                
                await asyncio.sleep(2)

                # Extracción de Ficha (rpa asocebu genealogy)
                found_data = False
                for f in page.frames:
                    # Entrar a la lupa del resultado
                    detalle_btn = f.locator("input[src*='lupa']").nth(1) if await f.locator("input[src*='lupa']").count() > 1 else None
                    if detalle_btn and await detalle_btn.count() > 0:
                        await detalle_btn.click()
                        await asyncio.sleep(2)
                        
                        # Captura de campos clave
                        row["RESULTADO_RPA"] = "✅ EXITOSO"
                        row["NOMBRE_WEB"] = await f.locator("#lblNombreAnimal").inner_text() if await f.locator("#lblNombreAnimal").count() > 0 else "N/A"
                        row["RAZA"] = await f.locator("#lblRaza").inner_text() if await f.locator("#lblRaza").count() > 0 else "N/A"
                        row["SEXO"] = await f.locator("#lblSexo").inner_text() if await f.locator("#lblSexo").count() > 0 else "N/A"
                        
                        # Flujo circular: Regresar para nueva consulta
                        nueva_btn = f.locator("input[value*='Nueva'], .btn-primary").first
                        if await nueva_btn.count() > 0: await nueva_btn.click()
                        
                        found_data = True
                        break
                
                if not found_data:
                    row["RESULTADO_RPA"] = "⚠️ NO ENCONTRADO"

            except Exception:
                row["RESULTADO_RPA"] = "❌ ERROR DE CARGA"
            
            results.append(row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        status.success("✅ Auditoría terminada")
        return pd.DataFrame(results)

# --- UI INTERFAZ ---
uploaded_file = st.file_uploader("Cargar Inventario (Excel)", type=["xlsx"])
if uploaded_file:
    df_clean = robust_read_excel(uploaded_file)
    st.info(f"Registros válidos encontrados: {len(df_clean)}")
    
    col1, col2 = st.columns(2)
    with col1:
        cantidad = st.number_input("Registros a procesar", 1, len(df_clean), 10)
    
    if st.button("🚀 Iniciar Proceso Circular"):
        res_df = asyncio.run(run_audit_flow(df_clean, cantidad))
        st.dataframe(res_df)
        
        # Exportación de resultados
        to_download = io.BytesIO()
        with pd.ExcelWriter(to_download) as writer:
            res_df.to_excel(writer, index=False)
        st.download_button("📥 Descargar Reporte Final", to_download.getvalue(), "Auditoria_Final_Asocebu.xlsx")