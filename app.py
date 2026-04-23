import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import os
import io

# 1. CONFIGURACIÓN
st.set_page_config(page_title="RPA Asocebu Pro", page_icon="🐄", layout="wide")
st.title("🐄 Auditoría Integral: Registro, Grupo, Sexo y Color")

@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

install_playwright()

# 2. PROCESAMIENTO DE EXCEL
def procesar_archivo_cliente(file):
    xl = pd.ExcelFile(file, engine='openpyxl')
    all_dfs = []
    for sheet in xl.sheet_names:
        df_raw = pd.read_excel(file, sheet_name=sheet, header=None)
        header_row = 0
        found = False
        for i, row in df_raw.iterrows():
            if i > 50: break 
            row_str = " ".join([str(val).upper() for val in row.values if pd.notna(val)])
            if "N° ANIMAL" in row_str and "REGISTRO" in row_str:
                header_row = i
                found = True
                break
        if found:
            df_clean = pd.read_excel(file, sheet_name=sheet, skiprows=header_row)
            df_clean.columns = [str(c).strip().upper().replace('°', '').replace(' ', '_').replace('.', '') for c in df_clean.columns]
            df_clean = df_clean.dropna(subset=['REGISTRO'], how='any')
            if not df_clean.empty:
                df_clean['HOJA_ORIGEN'] = sheet
                all_dfs.append(df_clean)
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

# 3. MOTOR RPA CORREGIDO (LÓGICA DE LUPA REFORZADA)
async def run_web_automation(df, max_rows):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        df_proc = df.head(max_rows).copy()
        for index, row in df_proc.iterrows():
            animal_id = str(row["REGISTRO"]).strip().upper()
            status_text.text(f"🔍 Validando {index+1}/{len(df_proc)}: {animal_id}")
            res_row = row.to_dict()

            try:
                # Ir a la página de inicio en cada búsqueda para evitar caché de sesión
                await page.goto("https://sir.asocebu.com.co/Genealogias/inicio", timeout=60000)
                
                # Seleccionar búsqueda por Registro
                await page.select_option('select[id*="ddlTipoBusqueda"]', value="1")
                await page.fill('input[id*="txtBusqueda"]', animal_id)
                await page.keyboard.press("Enter")
                
                # ESPERA ACTIVA DE LA LUPA (Independiente de la estructura de la tabla)
                # Este selector busca cualquier botón de tipo imagen o link que actúe como lupa
                lupa = await page.wait_for_selector('input[src*="lupa"], a.btn-ver, .lupa, input[type="image"]', timeout=8000)
                
                if lupa:
                    await lupa.click()
                    # Esperar específicamente a que cargue la ficha (ID de raza es el más estable)
                    await page.wait_for_selector('#lblRaza', timeout=8000)
                    
                    raza_w = (await page.inner_text('#lblRaza')).upper()
                    sexo_w = (await page.inner_text('#lblSexo')).upper()
                    color_w = (await page.inner_text('#lblColor')).upper()
                    nombre_w = await page.inner_text('#lblNombreAnimal')

                    res_row.update({
                        "RESULTADO_RPA": "✅ ENCONTRADO", 
                        "INFO_WEB": f"{raza_w} | {sexo_w} | {color_w}",
                        "NOMBRE_OFICIAL": nombre_w
                    })
                else:
                    raise Exception("Lupa no encontrada")

            except Exception:
                res_row.update({"RESULTADO_RPA": "❌ NO ENCONTRADO", "INFO_WEB": "N/A", "NOMBRE_OFICIAL": "N/A"})
            
            results.append(res_row)
            progress_bar.progress((index + 1) / len(df_proc))
            
        await browser.close()
        return pd.DataFrame(results)

# 4. INTERFAZ
file = st.file_uploader("Suba el archivo de Inventario", type=["xlsx"])
if file:
    df_c = procesar_archivo_cliente(file)
    if not df_c.empty:
        st.dataframe(df_c.head(5))
        if st.button("🚀 Iniciar Auditoría"):
            df_f = asyncio.run(run_web_automation(df_c, 100))
            st.success("✅ Auditoría Completada")
            st.dataframe(df_f)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_f.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte Final", buffer.getvalue(), "Resultado_Auditoria.xlsx")