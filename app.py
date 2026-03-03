import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os

# 1. Configuración de la página
st.set_page_config(page_title="RPA Asocebu Cloud", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría de Inventario Ganadería")

# 2. Configuración de Cuenta y Seguridad (Uso de Secrets)
with st.sidebar:
    st.header("Configuración de Acceso")
    user_select = st.selectbox("Seleccione Usuario Asocebu:", ["1307", "2306"])
    
    # Buscamos la clave en los Secrets de Streamlit
    # El nombre coincide con lo que configuraste: USER_1307_PASS o USER_2306_PASS
    secret_key = f"USER_{user_select}_PASS"
    pass_key = st.secrets.get(secret_key, "")
    
    if pass_key:
        st.success(f"🔐 Contraseña de {user_select} cargada correctamente.")
    else:
        st.warning(f"⚠️ No se encontró '{secret_key}' en los Secrets de Streamlit.")
        pass_key = st.text_input("Ingresar contraseña manualmente:", type="password")

@st.cache_resource
def install_playwright():
    # Instalación de Chromium en el servidor de Streamlit
    os.system("playwright install chromium")

install_playwright()

# 3. Lógica para unir todas las pestañas de Excel (Potreros)
def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    dfs = []
    for sheet in xl.sheet_names:
        df_sheet = pd.read_excel(file, sheet_name=sheet)
        # Limpiamos nombres de columnas
        df_sheet.columns = [str(c).strip() for c in df_sheet.columns]
        # Filtramos filas vacías
        df_sheet = df_sheet.dropna(how='all')
        # Guardamos el nombre del potrero (pestaña)
        df_sheet['Potrero_Original'] = sheet 
        dfs.append(df_sheet)
    return pd.concat(dfs, ignore_index=True)

# 4. Automatización de Consulta (Auditoría)
async def run_web_automation(df, user_code):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        
        # URL de consulta pública para Auditoría de Inventario
        await page.goto("https://sir.asocebu.com.co/Genealogias/", timeout=60000)

        total = len(df)
        for index, row in df.iterrows():
            # Buscamos el ID del animal (N° ANIMAL o Registration_Number)
            animal_id = str(row.get('N° ANIMAL', row.get('Registration_Number', ''))).strip()
            
            # Saltamos basura o filas de totales
            if not animal_id or animal_id.lower() in ['nan', 'none', 'total']:
                continue

            status_text.text(f"Consultando animal {index+1}/{total}: {animal_id}")
            try:
                await page.fill('input[name="txtBusqueda"]', animal_id)
                await page.press('input[name="txtBusqueda"]', "Enter")
                await page.wait_for_timeout(1800) # Tiempo para que Angular responda
                
                nombre_web = await page.inner_text('#lblNombreAnimal')
                results.append({**row, "Usuario_RPA": user_code, "Estado": "OK", "Nombre_Asocebu": nombre_web})
            except:
                results.append({**row, "Usuario_RPA": user_code, "Estado": "No Encontrado", "Nombre_Asocebu": "N/A"})
            
            progress_bar.progress((index + 1) / total)
            
        await browser.close()
        return pd.DataFrame(results)

# 5. Interfaz de Usuario (Carga de Archivos)
uploaded_file = st.file_uploader("Suba el archivo Excel (database.xlsx)", type=["xlsx"])

if uploaded_file:
    if uploaded_file.size == 0:
        st.error("⚠️ El archivo está vacío (0.0B). Por favor suba un archivo con datos.")
    else:
        uploaded_file.seek(0)
        try:
            df_consolidado = procesar_archivo_cliente(uploaded_file)
            st.success(f"✅ Se detectaron {len(df_consolidado)} registros en todos los potreros.")
            st.dataframe(df_consolidado.head(10)) # Vista previa

            if st.button("🚀 Iniciar Conciliación"):
                with st.spinner(f"El Bot está auditando con la cuenta {user_select}..."):
                    # Ejecución del bot
                    df_final = asyncio.run(run_web_automation(df_consolidado, user_select))
                    
                    st.balloons()
                    st.success("¡Auditoría completada!")
                    st.dataframe(df_final)
                    
                    # Generación del archivo de salida
                    output_file = "reporte_auditoria_asocebu.xlsx"
                    df_final.to_excel(output_file, index=False)
                    
                    with open(output_file, "rb") as f:
                        st.download_button(
                            label="📥 Descargar Reporte Final (Excel)",
                            data=f,
                            file_name=output_file,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
        except Exception as e:
            st.error(f"Error al procesar el Excel: {e}")

# Pie de página
st.divider()
st.caption("🔒 Los datos se procesan de forma segura y no se almacenan permanentemente en el servidor.")