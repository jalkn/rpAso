import asyncio
import os
import pandas as pd
from playwright.async_api import async_playwright

os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'

async def main():
    print("--- RPA ASOCEBU LOCAL (POTREROS) ---")
    file = "database.xlsx"
    
    if not os.path.exists(file):
        print("Error: No se encuentra database.xlsx")
        return

    # Leer todas las pestañas
    xl = pd.ExcelFile(file)
    df = pd.concat([pd.read_excel(file, sheet_name=s).assign(Pestaña=s) for s in xl.sheet_names], ignore_index=True)
    df.columns = [str(c).strip() for c in df.columns]

    print(f"Cuentas: 1. 1307 | 2. 2306")
    user_id = "1307" if input("Seleccione (1/2): ") == "1" else "2306"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://sir.asocebu.com.co/Genealogias/")

        results = []
        for i, row in df.iterrows():
            animal = str(row.get('N° ANIMAL', '')).strip()
            if not animal or "total" in animal.lower(): continue
            
            print(f"Consultando {animal}...")
            try:
                await page.fill('input[name="txtBusqueda"]', animal)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2000)
                nombre = await page.inner_text('#lblNombreAnimal')
                results.append({**row, "Cuenta": user_id, "Resultado": nombre})
            except:
                results.append({**row, "Cuenta": user_id, "Resultado": "No Encontrado"})

        pd.DataFrame(results).to_excel("resultado_auditoria.xlsx", index=False)
        await browser.close()
        print("Hecho. Reporte guardado.")

if __name__ == "__main__":
    asyncio.run(main())