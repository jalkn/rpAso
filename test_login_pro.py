import asyncio
from playwright.async_api import async_playwright

# Sustituir con las claves reales enviadas por el cliente
CREDS = {
    "1307": "CONTRASEÑA_USUARIO_1307",
    "2306": "CONTRASEÑA_USUARIO_2306"
}

async def verificar_acceso(usuario, clave):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) 
        page = await browser.new_page()
        print(f"--- Probando Cuenta {usuario} ---")
        
        try:
            await page.goto("https://app.asocebu.com.co/", timeout=60000)
            # Espera específica para componentes Angular
            await page.wait_for_selector("input", timeout=15000) 
            
            inputs = await page.query_selector_all("input")
            if len(inputs) >= 2:
                await inputs[0].fill(str(usuario))
                await inputs[1].fill(str(clave))
                await page.keyboard.press("Enter")
                
                await page.wait_for_timeout(5000)
                if "login" not in page.url.lower():
                    print(f"✅ LOGIN EXITOSO para {usuario}")
                else:
                    print(f"❌ LOGIN FALLIDO para {usuario}. Verifique credenciales.")
        except Exception as e:
            print(f"⚠️ Error de conexión: {e}")
        finally:
            await browser.close()

async def run_tests():
    for u, p in CREDS.items():
        await verificar_acceso(u, p)

if __name__ == "__main__":
    asyncio.run(run_tests())