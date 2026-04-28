import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="ARPA - Auditoría Asocebu",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CLONING IDENTITY (LOGO & BUTTONS) ---
st.markdown("""
    <style>
    /* Global Reset to White */
    .stApp, .main, [data-testid="stHeader"], [data-testid="stVerticalBlock"] {
        background-color: #ffffff !important;
    }

    /* 1. BRANDING: EXACT LOGO FROM LANDING PAGE */
    .custom-navbar {
        background-color: #ffffff;
        padding: 1rem 2rem;
        border-bottom: 1px solid #e9ecef;
        display: flex;
        align-items: center;
        gap: 15px;
        margin-bottom: 2rem;
    }
    
    .logoIN {
        cursor: pointer;
        width: 40px;
        height: 40px;
        background-color: #0b00a2; /* Azul exacto de la landing */
        border-radius: 8px;
        display: inline-flex;
        position: relative;
        flex-shrink: 0;
    }
    
    .logoIN::before {
        content: "";
        width: 40px;
        height: 40px;
        border-radius: 50%;
        position: absolute;
        top: 30%;
        left: 70%;
        transform: translate(-50%, -50%);
        background-image: linear-gradient(to right, 
            #ffffff 2px, transparent 1.5px,
            transparent 1.5px, #ffffff 1.5px,
            #ffffff 2px, transparent 1.5px);
        background-size: 4px 100%; 
    }

    .navbar-brand-text {
        color: #0b00a2;
        font-weight: 800;
        font-size: 1.5rem;
        letter-spacing: 2px;
        margin: 0;
        line-height: 1;
    }

    /* 2. BUTTONS & ICONS: FORCED WHITE */
    div[data-testid="stButton"] button p, 
    div[data-testid="stDownloadButton"] button p,
    div[data-testid="stFileUploader"] button p,
    div[data-testid="stFileUploader"] button svg,
    div[data-testid="stFileUploader"] button span {
        color: #ffffff !important;
        fill: #ffffff !important;
    }

    [data-testid="stFileUploaderFileName"], 
    [data-testid="stFileUploaderSmall"] div {
        color: #ffffff !important;
        font-weight: 500;
    }

    div[data-testid="stButton"] button, 
    div[data-testid="stDownloadButton"] button, 
    div[data-testid="stFileUploader"] button {
        background-color: #0b00a2 !important;
        color: #ffffff !important;
        border: none !important;
        padding: 0.7rem 1.5rem !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        width: 100% !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    div[data-testid="stButton"] button:hover, 
    div[data-testid="stDownloadButton"] button:hover,
    div[data-testid="stFileUploader"] button:hover {
        background-color: #08007a !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }

    /* 3. WIDGETS STYLE */
    [data-testid="stFileUploader"] section {
        background-color: #ffffff !important;
        border: 1px dashed #dee2e6 !important;
    }
    
    div[data-testid="stNumberInput"] input {
        background-color: #ffffff !important;
        color: #212529 !important;
        border: 1px solid #e9ecef !important;
    }

    h1, h2, h3, p, span, label, li {
        color: #212529 !important;
    }

    .card {
        padding: 1.5rem;
        border-radius: 0.25rem;
        background-color: #ffffff;
        border: 1px solid #e9ecef;
        box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.05);
        margin-bottom: 1.5rem;
    }

    .footer-arpa {
        width: 100%;
        text-align: center;
        margin-top: 50px;
        padding: 20px 0;
        border-top: 1px solid #e9ecef;
        color: #6c757d !important;
        font-size: 0.8rem;
        letter-spacing: 3px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. RPA LOGIC ---

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
    headers = {"User-Agent": "Mozilla/5.0", "Origin": "https://sir.asocebu.com.co"}
    try:
        res_get = session.get(url, timeout=10)
        soup = BeautifulSoup(res_get.text, 'html.parser')
        payload = {"txtCriterio": registro, "ddlTipoBusqueda": "1", "btnConsultar": "Consultar"}
        for h in soup.find_all("input", type="hidden"):
            payload[h.get("name")] = h.get("value", "")
        res_post = session.post(url, data=payload, timeout=15)
        if res_post.status_code == 200:
            return ("✅ REGISTRADO", "Validado en SIR") if registro in res_post.text else ("⚠️ NO ENCONTRADO", "Sin registros")
        return "❌ ERROR", f"Status {res_post.status_code}"
    except: return "❌ FALLA", "Error de conexión"

# --- 4. UI LAYOUT ---

st.markdown("""
    <div class="custom-navbar">
        <div class="logoIN"></div>
        <div class="navbar-brand-text">ARPA</div>
        <div style="color: #6c757d; font-size: 1.1rem; padding-left: 10px; border-left: 1px solid #dee2e6; margin-left: 10px;">
            Auditoría de Inventario Ganadero
        </div>
    </div>
    """, unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📥 Importar Datos")
    uploaded_file = st.file_uploader("Seleccione el archivo de potrero (.xlsx)", type=["xlsx"])
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded_file:
    df = clean_asocebu_excel(uploaded_file)
    if "REGISTRO" in df.columns:
        st.success(f"{len(df)} animales detectados.")
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        cant = st.number_input("Cantidad a auditar", 1, len(df), 10)
        
        if st.button("🚀 EJECUTAR AUDITORÍA"):
            results = []
            bar = st.progress(0)
            session = requests.Session()
            
            for index, row in df.head(cant).iterrows():
                reg = str(row["REGISTRO"]).strip().split('.')[0]
                if reg in ["NAN", ""]: continue
                est, det = consultar_asocebu_pro(reg, session)
                row["RESULTADO_RPA"] = est
                row["NOTAS"] = det
                results.append(row)
                bar.progress((index + 1) / cant)
                time.sleep(0.3)

            st.markdown("### Resultados")
            df_res = pd.DataFrame(results)
            st.dataframe(df_res, use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_res.to_excel(writer, index=False)
            
            st.download_button("📥 DESCARGAR REPORTE", output.getvalue(), "Reporte_ARPA.xlsx")
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
    <div class="footer-arpa">
        &copy;  A R P A - Automatización Robótica de Procesos de Auditoría
    </div>
    """, unsafe_allow_html=True)