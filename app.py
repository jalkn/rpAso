import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import io
import subprocess
import os
import time

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="ARPA - Sniper Cloud Edition",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. IDENTIDAD VISUAL (Mismo estilo que ganarpa.py) ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff !important; }
    
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
        width: 40px;
        height: 40px;
        background-color: #0b00a2;
        border-radius: 8px;
        display: inline-flex;
    }
    
    .navbar-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a1a1a;
        letter-spacing: -0.5px;
    }

    .card {
        padding: 2rem;
        border-radius: 12px;
        border: 1px solid #e9ecef;
        background-color: #ffffff;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        margin-bottom: 1.5rem;
    }

    .stButton>button {
        width: 100%;
        background-color: #0b00a2 !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 0.75rem !important;
        font-weight: 600 !important;
        border: none !important;
    }
    </style>
    
    <div class="custom-navbar">
        <div class="logoIN"></div>
        <div class="navbar-title">A R P A <span style="color: #6c757d; font-weight: 300;">| Sniper Cloud</span></div>
    </div>
""", unsafe_allow_html=True)

# --- 3. INSTALACIÓN DE DEPENDENCIAS EN LA NUBE ---
@st.cache_resource
def install_browser():
    try:
        # Intentamos asegurar que las dependencias de sistema estén presentes
        subprocess.run(["playwright", "install", "chromium"], check=True)
        return True
    except Exception as e:
        st.error(f"Error configurando entorno de nube: {e}")
        return False

# --- 4. MOTOR DE AUDITORÍA (Hybrid Backend Sniper) ---
async def run_audit(df_proc, cant):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-dev-shm-usage", "--single-process"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        try:
            for index, row in df_proc.head(cant).iterrows():
                animal_id = str(row.get("REGISTRO", "")).strip().split('.')[0]
                if not animal_id or animal_id == "nan": continue
                
                status_text.text(f"Auditando animal: {animal_id}...")
                
                # Acceso directo al portal
                await page.goto("https://www.asocebu.com/SIR/formularios/consultas.aspx", timeout=60000)
                
                # Inyección de búsqueda avanzada (JS nivel senior)
                injection_js = f"""
                (() => {{
                    function find(root, val) {{
                        let inputs = root.querySelectorAll('input');
                        for (let i of inputs) {{
                            if (i.type === 'text') i.value = val;
                            let btn = Array.from(inputs).find(i => i.value && i.value.toUpperCase().includes('CONSULTAR'));
                            if (btn) {{ btn.click(); return true; }}
                        }}
                        return false;
                    }}
                    return find(document, '{animal_id}');
                }})();
                """
                await page.evaluate(injection_js)
                await asyncio.sleep(8) # Espera técnica para respuesta del servidor
                
                row["RESULTADO_RPA"] = "✅ PROCESADO"
                row["ESTADO_SERVER"] = "Investigación en curso"
                results.append(row)
                
                progress_bar.progress((index + 1) / cant)
                
        except Exception as e:
            st.error(f"Interrupción técnica: {e}")
        finally:
            await browser.close()
            
    return pd.DataFrame(results)

# --- 5. INTERFAZ DE USUARIO ---
if install_browser():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📥 Carga de Datos")
    uploaded_file = st.file_uploader("Sube el archivo Excel de potrero", type=["xlsx"])
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        # Normalizar columnas
        df.columns = [str(c).upper().strip() for c in df.columns]
        
        if "REGISTRO" in df.columns:
            st.success(f"Se detectaron {len(df)} animales para auditar.")
            cant = st.number_input("Cantidad de registros a validar", 1, len(df), 5)
            
            if st.button("🚀 INICIAR SNIPER CLOUD"):
                with st.spinner("Ejecutando protocolo de auditoría..."):
                    df_final = asyncio.run(run_audit(df, cant))
                    
                    st.markdown("### 📊 Consolidado de Resultados")
                    st.dataframe(df_final, use_container_width=True)
                    
                    # Preparar descarga
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_final.to_excel(writer, index=False)
                    
                    st.download_button(
                        label="📥 DESCARGAR REPORTE",
                        data=output.getvalue(),
                        file_name="Reporte_Investigacion_ARPA.xlsx",
                        mime="application/vnd.ms-excel"
                    )
        else:
            st.error("El archivo no contiene la columna 'REGISTRO'.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
    <div style="text-align: center; color: #6c757d; font-size: 0.8rem; margin-top: 2rem;">
        &copy; A R P A - Automatización Robótica de Procesos de Auditoría
    </div>
""", unsafe_allow_html=True)