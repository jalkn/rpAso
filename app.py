import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os

st.set_page_config(page_title="RPA Asocebu Cloud", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría de Inventario Ganadería")

with st.sidebar:
    st.header("Configuración de Acceso")
    user_select = st.selectbox("Seleccione Usuario Asocebu:", ["1307", "2306"])
    secret_key = f"USER_{user_select}_PASS"
    pass_key = st.secrets.get(secret_key, "")
    
    if pass_key:
        st.success(f"🔐 Clave {user_select} cargada.")
    else:
        pass_key = st.text_input("Ingresar contraseña manualmente:", type="password")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    dfs = []
    for sheet in xl.sheet_names:
        df_sheet = pd.read_excel(file, sheet_name=sheet)
        # Normalización total de columnas: Mayúsculas, sin espacios, sin tildes
        df_sheet.columns = [str(c).strip().upper().replace('°', '').replace('Ú', 'U').replace('Ó', 'O') for c in df_sheet.columns]
        df_sheet = df_sheet.dropna(how='all')
        df_sheet['POTRERO_ORIGEN'] = sheet 
        dfs.append(df_sheet)
    return pd.concat(dfs, ignore_index=True)

async def run_web_automation(df, user_code):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Identificar la columna de identificación automáticamente
    col_id = None
    posibles_nombres = ['N ANIMAL', 'NUMERO ANIMAL', 'REGISTRO', 'IDENTIFICACION', 'N ANIMAL', 'REGISTRATION_NUMBER']
    
    for col in df.columns:
        if col in posibles_nombres:
            col_id = col
            break
    
    if not col_id:
        st.error("❌ No se encontró la columna 'N° ANIMAL'. Columnas detectadas: " + str(list(df.columns)))
        return pd.DataFrame()

    st.info(f"🔍 Usando la columna: **{col_id}** para la búsqueda.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0")
        page = await context.new_page()
        
        await page.goto("https://sir.asocebu.com.co/Genealogias/", timeout=60000)

        # Para pruebas, limitamos a los primeros registros si es muy grande, 
        # pero aquí procesaremos todo. 
        total = len(df)
        for index, row in df.iterrows():
            val_raw = str(row[col_id]).strip()
            # Limpiar el valor si viene como "123.0"
            animal_id = val_raw.replace('.0', '')
            
            if not animal_id or animal_id.lower() in ['nan', 'none', 'total', '0']:
                continue

            status_text.text(f"Auditando: {animal_id} ({index+1}/{total})")
            
            # Crear la fila de resultado base
            res_row = row.to_dict()
            res_row["CUENTA_AUDITORA"] = user_code
            
            try:
                await page.fill('input[name="txtBusqueda"]', animal_id)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1500)
                
                # Intentar capturar el nombre
                nombre_web = await page.inner_text('#lblNombreAnimal')
                res_row["ESTADO_RPA"] = "ENCONTRADO"
                res_row["NOMBRE_ASOCEBU"] = nombre_web
            except:
                res_row["ESTADO_RPA"] = "NO ENCONTRADO / ERROR"
                res_row["NOMBRE_ASOCEBU"] = "N/A"
            
            results.append(res_row)
            progress_bar.progress((index + 1) / total)
            
            # Para no saturar la memoria con 163k registros en una sola lista de Python,
            # podrías limitar el proceso o ir guardando.
            if index > 500: # Límite de seguridad para esta prueba
                st.warning("⚠️ Proceso limitado a los primeros 500 por estabilidad. Para procesar 163k se requiere ejecución por lotes.")
                break

        await browser.close()
        return pd.DataFrame(results)

# Interfaz
uploaded_file = st.file_uploader("Suba el archivo Excel", type=["xlsx"])

if uploaded_file:
    uploaded_file.seek(0)
    df_consolidado = procesar_archivo_cliente(uploaded_file)
    st.info(f"📋 Filas detectadas: {len(df_consolidado)}")

    if st.button("🚀 Iniciar Auditoría"):
        if not df_consolidado.empty:
            df_final = asyncio.run(run_web_automation(df_consolidado, user_select))
            
            if not df_final.empty:
                st.success("¡Auditoría finalizada!")
                st.dataframe(df_final.head(100)) # Mostrar solo los primeros 100
                
                output = "REPORTE_FINAL_ASOCEBU.xlsx"
                df_final.to_excel(output, index=False)
                with open(output, "rb") as f:
                    st.download_button("📥 Descargar Reporte (Excel)", f, output)
        else:
            st.error("El archivo cargado no tiene datos válidos.")