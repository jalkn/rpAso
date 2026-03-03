import asyncio
from playwright.async_api import async_playwright

async def test_asocebu_login():
    async with async_playwright() as p:
        # Lanzamos el navegador visible para monitorear el proceso
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        print("🚀 Accediendo a la plataforma de Denuncios...")
        await page.goto("https://app.asocebu.com.co/", timeout=60000)

        # Basado en la estructura Angular detectada en el inspector
        # Intentamos localizar los inputs de login
        try:
            # Esperamos a que el formulario cargue (Angular usa componentes dinámicos)
            await page.wait_for_selector("input", timeout=10000)
            
            # Ingreso de credenciales del cliente
            print("🔐 Ingresando credenciales...")
            inputs = await page.query_selector_all("input")
            
            if len(inputs) >= 2:
                await inputs[0].fill("1307")  # Usuario
                await inputs[1].fill("TU_CONTRASEÑA_AQUÍ") # Contraseña del correo
                
                # Buscamos el botón de ingreso (comúnmente mat-button en Angular)
                await page.keyboard.press("Enter")
                
                print("⏳ Verificando acceso...")
                await page.wait_for_timeout(5000)
                
                if "login" not in page.url.lower():
                    print("✅ ¡Login Exitoso! Estamos dentro del sistema.")
                else:
                    print("❌ El login falló o requiere interacción adicional.")
            
        except Exception as e:
            print(f"⚠️ Error durante la prueba: {e}")
        
        finally:
            print("Cerrando sesión de prueba en 10 segundos...")
            await asyncio.sleep(10)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_asocebu_login())