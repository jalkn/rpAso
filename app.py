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
        # Limpieza agresiva de columnas
        df_sheet.columns = [str(c).strip().upper() for c in df_sheet.columns]
        df_sheet = df_sheet.dropna(how='all')
        df_sheet['POTRERO_ORIGEN'] = sheet 
        dfs.append(df_sheet)
    return pd.concat(dfs, ignore_index=True)

async def run_web_automation(df, user_code):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0")
        page = await context.new_page()
        
        await page.goto("https://sir.asocebu.com.co/Genealogias/", timeout=60000)

        total = len(df)
        for index, row in df.iterrows():
            # Intentamos encontrar la columna de registro sin importar cómo se llame
            animal_id = ""
            posibles_nombres = ['N° ANIMAL', 'REGISTRATION_NUMBER', 'REGISTRO', 'IDENTIFICACION']
            for col in posibles_nombres:
                if col in df.columns:
                    animal_id = str(row[col]).strip()
                    break
            
            # Si la celda está vacía o es un total, saltar
            if not animal_id or animal_id.lower() in ['nan', 'none', 'total', '0', '0.0']:
                continue

            status_text.text(f"Auditando: {animal_id} ({index+1}/{total})")
            
            try:
                await page.fill('input[name="txtBusqueda"]', animal_id)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2000)
                
                # Intentamos extraer el nombre
                nombre_web = await page.inner_text('#lblNombreAnimal')
                
                # GUARDAR RESULTADO (Aquí estaba el fallo, ahora forzamos el guardado)
                new_row = row.to_dict()
                new_row["ESTADO_RPA"] = "ENCONTRADO"
                new_row["NOMBRE_ASOCEBU"] = nombre_web
                new_row["CUENTA_AUDITORA"] = user_code
                results.append(new_row)
            except:
                new_row = row.to_dict()
                new_row["ESTADO_RPA"] = "NO ENCONTRADO"
                new_row["NOMBRE_ASOCEBU"] = "N/A"
                new_row["CUENTA_AUDITORA"] = user_code
                results.append(new_row)
            
            progress_bar.progress((index + 1) / total)
            
        await browser.close()
        return pd.DataFrame(results)

# Interfaz
uploaded_file = st.file_uploader("Suba el archivo Excel", type=["xlsx"])

if uploaded_file:
    uploaded_file.seek(0)
    df_consolidado = procesar_archivo_cliente(uploaded_file)
    st.info(f"📋 Se procesarán {len(df_consolidado)} filas detectadas.")

    if st.button("🚀 Iniciar Auditoría"):
        df_final = asyncio.run(run_web_automation(df_consolidado, user_select))
        
        if not df_final.empty:
            st.success("¡Auditoría finalizada con éxito!")
            st.dataframe(df_final)
            
            output = "REPORTE_FINAL_ASOCEBU.xlsx"
            df_final.to_excel(output, index=False)
            with open(output, "rb") as f:
                st.download_button("📥 Descargar Reporte (Excel)", f, output)
        else:
            st.error("❌ El reporte salió vacío. Verifique que la columna se llame 'N° ANIMAL'.")