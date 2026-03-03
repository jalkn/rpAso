import asyncio
import os
import pandas as pd
from playwright.async_api import async_playwright

os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'

async def main():
    print("--- RPA ASOCEBU: CONSOLIDADOR DE POTREROS ---")
    file_path = "database.xlsx"
    
    if not os.path.exists(file_path):
        print(f"Error: No se encuentra {file_path}")
        return

    # Leer todas las pestañas del cliente
    print("Leyendo pestañas del archivo...")
    xl = pd.ExcelFile(file_path)
    all_sheets = []
    for sheet in xl.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet)
        df['Pestaña_Origen'] = sheet
        all_sheets.append(df)
    
    df_total = pd.concat(all_sheets, ignore_index=True)
    df_total.columns = [str(c).strip() for c in df_total.columns]

    # Pedir usuario al iniciar (según requerimiento del cliente)
    print("\nCuentas disponibles: 1. 1307 | 2. 2306")
    opcion = input("Seleccione el número de cuenta a usar: ")
    user_id = "1307" if opcion == "1" else "2306"

    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://sir.asocebu.com.co/Genealogias/")

        for i, row in df_total.iterrows():
            animal_id = str(row.get('N° ANIMAL', '')).strip()
            if not animal_id or "total" in animal_id.lower(): continue
            
            print(f"[{i+1}/{len(df_total)}] Consultando: {animal_id}")
            try:
                await page.fill('input[name="txtBusqueda"]', animal_id)
                await page.press('input[name="txtBusqueda"]', "Enter")
                await page.wait_for_timeout(2000)
                nombre = await page.inner_text('#lblNombreAnimal')
                results.append({**row, "Cuenta": user_id, "Resultado": nombre})
            except:
                results.append({**row, "Cuenta": user_id, "Resultado": "No Encontrado"})

        # Guardar reporte
        pd.DataFrame(results).to_excel("resultado_auditoria.xlsx", index=False)
        await browser.close()
        print("\n--- Proceso Finalizado. Revise resultado_auditoria.xlsx ---")
        input("Presione Enter para salir...")

if __name__ == "__main__":
    asyncio.run(main())