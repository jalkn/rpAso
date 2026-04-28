import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

st.set_page_config(page_title="Zenergy - Backend Sniper", layout="wide")
st.title("🐄 Auditoría Asocebu: Motor de Sesión Pro")

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

def consultar_asocebu(registro, session):
    """Mimetismo de sesión para evitar el Error 405"""
    url = "https://sir.asocebu.com.co/Genealogias/inicio"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": url
    }
    
    try:
        # Paso 1: Obtener la página para activar la sesión y cookies
        first_resp = session.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(first_resp.text, 'html.parser')
        
        # Paso 2: Extraer campos ocultos de seguridad (ViewState)
        payload = {
            "txtCriterio": registro,
            "ddlTipoBusqueda": "1",
            "btnConsultar": "Consultar"
        }
        
        # Buscamos inputs ocultos que el servidor de .NET suele requerir
        for hidden in soup.find_all("input", type="hidden"):
            payload[hidden.get("name")] = hidden.get("value")

        # Paso 3: Enviar la consulta real
        response = session.post(url, data=payload, headers=headers, timeout=20)
        
        if response.status_code == 200:
            if registro in response.text:
                return "✅ REGISTRADO", "Validado"
            return "⚠️ NO ENCONTRADO", "Sin datos"
        return "❌ BLOQUEO", f"Status {response.status_code}"
    except Exception as e:
        return "❌ ERROR", "Falla de red"

# --- UI ---
file = st.file_uploader("📂 Sube el archivo Excel", type=["xlsx"])
if file:
    df = clean_asocebu_excel(file)
    if "REGISTRO" in df.columns:
        st.success("Archivo estructurado correctamente.")
        cant = st.number_input("Cantidad", 1, len(df), 5)
        
        if st.button("🚀 INICIAR AUDITORÍA"):
            results = []
            progress = st.progress(0)
            session = requests.Session() # Mantenemos la misma sesión para todo el proceso
            
            for index, row in df.head(cant).iterrows():
                reg = str(row["REGISTRO"]).strip().split('.')[0]
                estado, detalle = consultar_asocebu(reg, session)
                row["RESULTADO_RPA"] = estado
                row["NOTAS"] = detalle
                results.append(row)
                progress.progress((index + 1) / cant)
                time.sleep(0.5)

            st.dataframe(pd.DataFrame(results))