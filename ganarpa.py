import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

# --- 1. CONFIGURACIÓN DE PÁGINA Y TEMA ---
st.set_page_config(
    page_title="Zenergy - Auditoría Asocebu",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. INYECCIÓN DE ESTILO (FONDO BLANCO Y LOOK & FEEL DJANGO) ---
st.markdown("""
    <style>
    /* Forzar fondo blanco en toda la app */
    .stApp {
        background-color: #ffffff;
    }
    
    /* Estilo del Header/Navbar similar a los archivos .html previos */
    .custom-navbar {
        background-color: #ffffff;
        padding: 1rem 2rem;
        border-bottom: 1px solid #e9ecef;
        display: flex;
        align-items: center;
        gap: 15px;
        margin-bottom: 2rem;
    }
    
    /* Títulos y texto en color oscuro para legibilidad */
    h1, h2, h3, p, span, label {
        color: #212529 !important;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }

    /* Estilo de Tarjetas (Cards) */
    .card {
        padding: 1.5rem;
        border-radius: 0.5rem;
        background-color: #ffffff;
        border: 1px solid #dee2e6;
        box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.05);
        margin-bottom: 1.5rem;
    }

    /* Botón estilo Bootstrap Primary */
    .stButton>button {
        background-color: #0d6efd;
        color: white !important;
        border-radius: 6px;
        border: none;
        padding: 0.6rem 1.2rem;
        font-weight: 500;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #0b5ed7;
        border: none;
    }
    
    /* Estilo de la barra de progreso */
    .stProgress > div > div > div > div {
        background-color: #0d6efd;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LÓGICA DEL BACKEND (SNIPER ENGINE) ---

def clean_asocebu_excel(file):
    """
    Identifies the header row dynamically and cleans the dataframe.
    (Technical note: Skips logos and decorative rows found in client excels).
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
    Advanced Handshake: Synchronizes ASP.NET tokens and session cookies.
    (Technical note: POST request targets __VIEWSTATE to emulate browser state).
    """
    url = "https://sir.asocebu.com.co/Genealogias/inicio"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://sir.asocebu.com.co",
        "Referer": url
    }
    try:
        # Step 1: Handshake to get fresh session tokens
        response_get = session.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response_get.text, 'html.parser')
        
        # Step 2: Build Payload with dynamic security fields
        payload = {
            "txtCriterio": registro,
            "ddlTipoBusqueda": "1",
            "btnConsultar": "Consultar"
        }
        for hidden in soup.find_all("input", type="hidden"):
            name = hidden.get("name")
            if name:
                payload[name] = hidden.get("value", "")

        # Step 3: Execution
        response_post = session.post(url, data=payload, headers=headers, timeout=20)
        
        if response_post.status_code == 200:
            if registro in response_post.text:
                return "✅ REGISTRADO", "Encontrado en SIR"
            return "⚠️ NO ENCONTRADO", "Sin coincidencia en portal"
        return "❌ ERROR", f"Servidor respondió con {response_post.status_code}"
    except Exception as e:
        return "❌ FALLA", f"Error de red: {str(e)}"

# --- 4. INTERFAZ DE USUARIO (FRONTEND) ---

# Navbar simulada
st.markdown("""
    <div class="custom-navbar">
        <span style="font-size: 1.5rem;">🐄</span>
        <h1 style="margin: 0; font-size: 1.25rem; font-weight: 600;">Auditoría de Inventario - Asocebu</h1>
    </div>
    """, unsafe_allow_html=True)

# Contenedor principal
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Importación de Datos")
    uploaded_file = st.file_uploader("Arrastre aquí el archivo Excel de potreros", type=["xlsx"])
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded_file:
    with st.spinner("Analizando archivo..."):
        df = clean_asocebu_excel(uploaded_file)
    
    if "REGISTRO" in df.columns:
        st.success(f"Estructura validada: {len(df)} registros detectados.")
        
        # Layout de configuración
        col_setup, _ = st.columns([1, 2])
        with col_setup:
            cant = st.number_input("Cantidad de animales a auditar", 1, len(df), 10)
        
        if st.button("🚀 INICIAR AUDITORÍA"):
            results = []
            progress_bar = st.progress(0)
            session = requests.Session() # Persistencia de cookies necesaria para ASP.NET
            
            # Ejecución del RPA
            for index, row in df.head(cant).iterrows():
                reg_raw = str(row["REGISTRO"]).strip().split('.')[0]
                if reg_raw in ["NAN", "", "None"]: continue
                
                estado, detalle = consultar_asocebu_pro(reg_raw, session)
                row["RESULTADO_RPA"] = estado
                row["NOTAS_TECNICAS"] = detalle
                results.append(row)
                
                # Actualizar progreso
                progress_bar.progress((index + 1) / cant)
                time.sleep(0.4) # Delay preventivo para evitar bloqueos por IP

            # Mostrar resultados en tabla estilo Django
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("### Vista Previa de Resultados")
            df_final = pd.DataFrame(results)
            st.dataframe(df_final, use_container_width=True)
            
            # Preparar descarga
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Descargar Reporte Completo (Excel)",
                data=output.getvalue(),
                file_name="Reporte_Auditoria_Asocebu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error("Error: No se encontró la columna 'REGISTRO'. Verifique el formato del Excel.")

# Pie de página discreto
st.markdown("""
    <div style="text-align: center; margin-top: 50px; padding: 20px; color: #6c757d; font-size: 0.8rem;">
        Zenergy | Tecnología de Auditoría Ganadera
    </div>
    """, unsafe_allow_html=True)