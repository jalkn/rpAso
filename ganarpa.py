import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

st.set_page_config(page_title="Zenergy - Backend Sniper", layout="wide")
st.title("🐄 Auditoría Asocebu: Conexión Directa")

def clean_asocebu_excel(file):
    """Limpia el Excel buscando la fila de encabezados real"""
    # Leemos el excel saltando las filas de logos/títulos iniciales
    df_raw = pd.read_excel(file, header=None)
    
    # Buscamos la fila que contiene la palabra 'REGISTRO'
    header_idx = 0
    for i, row in df_raw.iterrows():
        row_str = " ".join([str(x).upper() for x in row.values if pd.notna(x)])
        if "REGISTRO" in row_str:
            header_idx = i
            break
            
    # Volvemos a leer desde esa fila
    file.seek(0)
    df = pd.read_excel(file, skiprows=header_idx)
    
    # Limpiamos nombres de columnas
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    # Renombrar columna de registro si tiene variaciones
    for col in df.columns:
        if "REGISTRO" in col:
            df = df.rename(columns={col: "REGISTRO"})
            break
    return df

def consultar_backend(registro):
    """Petición directa al servidor de Asocebu"""
    url = "https://sir.asocebu.com.co/Genealogias/inicio"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        session = requests.Session()
        # Payload mínimo necesario para activar la búsqueda
        payload = {
            "txtCriterio": registro,
            "ddlTipoBusqueda": "1",
            "btnConsultar": "Consultar"
        }
        
        response = session.post(url, data=payload, headers=headers, timeout=20)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Si el registro aparece en el cuerpo de la página, es porque la tabla lo encontró
            if registro in response.text:
                return "✅ REGISTRADO", "Encontrado en base de datos"
            return "⚠️ NO ENCONTRADO", "Sin coincidencia en portal"
        return "❌ ERROR", f"Status {response.status_code}"
    except:
        return "❌ TIMEOUT", "Error de conexión"

# --- INTERFAZ ---
uploaded_file = st.file_uploader("📂 Sube el archivo 'database (3).xlsx'", type=["xlsx"])

if uploaded_file:
    with st.spinner("Analizando estructura del archivo..."):
        df = clean_asocebu_excel(uploaded_file)
    
    if "REGISTRO" in df.columns:
        st.success(f"Columna 'REGISTRO' detectada. {len(df)} animales cargados.")
        cant = st.number_input("Cantidad a auditar", 1, len(df), 10)
        
        if st.button("🚀 INICIAR ESCANEO DE ALTA VELOCIDAD"):
            results = []
            progress = st.progress(0)
            df_proc = df.head(cant).copy()
            
            for index, row in df_proc.iterrows():
                reg = str(row["REGISTRO"]).strip().split('.')[0]
                if reg == "NAN" or reg == "": continue
                
                estado, detalle = consultar_backend(reg)
                row["RESULTADO_RPA"] = estado
                row["NOTAS"] = detalle
                results.append(row)
                
                progress.progress((index + 1) / len(df_proc))
                time.sleep(0.3) # Respeto al servidor

            df_final = pd.DataFrame(results)
            st.dataframe(df_final)
            
            # Exportar
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte Final", output.getvalue(), "Auditoria_Zenergy.xlsx")
    else:
        st.error("No se pudo identificar la columna de Registros. Verifica que el Excel tenga la palabra 'REGISTRO' en el encabezado.")