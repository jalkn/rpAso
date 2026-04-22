import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os
import io

# 1. CONFIGURACIÓN DE PÁGINA Y UI
st.set_page_config(page_title="RPA Asocebu Pro", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría Integral: Registro, Grupo, Sexo y Color")

with st.sidebar:
    st.header("Configuración de Auditoría")
    user_select = st.selectbox("Seleccione Usuario:", ["1307", "2306"])
    limit_rows = st.number_input("Cantidad de registros a validar:", min_value=1, value=100, step=50)
    st.info("El bot comparará 'REGISTRO' y 'GRUPO' contra la ficha técnica oficial de Asocebu.")
    st.warning("Nota: Procesar volúmenes masivos (163k) requiere ejecución por lotes.")

# 2. INSTALACIÓN DE DEPENDENCIAS
@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

# 3. PROCESAMIENTO DE ARCHIVOS EXCEL (MATCH CON TUS PANTALLAZOS)
def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    all_dfs = []
    for sheet in xl.sheet_names:
        df_raw = pd.read_excel(file, sheet_name=sheet, header=None)
        header_row = 0
        found = False
        # Escaneo de filas para saltar encabezados informativos (CENTRO, FECHA, RESPONSABLE)
        for i, row in df_raw.iterrows():
            if i > 50: break 
            row_str = " ".join([str(val).upper() for val in row.values if pd.notna(val)])
            # Buscamos las columnas exactas de tus fotos
            if "N° ANIMAL" in row_str and "REGISTRO" in row_str:
                header_row = i
                found = True
                break
        
        if found:
            df_clean = pd.read_excel(file, sheet_name=sheet, skiprows=header_row)
            # Normalizamos nombres de columnas para evitar errores de espacios o caracteres
            df_clean.columns = [str(c).strip().upper().replace('N°', 'N_').replace(' ', '_').replace('.', '') for c in df_clean.columns]
            df_clean = df_clean.loc[:, ~df_clean.columns.str.contains('UNNAMED')]
            df_clean = df_clean.dropna(subset=['REGISTRO'], how='any')
            
            if not df_clean.empty:
                df_clean['HOJA_ORIGEN'] = sheet
                all_dfs.append(df_clean)
            
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

# 4. MOTOR DE AUTOMATIZACIÓN (WEB SCRAPING)
async def run_web_automation(df, max_rows):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Mapeo según tus requerimientos: REGISTRO es el ID, GRUPO es la RAZA
    col_id = "REGISTRO" 
    col_grupo = "GRUPO" 
    col_sexo = next((c for c in df.columns if 'SEXO' in c), None)
    col_color = next((c for c in df.columns if any(p in c for p in ['COLOR', 'PELAJE'])), None)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Acceso directo al portal de Genealogías
        await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", timeout=60000)

        df_proc = df.head(max_rows).copy()
        for index, row in df_proc.iterrows():
            # Limpiamos el dato de Registro
            animal_id = str(row[col_id]).strip().split('.')[0]
            if not animal_id or animal_id.lower() in ['nan', 'none', '']: continue

            status_text.text(f"🔍 Validando {index+1}/{len(df_proc)}: {animal_id} (Sede: {row['HOJA_ORIGEN']})")
            res_row = row.to_dict()

            try:
                # Búsqueda por Registro
                await page.select_option('select[id*="ddlTipoBusqueda"]', value="1")
                await page.fill('input[id*="txtBusqueda"]', animal_id)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2500)
                
                # Extracción de la ficha técnica oficial
                raza_web = (await page.inner_text('#lblRaza')).upper()
                sexo_web = (await page.inner_text('#lblSexo')).upper()
                color_web = (await page.inner_text('#lblColor')).upper()
                nombre_web = await page.inner_text('#lblNombreAnimal')

                # VALIDACIÓN CUÁDRUPLE (Match de Integridad)
                grupo_ex = str(row.get(col_grupo, '')).upper()
                match_raza = raza_web in grupo_ex or grupo_ex in raza_web
                
                # Validación de Sexo (Compara la inicial M/F)
                match_sexo = True if not col_sexo else (sexo_web[0] == str(row[col_sexo])[0].upper())
                
                # Validación de Color
                match_color = True if not col_color else (color_web in str(row[col_color]).upper())

                if match_raza and match_sexo and match_color:
                    res_row.update({"RESULTADO_RPA": "✅ COINCIDE", "INFO_WEB": f"{raza_web} | {sexo_web} | {color_web}"})
                else:
                    dif = []
                    if not match_raza: dif.append("Grupo/Raza")
                    if not match_sexo: dif.append("Sexo")
                    if not match_color: dif.append("Color")
                    res_row.update({"RESULTADO_RPA": "⚠️ DISCREPANCIA", "INFO_WEB": f"Difiere en: {', '.join(dif)}"})
                
                res_row.update({"NOMBRE_OFICIAL": nombre_web})
            except:
                res_row.update({"RESULTADO_RPA": "❌ NO ENCONTRADO", "INFO_WEB": "N/A", "NOMBRE_OFICIAL": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# 5. INTERFAZ DE CARGA Y DESCARGA
file = st.file_uploader("Suba el archivo de Inventario", type=["xlsx"])
if file:
    df_c = procesar_archivo_cliente(file)
    if not df_c.empty:
        st.write(f"### Se detectaron {len(df_c)} registros en el archivo consolidado.")
        st.dataframe(df_c.head(10))
        if st.button("🚀 Iniciar Auditoría de Base de Datos"):
            df_final = asyncio.run(run_web_automation(df_c, limit_rows))
            st.success("✅ Auditoría finalizada.")
            st.dataframe(df_final)
            # Preparación del archivo de salida
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte de Auditoría", buffer.getvalue(), file_name="Auditoria_Argos_Final.xlsx")

