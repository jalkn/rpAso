import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

# --- CONFIGURACIÓN DE INTERFAZ (ESTILO DJANGO CUSTOM) ---
st.set_page_config(page_title="Zenergy - Auditoría Asocebu", layout="wide")

# Inyección de CSS para simular el look & feel del dashboard previo
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button {
        background-color: #0d6efd;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .stButton>button:hover { background-color: #0b5ed7; color: white; }
    .card {
        padding: 1.5rem;
        border-radius: 0.5rem;
        background-color: white;
        box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
        margin-bottom: 1rem;
    }
    h1 { color: #212529; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    </style>
    """, unsafe_allow_html=True)

# Encabezado estilo Navbar
st.markdown("""
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
        <i class="fas fa-database" style="font-size: 2rem; color: #0d6efd;"></i>
        <h1>Importar y Auditar Datos - Asocebu</h1>
    </div>
    """, unsafe_allow_html=True)

def clean_asocebu_excel(file):
    """
    Limpieza de datos: identifica la fila de encabezados real.
    (Technical note: Handles legacy formatting and variable title rows).
    """
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
    """
    Motor de sesión: Handshake sincronizado.
    (Technical note: GET initial tokens -> POST with __VIEWSTATE and session cookies).
    """
    url = "https://sir.asocebu.com.co/Genealogias/inicio"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://sir.asocebu.com.co",
        "Referer": url
    }
    try:
        # Paso 1: Handshake Inicial
        response_get = session.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response_get.text, 'html.parser')
        
        # Paso 2: Extracción de Tokens de Seguridad
        payload = {
            "txtCriterio": registro,
            "ddlTipoBusqueda": "1",
            "btnConsultar": "Consultar"
        }
        for hidden in soup.find_all("input", type="hidden"):
            name = hidden.get("name")
            if name:
                payload[name] = hidden.get("value", "")

        # Paso 3: Envío de Petición
        response_post = session.post(url, data=payload, headers=headers, timeout=20)
        
        if response_post.status_code == 200:
            if registro in response_post.text:
                return "✅ REGISTRADO", "Validación Exitosa"
            return "⚠️ NO ENCONTRADO", "Sin registros en portal"
        return "❌ BLOQUEO", f"Status del Servidor {response_post.status_code}"
    except Exception as e:
        return "❌ ERROR", f"Falla de conexión: {str(e)}"

# --- CUERPO PRINCIPAL ---
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("📂 Seleccione el archivo Excel para iniciar el análisis", type=["xlsx"])
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded_file:
    df = clean_asocebu_excel(uploaded_file)
    
    if "REGISTRO" in df.columns:
        st.success(f"Estructura validada: {len(df)} registros detectados.")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            cant = st.number_input("Cantidad de registros a procesar", 1, len(df), 10)
        
        if st.button("🚀 INICIAR AUDITORÍA"):
            results = []
            progress_bar = st.progress(0)
            session = requests.Session() # Persistencia de sesión (Critical for .NET)
            
            for index, row in df.head(cant).iterrows():
                reg = str(row["REGISTRO"]).strip().split('.')[0]
                if reg in ["NAN", "", "None"]: continue
                
                estado, detalle = consultar_asocebu_pro(reg, session)
                row["RESULTADO_RPA"] = estado
                row["NOTAS_TECNICAS"] = detalle
                results.append(row)
                
                progress_bar.progress((index + 1) / cant)
                time.sleep(0.5) # Delay preventivo

            # Resultados estilo tabla Django
            st.markdown("### Resultados del Análisis")
            df_final = pd.DataFrame(results)
            st.dataframe(df_final, use_container_width=True)
            
            # Exportación
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Descargar Reporte de Auditoría (Excel)",
                data=output.getvalue(),
                file_name="Reporte_Auditoria_Asocebu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("No se detectó la columna 'REGISTRO'. Por favor verifique el formato del archivo.")