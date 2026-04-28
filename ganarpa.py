import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

st.set_page_config(page_title="Zenergy - Backend Sniper V5", layout="wide")
st.title("🐄 Auditoría Asocebu: Handshake Completo")

def consultar_asocebu_final(registro, session):
    url = "https://sir.asocebu.com.co/Genealogias/inicio"
    # Headers extendidos para máxima compatibilidad
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Origin": "https://sir.asocebu.com.co",
        "Referer": url,
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        # 1. Cargar la página para obtener cookies y el estado inicial
        res_get = session.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res_get.text, 'html.parser')
        
        # 2. Construir el Payload con TODOS los campos de ASP.NET
        payload = {}
        inputs = soup.find_all("input")
        for inp in inputs:
            name = inp.get("name")
            value = inp.get("value", "")
            if name:
                payload[name] = value
        
        # 3. Sobrescribir los campos de búsqueda
        payload["txtCriterio"] = registro
        payload["ddlTipoBusqueda"] = "1"
        
        # El botón de ASP.NET a veces requiere su propia clave en el POST
        payload["btnConsultar"] = "Consultar"

        # 4. Enviar el POST
        res_post = session.post(url, data=payload, headers=headers, timeout=20)
        
        if res_post.status_code == 200:
            if registro in res_post.text:
                return "✅ REGISTRADO", "Encontrado"
            return "⚠️ NO ENCONTRADO", "Sin datos"
        return "❌ BLOQUEO", f"Status {res_post.status_code}"
    except Exception as e:
        return "❌ ERROR", str(e)

# --- UI Simplificada ---
file = st.file_uploader("Sube el Excel", type=["xlsx"])
if file:
    # Usamos la lógica de limpieza que ya teníamos
    df_raw = pd.read_excel(file, header=None)
    header_idx = 0
    for i, row in df_raw.iterrows():
        if "REGISTRO" in " ".join([str(x).upper() for x in row.values if pd.notna(x)]):
            header_idx = i
            break
    file.seek(0)
    df = pd.read_excel(file, skiprows=header_idx)
    df.columns = [str(c).upper().strip() for c in df.columns]
    
    if st.button("🚀 ÚLTIMO DISPARO"):
        results = []
        session = requests.Session()
        for idx, row in df.head(5).iterrows():
            reg = str(row.get("REGISTRO", "")).split('.')[0]
            status, note = consultar_asocebu_final(reg, session)
            row["RESULTADO_RPA"] = status
            row["NOTAS"] = note
            results.append(row)
            time.sleep(1)
        st.dataframe(pd.DataFrame(results))