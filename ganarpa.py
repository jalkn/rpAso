import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

# --- STREAMLIT UI CONFIGURATION ---
st.set_page_config(page_title="Zenergy - RPA Backend Sniper", layout="wide")
st.title("🐄 Asocebu Audit: Direct Session Engine")

def clean_asocebu_excel(file):
    """
    Cleans the uploaded Excel by identifying the dynamic header row.
    Handles legacy formatting and multiple title rows.
    """
    df_raw = pd.read_excel(file, header=None)
    header_idx = 0
    # Search for the row containing the 'REGISTRO' keyword
    for i, row in df_raw.iterrows():
        row_str = " ".join([str(x).upper() for x in row.values if pd.notna(x)])
        if "REGISTRO" in row_str:
            header_idx = i
            break
    
    file.seek(0)
    df = pd.read_excel(file, skiprows=header_idx)
    # Standardize column names to uppercase and trim whitespaces
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    # Ensure the main key column is named 'REGISTRO'
    for col in df.columns:
        if "REGISTRO" in col:
            df = df.rename(columns={col: "REGISTRO"})
            break
    return df

def consultar_asocebu_pro(registro, session):
    """
    Executes a mirrored session handshake to bypass ASP.NET security layers.
    1. GET: Retrieves session cookies and hidden security tokens (__VIEWSTATE).
    2. POST: Replicates the browser's form submission with synchronized tokens.
    """
    url = "https://sir.asocebu.com.co/Genealogias/inicio"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://sir.asocebu.com.co",
        "Referer": url
    }
    
    try:
        # STEP 1: INITIAL HANDSHAKE
        # We request the page to capture active cookies and the current server state
        response_get = session.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response_get.text, 'html.parser')
        
        # STEP 2: TOKEN EXTRACTION
        # Mapping all hidden inputs required by the .NET ViewState validation
        payload = {
            "txtCriterio": registro,
            "ddlTipoBusqueda": "1", # Type '1' usually corresponds to 'Registration Number'
            "btnConsultar": "Consultar"
        }
        
        for hidden in soup.find_all("input", type="hidden"):
            name = hidden.get("name")
            value = hidden.get("value", "")
            if name:
                payload[name] = value

        # STEP 3: DATA SUBMISSION
        # Sending the POST request with the freshly acquired tokens
        response_post = session.post(url, data=payload, headers=headers, timeout=20)
        
        if response_post.status_code == 200:
            # Verification logic: checking if the registration ID exists within the result table
            if registro in response_post.text:
                return "✅ REGISTERED", "Validation Successful"
            return "⚠️ NOT FOUND", "No records found in portal"
        
        # Handling HTTP 405 or other server-side restrictions
        return "❌ BLOCKED", f"Server Status {response_post.status_code}"
        
    except Exception as e:
        return "❌ FAILED", f"Connection error: {str(e)}"

# --- MAIN APPLICATION FLOW ---
uploaded_file = st.file_uploader("📂 Upload 'database.xlsx' for auditing", type=["xlsx"])

if uploaded_file:
    with st.spinner("Processing file structure..."):
        df = clean_asocebu_excel(uploaded_file)
    
    if "REGISTRO" in df.columns:
        st.info(f"Structure validated. {len(df)} animals detected.")
        count = st.number_input("Records to process", 1, len(df), 5)
        
        if st.button("🚀 EXECUTE SNIPER"):
            results = []
            progress = st.progress(0)
            # Persistent session to maintain cookie synchronization
            session = requests.Session()
            
            for index, row in df.head(count).iterrows():
                reg = str(row["REGISTRO"]).strip().split('.')[0]
                if reg in ["NAN", "", "None"]: continue
                
                status, detail = consultar_asocebu_pro(reg, session)
                row["RPA_RESULT"] = status
                row["ENGINE_NOTES"] = detail
                results.append(row)
                
                progress.progress((index + 1) / count)
                # Anti-ban delay to prevent IP throttling
                time.sleep(0.5)

            # Display and Export Results
            df_final = pd.DataFrame(results)
            st.dataframe(df_final)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False)
            st.download_button("📥 Download Final Audit Report", output.getvalue(), "Zenergy_Audit_Report.xlsx")
    else:
        st.error("Header 'REGISTRO' not found. Please check Excel formatting.")