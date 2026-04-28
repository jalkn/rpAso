import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

st.set_page_config(page_title="Zenergy - Backend Sniper Pro", layout="wide")
st.title("🐄 Auditoría Asocebu: Motor de Sesión Blindado")

def clean_asocebu_excel(file):
    df_raw = pd.read_excel(file, header=None)
    header_idx = 0
    for i, row in df_raw.iterrows():
        row_str = " ".join([str(x).upper() for x in row.values if pd.notna(x)])
        if "REGISTRO" in row_str:
            header_idx = i
            break
    file.seek(0)
    df = pd.read_excel(file, skiprows=header_idx)
    df.columns = [str(c).strip().upper() for c in df.columns]
    for col in df.columns:
        if "REGISTRO" in col:
            df = df.rename(columns={col: "REGISTRO"})
            break
    return df

def consultar_asocebu_pro(registro, session):
    url = "https://sir.asocebu.com.co/Genealogias/inicio"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://sir.asocebu.com.co",
        "Referer": url
    }
    
    try:
        # 1. Obtener la página actual para extraer los tokens de ASP.NET
        response_get = session.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response_get.text, 'html.parser')
        
        # 2. Mapear TODOS los campos ocultos necesarios para el servidor
        payload = {
            "txtCriterio": registro,
            "ddlTipoBusqueda": "1",
            "btnConsultar": "Consultar"
        }
        
        for hidden in soup.find_all("input", type="hidden"):
            name = hidden.get("name")
            value = hidden.get("value", "")
            if name:
                payload[name] = value

        # 3. Ejecutar el POST con los tokens frescos
        response_post = session.post(url, data=payload, headers=headers, timeout=20)
        
        if response_post.status_code == 200:
            # Si el número de registro aparece en la tabla de resultados del HTML
            if registro in response_post.text:
                return "✅ REGISTRADO", "Validación Exitosa"
            return "⚠️ NO ENCONTRADO", "No figura en portal"
        
        return "❌ ERROR", f"Status {response_post.status_code}"
    except Exception as e:
        return "❌ FALLA", str(e)

# --- FLUJO PRINCIPAL ---
uploaded_file = st.file_uploader("📂 Sube el archivo Excel", type=["xlsx"])

if uploaded_file:
    df = clean_asocebu_excel(uploaded_file)
    if "REGISTRO" in df.columns:
        st.info(f"Estructura válida. {len(df)} animales detectados.")
        cant = st.number_input("Cantidad a procesar", 1, len(df), 5)
        
        if st.button("🚀 INICIAR SNIPER"):
            results = []
            progress = st.progress(0)
            # Una sola sesión para reutilizar cookies de conexión
            session = requests.Session()
            
            for index, row in df.head(cant).iterrows():
                reg = str(row["REGISTRO"]).strip().split('.')[0]
                if reg in ["NAN", ""]: continue
                
                estado, detalle = consultar_asocebu_pro(reg, session)
                row["RESULTADO_RPA"] = estado
                row["NOTAS"] = detalle
                results.append(row)
                
                progress.progress((index + 1) / cant)
                time.sleep(0.4) # Evitar baneo por velocidad

            df_res = pd.DataFrame(results)
            st.dataframe(df_res)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_res.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte", output.getvalue(), "Auditoria_Final.xlsx")