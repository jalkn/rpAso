import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os
import io

st.set_page_config(page_title="RPA Asocebu Pro", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría de Inventario de Alta Capacidad")

with st.sidebar:
    st.header("Configuración")
    user_select = st.selectbox("Usuario:", ["1307", "2306"])
    limit_rows = st.number_input("Límite de registros a auditar:", min_value=1, value=100, step=50)
    
    st.warning("Nota: Procesar 163k registros tomaría aprox. 40 horas. Se recomienda usar muestras.")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    all_dfs = []
    
    for sheet in xl.sheet_names:
        # Leemos sin procesar para encontrar la tabla real
        df_raw = pd.read_excel(file, sheet_name=sheet, header=None)
        
        # BUSQUEDA DINÁMICA MEJORADA
        header_row = 0
        found = False
        # Escaneamos más filas (50) por si el encabezado es muy largo
        for i, row in df_raw.iterrows():
            if i > 50: break 
            row_str = " ".join([str(val).upper() for val in row.values if pd.notna(val)])
            # Buscamos palabras clave exactas o parciales
            if any(k in row_str for k in ["ANIMAL", "REGISTRO", "IDENTIFICACION", "N°"]):
                header_row = i
                found = True
                break
        
        # Re-leemos con la cabecera correcta
        if found:
            df_clean = pd.read_excel(file, sheet_name=sheet, skiprows=header_row)
        else:
            df_clean = df_raw # Fallback si no encuentra nada
            
        # Limpieza profunda de nombres de columnas
        df_clean.columns = [str(c).strip().upper().replace('°', '').replace(' ', '_').replace('.', '') for c in df_clean.columns]
        # Eliminar columnas sin nombre (Unnamed)
        df_clean = df_clean.loc[:, ~df_clean.columns.str.contains('UNNAMED')]
        df_clean = df_clean.dropna(how='all', axis=0)
        
        if not df_clean.empty:
            df_clean['HOJA_ORIGEN'] = sheet
            all_dfs.append(df_clean)
        
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

async def run_web_automation(df, user_code, max_rows):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Buscamos la columna de ID con más variantes para evitar el error de la captura
    col_id = next((c for c in df.columns if any(p in c for p in ['ANIMAL', 'REGISTRO', 'IDENTI', 'ID', 'NUMERO'])), None)
    
    if not col_id:
        st.error(f"❌ No encontré columna de identificación. Columnas: {list(df.columns)}")
        return pd.DataFrame()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Ir directamente a la herramienta de genealogías
        await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", timeout=60000)

        df_to_process = df.head(max_rows).copy()
        
        for index, row in df_to_process.iterrows():
            animal_id = str(row[col_id]).strip().split('.')[0] # Limpia decimales .0
            
            if not animal_id or animal_id.lower() in ['nan', 'none', 'total', '0', '']:
                continue

            status_text.text(f"🚀 Procesando {index+1}/{len(df_to_process)}: ID {animal_id}")
            
            res_row = row.to_dict()
            try:
                # 1. SOLUCIÓN TI: Seleccionar "Nro. Registro" explícitamente
                await page.select_option('select[id*="ddlTipoBusqueda"]', value="1")
                await page.wait_for_timeout(300)
                
                # 2. Búsqueda
                await page.fill('input[id*="txtBusqueda"]', animal_id)
                await page.keyboard.press("Enter")
                
                # 3. Espera de carga dinámica
                await page.wait_for_timeout(2500)
                
                # 4. Extracción de datos
                nombre_web = await page.inner_text('#lblNombreAnimal')
                res_row.update({"ESTADO": "ENCONTRADO", "NOMBRE_ASOCEBU": nombre_web})
            except:
                res_row.update({"ESTADO": "NO ENCONTRADO", "NOMBRE_ASOCEBU": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_to_process))
            
        await browser.close()
        return pd.DataFrame(results)

# --- UI ---
file = st.file_uploader("Suba el archivo de Inventario", type=["xlsx"])

if file:
    df_consolidado = procesar_archivo_cliente(file)
    
    if not df_consolidado.empty:
        st.info(f"📊 Archivo cargado con {len(df_consolidado)} filas totales.")
        st.dataframe(df_consolidado.head(5))

        if st.button("🚀 Iniciar Auditoría"):
            df_res = asyncio.run(run_web_automation(df_consolidado, user_select, limit_rows))
            
            if not df_res.empty:
                st.success("✅ Auditoría completada")
                st.dataframe(df_res)
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_res.to_excel(writer, index=False)
                st.download_button("📥 Descargar Reporte Final", buffer.getvalue(), 
                                 file_name=f"Resultado_{user_select}.xlsx")
    else:
        st.error("No se detectaron datos válidos en el Excel.")