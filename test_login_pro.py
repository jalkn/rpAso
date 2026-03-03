import asyncio
from playwright.async_api import async_playwright

# Sustituir con las claves reales enviadas por el cliente
CREDS = {
    "1307": "CONTRASEÑA_CORREO_1",
    "2306": "CONTRASEÑA_CORREO_2"
}

async def verificar_acceso(usuario, clave):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) # Para que veas el proceso
        page = await browser.new_page()
        print(f"--- Probando Cuenta {usuario} ---")
        
        await page.goto("https://app.asocebu.com.co/", timeout=60000)
        await page.wait_for_selector("input", timeout=15000) # Espera a Angular
        
        inputs = await page.query_selector_all("input")
        if len(inputs) >= 2:
            await inputs[0].fill(usuario)
            await inputs[1].fill(clave)
            await page.keyboard.press("Enter")
            
            await page.wait_for_timeout(5000)
            if "login" not in page.url.lower():
                print(f"✅ LOGIN EXITOSO para {usuario}")
            else:
                print(f"❌ LOGIN FALLIDO para {usuario}")
        await browser.close()

async def run_tests():
    for u, p in CREDS.items():
        await verificar_acceso(u, p)

if __name__ == "__main__":
    asyncio.run(run_tests())