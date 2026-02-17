import asyncio
import os
import sys
import pandas as pd
from playwright.async_api import async_playwright

# 1. Configuración para que el EXE encuentre el navegador localmente
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'

async def run_automation():
    print("--- Iniciando Bot RPA Asocebu ---")
    
    # 2. Carga y validación del Excel
    file_path = "database.xlsx"
    if not os.path.exists(file_path):
        print(f"Error: No se encontró el archivo {file_path}")
        input("Presione Enter para salir...")
        return

    try:
        local_data = pd.read_excel(file_path)
        # Normalizar nombres de columnas (quitar espacios y pasar a minúsculas para comparar)
        local_data.columns = [str(c).strip() for c in local_data.columns]
        
        # Buscar la columna correcta de forma flexible
        target_col = None
        for col in local_data.columns:
            if col.lower() == 'registration_number':
                target_col = col
                break
        
        if not target_col:
            print("Error: No se encontró la columna 'Registration_Number' en el Excel.")
            print(f"Columnas detectadas: {list(local_data.columns)}")
            input("Corrija el Excel y presione Enter para salir...")
            return
            
    except Exception as e:
        print(f"Error al leer el Excel: {e}")
        input("Presione Enter para salir...")
        return

    results = []

    async with async_playwright() as p:
        # 3. Lanzamiento del navegador
        print("Abriendo navegador...")
        try:
            browser = await p.chromium.launch(headless=False) # Cambiar a True para ocultar
            page = await browser.new_page()
            await page.goto("https://sir.asocebu.com.co/Genealogias/", timeout=60000)

            for index, row in local_data.iterrows():
                animal_id = str(row[target_col]).strip()
                print(f"Consultando animal: {animal_id}")

                try:
                    # Lógica de búsqueda (ajustar selectores según la web real)
                    await page.fill('input[name="txtBusqueda"]', animal_id)
                    await page.click('#btnConsultar') # Selector de ejemplo
                    await page.wait_for_timeout(2000)

                    # Extraer dato (ejemplo)
                    web_name = await page.inner_text('#lblNombreAnimal') 
                    results.append({**row, "Web_Status": "Encontrado", "Nombre_Web": web_name})
                except:
                    results.append({**row, "Web_Status": "No Encontrado", "Nombre_Web": "N/A"})

            # 4. Generar Reporte Final
            final_df = pd.DataFrame(results)
            output_file = "comparison_report.xlsx"
            final_df.to_excel(output_file, index=False)
            print(f"--- Proceso completado. Reporte generado: {output_file} ---")

        except Exception as e:
            print(f"Error durante la automatización: {e}")
        finally:
            await browser.close()

    input("Presione Enter para cerrar esta ventana...")

if __name__ == "__main__":
    asyncio.run(run_automation())