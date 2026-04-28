import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

st.set_page_config(page_title="Zenergy - Backend Sniper", layout="wide")
st.title("🐄 Auditoría Asocebu: Conexión Directa (Backend)")
st.markdown("---")

def buscar_en_backend(registro):
    """
    Simula la petición POST que hace el formulario de Asocebu.
    """
    url_base = "https://sir.asocebu.com.co/Genealogias/inicio"
    
    # Headers para parecer un navegador real y evitar bloqueos
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        # 1. Obtenemos la sesión inicial para capturar cookies o ViewStates si existen
        session = requests.Session()
        response_intro = session.get(url_base, headers=headers, timeout=15)
        
        # 2. Preparamos los datos del formulario (Payload)
        # Nota: Estos campos deben coincidir exactamente con los 'name' del HTML de Asocebu
        payload = {
            "txtCriterio": registro,
            "ddlTipoBusqueda": "1", # 1 suele ser 'Registro'
            "btnConsultar": "Consultar"
        }

        # 3. Hacemos la petición directa al backend
        res = session.post(url_base, data=payload, headers=headers, timeout=20)
        
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Buscamos indicios de éxito en el HTML de respuesta
            # Ajusta estos selectores según lo que veas en el Inspector de Elementos (Network tab)
            tabla = soup.find('table') 
            if tabla and registro in tabla.text:
                return "✅ REGISTRADO", "Verificado en Backend"
            else:
                return "⚠️ NO ENCONTRADO", "Sin coincidencia"
        else:
            return "❌ ERROR SERVER", f"Código {res.status_code}"

    except Exception as e:
        return "❌ ERROR CONEXIÓN", str(e)

# --- INTERFAZ ---
file = st.file_uploader("📂 Sube tu Excel de 2500 registros", type=["xlsx"])

if file:
    df = pd.read_excel(file)
    # Limpieza de columnas
    df.columns = [str(c).upper().strip() for c in df.columns]
    reg_col = next((c for c in df.columns if "REGISTRO" in c), None)

    if reg_col:
        cant = st.number_input("Cantidad a procesar", 1, len(df), 10)
        
        if st.button("🚀 INICIAR ESCANEO DE ALTA VELOCIDAD"):
            results = []
            progress = st.progress(0)
            status_text = st.empty()
            
            df_slice = df.head(cant).copy()
            
            for index, row in df_slice.iterrows():
                val_registro = str(row[reg_col]).strip().split('.')[0]
                status_text.text(f"Consultando: {val_registro}...")
                
                estado, info = buscar_en_backend(val_registro)
                
                row["RESULTADO_RPA"] = estado
                row["DETALLE_BACKEND"] = info
                results.append(row)
                
                progress.progress((index + 1) / len(df_slice))
                # Un pequeño sleep para no ser baneados por inundación de peticiones
                time.sleep(0.5)

            df_final = pd.DataFrame(results)
            st.success("¡Proceso terminado!")
            st.dataframe(df_final)
            
            # Descarga
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte", output.getvalue(), "Auditoria_Backend.xlsx")
    else:
        st.error("No encontré la columna 'REGISTRO' en el archivo.")