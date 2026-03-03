import asyncio
from playwright.async_api import async_playwright

# Sustituir con las claves reales para la prueba
CREDS = {
    "1307": "TU_PASSWORD_AQUI",
    "2306": "TU_PASSWORD_AQUI"
}

async def verificar_acceso(usuario, clave):
    async with async_playwright() as p:
        # headless=False para que puedas ver el navegador en tu PC
        browser = await p.chromium.launch(headless=False) 
        page = await browser.new_page()
        print(f"\n--- Probando Acceso Cuenta {usuario} ---")
        
        try:
            await page.goto("https://app.asocebu.com.co/", timeout=60000)
            
            # Espera a que el componente de login de Angular cargue
            await page.wait_for_selector("input", timeout=20000) 
            
            inputs = await page.query_selector_all("input")
            if len(inputs) >= 2:
                # Llenado de campos
                await inputs[0].fill(str(usuario))
                await inputs[1].fill(str(clave))
                
                print("Enviando formulario...")
                await page.keyboard.press("Enter")
                
                # Esperar para ver si la URL cambia (indicativo de login exitoso)
                await page.wait_for_timeout(7000)
                
                if "login" not in page.url.lower():
                    print(f"✅ LOGIN EXITOSO: Bienvenido al portal {usuario}")
                    # Aquí podrías capturar un screenshot para confirmar
                    await page.screenshot(path=f"login_success_{usuario}.png")
                else:
                    print(f"❌ LOGIN FALLIDO: Verifique credenciales para {usuario}")
            else:
                print("❌ No se encontraron los campos de entrada de texto.")
                
        except Exception as e:
            print(f"⚠️ Error durante la ejecución: {e}")
        finally:
            await browser.close()

async def run_all():
    for u, p in CREDS.items():
        if p != "TU_PASSWORD_AQUI":
            await verificar_acceso(u, p)
        else:
            print(f"Skipping {u}: No password provided.")

if __name__ == "__main__":
    asyncio.run(run_all())