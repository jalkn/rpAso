# 🐄 RPA Asocebu - Auditoría de Inventario Ganadero

Esta es una solución de automatización robótica de procesos (RPA) de alto rendimiento diseñada para agilizar la conciliación de inventarios bovinos ante la plataforma **Asocebu**. La herramienta permite procesar archivos masivos de potreros y validar la integridad de los datos de forma automática y precisa.

---

## 🛠️ Stack Tecnológico
El proyecto utiliza estándares de ingeniería de software para garantizar velocidad y estabilidad:

* **Lenguaje:** [Python 3.12](https://www.python.org/)
* **Motor de Automatización:** Peticiones directas a nivel de servidor (Backend Sniper) para omitir la carga de interfaces gráficas pesadas.
* **Procesamiento de Datos:** [Pandas](https://pandas.pydata.org/) & [OpenPyXL](https://openpyxl.readthedocs.io/) para el manejo inteligente de tablas masivas.
* **Interfaz de Usuario:** [Streamlit](https://streamlit.io/) con estética de dashboard corporativo.

---

## 📋 Funcionalidades Principales
1.  **Limpieza Inteligente de Datos:** Identificación automática de la tabla de datos real dentro de archivos Excel, ignorando encabezados decorativos o logos.
2.  **Protocolo de Conexión Directa:** Sistema de "handshake" que gestiona tokens ASP.NET (`__VIEWSTATE`, `__EVENTVALIDATION`) para una comunicación fluida con el portal SIR de Asocebu.
3.  **Auditoría de Alta Velocidad:** Validación masiva de registros de animales mediante el análisis de respuestas directas del servidor.
4.  **Generación de Reportes Finales:** Exportación de resultados detallados en formato Excel (`.xlsx`) con diagnósticos de estado por cada animal.

---

## ⚙️ Estructura del Repositorio
* `ganarpa.py`: Aplicación principal que contiene el motor de auditoría y la interfaz de usuario.
* `requirements.txt`: Dependencias de librerías Python necesarias.
* `packages.txt`: Dependencias de sistema para el despliegue en la nube.

---

## 💻 Instalación Local (Para Desarrolladores)
Si deseas ejecutar el proyecto localmente o realizar auditorías al código:

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/jalkn/rpAso.git](https://github.com/jalkn/rpAso.git)

2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt

3. **Ejecutar la aplicación:**
   ```bash
   streamlit run ganarpa.py