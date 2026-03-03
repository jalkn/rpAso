# 🐄 RPA Asocebu - Auditoría de Inventario Ganadero

Esta es una solución de automatización robótica de procesos (RPA) diseñada para agilizar la conciliación de inventarios bovinos ante la plataforma de **Asocebu**. La herramienta permite procesar archivos masivos de potreros y validar la existencia y datos de los semovientes de forma automática.

## 🚀 Acceso a la Aplicación
La herramienta está desplegada como una plataforma SaaS (Software as a Service) y no requiere instalación local ni permisos de administrador:
👉 **[rpasocebu.streamlit.app](https://rpasocebu.streamlit.app/)**

---

## 🛠️ Stack Tecnológico
El proyecto ha sido desarrollado siguiendo estándares modernos de ingeniería de software:

* **Lenguaje:** [Python 3.12](https://www.python.org/)
* **Automatización Web:** [Playwright](https://playwright.dev/) (Motor de alta velocidad para navegación controlada por script).
* **Procesamiento de Datos:** [Pandas](https://pandas.pydata.org/) & [OpenPyXL](https://openpyxl.readthedocs.io/) (Data Science para manejo de grandes volúmenes de registros).
* **Interfaz de Usuario:** [Streamlit](https://streamlit.io/) (Framework para aplicaciones web de datos).

---

## 📋 Funcionalidades Principales
1.  **Limpieza Inteligente de Datos:** El sistema escanea el archivo Excel del cliente, identifica automáticamente la tabla real (omitiendo encabezados decorativos) y normaliza los registros.
2.  **Procesamiento Multi-Pestaña:** Capacidad de unir automáticamente todos los potreros contenidos en diferentes hojas de un mismo libro de Excel.
3.  **Auditoría Web Automática:** Navega de forma autónoma por el SIR de Asocebu para validar la información de cada animal.
4.  **Generación de Reportes:** Exporta los resultados en un archivo Excel (`.xlsx`) listo para la toma de decisiones.

---

## ⚙️ Estructura del Repositorio
* `app.py`: Aplicación principal (SaaS) desplegada en la nube.
* `main.py`: Versión de escritorio para procesamiento local.
* `test_login_pro.py`: Script de diagnóstico para validación de credenciales en el portal privado.
* `.github/workflows/build.yml`: Pipeline de CI/CD para la generación automática del ejecutable (.exe) para Windows.

---

## 💻 Instalación Local (Para Desarrolladores)
Si deseas ejecutar el proyecto localmente o realizar auditorías al código:

1. Clonar el repositorio:
   ```bash
   git clone [https://github.com/jalkn/rpAso.git](https://github.com/jalkn/rpAso.git)

2. Instalar dependencias:
    ```bash
    pip install -r requirements.txt

3. Instalar navegadores de Playwright:
    ```bash
    playwright install chromium


4. Ejecutar la aplicación web:
    ```bash
    streamlit run app.py