# Urban Scooter — Framework de Automatización QA

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![pytest](https://img.shields.io/badge/pytest-8.3.5-blue?logo=pytest)](https://docs.pytest.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.50-green?logo=playwright)](https://playwright.dev/)
[![Appium](https://img.shields.io/badge/Appium-5.1.1-purple?logo=appium)](https://appium.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-blue?logo=postgresql)](https://www.postgresql.org/)

Framework de automatización E2E para la plataforma de renta de scooters Urban Scooter.  
Proyecto final del bootcamp **TripleTen QA Engineer — Cohorte 2026**.

---

## Resumen

Este proyecto demuestra capacidad para **diseñar e implementar un framework de QA desde cero**, cubriendo la pirámide completa de pruebas en un producto real:

- **251 casos automatizados** distribuidos en 5 suites (Web, API, Móvil, DB) con **81 bugs documentados** y exportados a Jira.
- **Arquitectura modular** con Page Object Model, fixtures reutilizables, decoradores personalizados (`@retry`, `@screenshot_on_fail`) y configuración centralizada por entorno.
- **Pruebas dual-browser** (Opera + Chromium) parametrizadas en una sola ejecución sin duplicar código.
- **Pipeline de bugs completo**: detección → reporte Excel → CSV para Jira → adjunto de capturas vía REST API → transición de estados automática.
- **Cobertura de técnicas QA**: Análisis de Valores Límite (BVA), Partición por Equivalencia, checklist funcional, happy path y pruebas de regresión.
- **Acceso a base de datos** PostgreSQL en entorno remoto vía túnel SSH para validación de estado de datos.
- **Código mantenible**: sin credenciales hardcodeadas, `.env`-driven, compatible con CI/CD.

---

## Cobertura

| Suite | Alcance | Plataforma | Casos | Bugs |
|-------|---------|-----------|------:|-----:|
| T2 – Checklist Web | 58 verificaciones funcionales | Opera + Chrome | 116 | 31 |
| T2 – Validación de Datos | 39 casos límite/equivalencia (BVA) | Opera + Chrome | 78 | 18 |
| T3 – Casos Móvil | Flujos de notificaciones push | Android (Appium) | 8 | 8 |
| T4 – Checklist API | 47 endpoints REST | HTTP | 47 | 23 |
| T5 – Happy Path | Ciclo de vida completo del pedido | Opera + Chrome | 2 | 1 |
| **Total** | | | **251** | **81** |

---

## Stack tecnológico

| Capa | Herramientas |
|------|-------------|
| Lenguaje | Python 3.11+ |
| Framework de pruebas | pytest · pytest-html · pytest-ordering · pytest-metadata |
| UI Web | Playwright (Opera + Chromium) |
| REST API | requests |
| Móvil | Appium-Python-Client · emulador Android |
| Base de datos | psycopg3 · paramiko · sshtunnel · pexpect |
| Reportes | openpyxl · Pillow |
| Gestión de bugs | Jira REST API v3 |
| Configuración | python-dotenv |

---

## Flujo general

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│  pytest run  │───▶│ Excel results│───▶│ bug_reporter │───▶│ Jira import │
│  (UI/API/   │    │ results/*.xlsx│    │ CSV + manifest│    │ via REST API│
│   mobile)   │    └──────────────┘    └──────────────┘    └─────────────┘
│             │
│ screenshots │───▶  screenshots/<suite>/<test>.png
└─────────────┘
```

---

## Estructura del proyecto

```
urban_scooter/
├── components/
│   ├── api/              # Clientes HTTP por recurso (courier, orders)
│   ├── web/              # Page Object Model — Playwright
│   └── mobile/           # Page Object Model — Appium
├── config/
│   └── settings.py       # Configuración centralizada desde .env
├── models/
│   └── test_entities.py  # Dataclasses: Status, CourierCredentials, OrderResult
├── utils/
│   ├── db_connector.py   # PostgreSQL vía túnel SSH (pexpect interactivo)
│   ├── decorators.py     # @screenshot_on_fail · @retry · @log_step
│   ├── excel_handler.py  # Lectura/escritura de resultados (openpyxl)
│   ├── logger.py
│   ├── screenshot_manager.py
│   └── server_manager.py
├── tests/
│   ├── conftest.py
│   ├── test_tarea_2_checklist.py
│   ├── test_tarea_2_validacion_datos.py
│   ├── test_tarea_3_cases.py
│   ├── test_tarea_4_checklist.py
│   └── test_tarea_5_happy_path.py
├── excel_templates/      # Plantillas Excel de origen (solo lectura)
├── bug_reporter.py       # Genera CSV + JSON manifest para Jira
├── jira_uploader.py      # Adjunta capturas a issues vía REST API
├── jira_bug_updater.py   # Actualiza issues: descripción, captura, estado
├── launcher.py           # GUI tkinter para ejecutar suites y exportar bugs
├── pytest.ini
├── requirements.txt
├── .env.example
└── README.md
```

---

## Instalación

### Requisitos previos

- Python 3.11+
- Opera Browser
- Android emulator + Appium Server *(solo para pruebas móviles)*
- Clave SSH configurada para el contenedor TripleTen

### Pasos

```bash
git clone <repo-url>
cd urban_scooter

python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\Activate.ps1    # Windows

pip install -r requirements.txt
playwright install chromium
```

### Variables de entorno

```bash
cp .env.example .env
# Completar: SERVER_BASE_URL, DB_*, JIRA_*, SSH_*
```

Ver `.env.example` para la lista completa de variables y sus descripciones.

---

## Ejecución de pruebas

```bash
# Suite individual
pytest tests/test_tarea_2_validacion_datos.py -v

# Todas las suites
pytest tests/ -v

# Con reporte HTML
pytest tests/ -v --html=results/report.html
```

> Las pruebas móviles requieren el servidor Appium activo en `APPIUM_SERVER` con un emulador conectado.

---

## Exportación a Jira

```bash
# 1. Ejecutar pruebas  →  resultados en results/*.xlsx

# 2. Generar reporte de bugs
python bug_reporter.py
#    → results/bugs_jira_<ts>.csv
#    → results/bug_manifest_<ts>.json

# 3. Importar CSV en Jira (Issues > Importar CSV)
#    Exportar de vuelta el CSV con Issue Keys asignados

# 4. Subir capturas
python jira_uploader.py "Jira_export.csv" "results/bug_manifest_<ts>.json"

# 5. Actualizar issues existentes (descripción + captura + estado)
python jira_bug_updater.py [--dry-run]
```

O usar el lanzador con interfaz gráfica:

```bash
python launcher.py
```

---

## Notas de arquitectura

- **Dual-browser** — T2 y T5 parametrizan Opera y Chrome en una sola ejecución mediante fixtures de pytest.
- **Escritura incremental en Excel** — resultados persistidos tras cada prueba; sin pérdida de datos ante interrupciones.
- **Acceso DB por SSH** — sesión `pexpect` interactiva sin port forwarding local.
- **Jira REST API v3** — pipeline completo: creación de issue → adjuntar captura → transición de estado.
- **Patrón POM** — capas web y móvil completamente desacopladas de la lógica de pruebas.

---

## Seguridad

- Todas las credenciales y URLs se cargan exclusivamente desde `.env` (sin valores hardcodeados).
- `.env` está en `.gitignore`; solo `.env.example` (sin valores reales) se incluye en el repositorio.
- Las credenciales de courier usan el patrón `test_courier_<uuid>` para garantizar unicidad y no contaminar datos reales.
