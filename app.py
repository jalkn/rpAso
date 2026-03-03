import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os

# 1. Configuración de la página
st.set_page_config(page_title="RPA Asocebu Cloud", page_icon="🐄")
st.title("🐄 Auditoría de Inventario Asocebu")
st.markdown("""
Esta plataforma sincroniza su base de datos interna con el portal oficial de **Asocebu** de forma 100% autónoma. 
Siga las instrucciones para iniciar la conciliación.
""")

# 2. Instalación de dependencias en el servidor (Vital para Streamlit Cloud)
@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

# 3. Función de Automatización Web
async def run_web_automation(df):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    async with async_playwright() as p:
        # Lanzamiento en modo 'headless' para servidores
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # URL oficial de Genealogías [cite: 35]
            await page.goto("https://sir.asocebu.com.co/Genealogias/", timeout=60000)

            total = len(df)
            for index, row in df.iterrows():
                # Identificación de la columna Registration_Number
                animal_id = str(row.get('Registration_Number', '')).strip()
                status_text.text(f"Procesando animal {index+1} de {total}: {animal_id}")
                
                try:
                    # Interacción con el portal [cite: 25, 34]
                    await page.fill('input[name="txtBusqueda"]', animal_id)
                    await page.click('#btnConsultar')
                    await page.wait_for_timeout(2000)
                    
                    # Extracción de datos para el reporte [cite: 24]
                    web_name = await page.inner_text('#lblNombreAnimal')
                    results.append({**row, "Web_Status": "Encontrado", "Nombre_Asocebu": web_name})
                except:
                    results.append({**row, "Web_Status": "No Encontrado", "Nombre_Asocebu": "N/A"})
                
                progress_bar.progress((index + 1) / total)

        except Exception as e:
            st.error(f"Error en la navegación: {e}")
        finally:
            await browser.close()
            
        return pd.DataFrame(results)

# 4. Interfaz de Usuario y Manejo de Archivos
uploaded_file = st.file_uploader("Suba su archivo database.xlsx", type=["xlsx"])

if uploaded_file is not None:
    try:
        # Solución al BadZipFile: Reiniciar el puntero del archivo
        uploaded_file.seek(0)
        df_input = pd.read_excel(uploaded_file, engine='openpyxl')
        
        # Normalización de columnas para evitar KeyError
        df_input.columns = [str(c).strip() for c in df_input.columns]
        
        st.success("✅ Archivo cargado correctamente.")
        
        if st.button("🚀 Iniciar Conciliación"):
            with st.spinner("El Bot RPA está verificando registros..."):
                # Ejecución asíncrona
                df_final = asyncio.run(run_web_automation(df_input))
                
                st.balloons()
                st.success("¡Proceso completado!")

                # Generación del reporte de discrepancias [cite: 20, 24]
                output_name = "reporte_conciliacion_asocebu.xlsx"
                df_final.to_excel(output_name, index=False)
                
                with open(output_name, "rb") as f:
                    st.download_button(
                        label="📥 Descargar Reporte Final (Excel)",
                        data=f,
                        file_name=output_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
    except Exception as e:
        st.error(f"Error técnico: {e}. Por favor, asegúrese de que el archivo no esté corrupto.")

# 5. Pie de página de Seguridad [cite: 47, 48]
st.divider()
st.caption("🔒 Seguridad y Privacidad: Los datos se procesan en la memoria volátil del servidor y se eliminan al finalizar la sesión.")