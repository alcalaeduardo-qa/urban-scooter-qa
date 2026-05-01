# Urban Scooter — Framework de Automatización QA

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![Pytest](https://img.shields.io/badge/Pytest-Framework-orange?logo=pytest&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Dual--Browser-green?logo=playwright&logoColor=white)
![Appium](https://img.shields.io/badge/Appium-Mobile-purple?logo=appium&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?logo=postgresql&logoColor=white)
![Jira](https://img.shields.io/badge/Jira-REST%20API-0052CC?logo=jira&logoColor=white)
![Cobertura](https://img.shields.io/badge/Cobertura-251%20casos%20%C2%B7%2081%20bugs-brightgreen)

---

Framework de automatización E2E para la plataforma de renta de scooters Urban Scooter.
251 casos · 81 bugs · Web, API, Mobile y Base de Datos.

> Desarrollado por **Eduardo Alcalá García** · QA Automation Engineer con background en ingeniería de calidad industrial
> 🔗 [LinkedIn](https://linkedin.com/in/eduardo-alcala-qa) · [Portafolio](https://alcalaeduardo-qa.github.io)

---

## Resumen

Este proyecto demuestra capacidad para diseñar e implementar un framework de QA desde cero, cubriendo la pirámide completa de pruebas en un producto real:

- 251 casos automatizados distribuidos en 5 suites (Web, API, Móvil, DB) con 81 bugs documentados y exportados a Jira.
- Arquitectura modular con Page Object Model, fixtures reutilizables, decoradores personalizados (`@retry`, `@screenshot_on_fail`) y configuración centralizada por entorno.
- Pruebas dual-browser (Opera + Chromium) parametrizadas en una sola ejecución sin duplicar código.
- Pipeline de bugs completo: detección → reporte Excel → CSV para Jira → adjunto de capturas vía REST API → transición de estados automática.
- Cobertura de técnicas QA: Análisis de Valores Límite (BVA), Partición por Equivalencia, checklist funcional, happy path y pruebas de regresión.
- Acceso a base de datos PostgreSQL en entorno remoto vía túnel SSH para validación de estado de datos.
- Código mantenible: sin credenciales hardcodeadas, `.env`-driven, compatible con CI/CD.

---

## Bugs Críticos Encontrados

Los defectos mas relevantes detectados durante la ejecucion del framework — ninguno era visible desde la interfaz de usuario sin validacion en base de datos o analisis del flujo de estados.

| Severidad | Componente | Descripcion | Como se detecto |
|---|---|---|---|
| Critico | Base de datos | Duplicacion de ordenes en PostgreSQL — una sola accion en la UI generaba dos registros identicos en la tabla de ordenes | Auditoria SQL: `SELECT COUNT(*) GROUP BY order_id HAVING COUNT(*) > 1` |
| Critico | Flujo de estados | Salto de estado 2 a 4 sin pasar por el estado 3 — el flujo de pedido omitia un paso del ciclo de vida | Correlacion entre accion de UI y estado real en DB via consulta directa |
| Alto | Seguridad backend | Contrasenas almacenadas sin hashing en ciertos flujos del sistema | Inspeccion directa de registros en PostgreSQL via tunel SSH |

> Estos bugs no eran detectables mediante testing manual de UI. Requirieron correlacion entre capas: interfaz, API y base de datos.

---

## Cobertura

| Suite | Alcance | Plataforma | Casos | Bugs |
|---|---|---|---|---|
| T2 – Checklist Web | 58 verificaciones funcionales | Opera + Chrome | 116 | 31 |
| T2 – Validacion de Datos | 39 casos limite/equivalencia (BVA) | Opera + Chrome | 78 | 18 |
| T3 – Casos Movil | Flujos de notificaciones push | Android (Appium) | 8 | 8 |
| T4 – Checklist API | 47 endpoints REST | HTTP | 47 | 23 |
| T5 – Happy Path | Ciclo de vida completo del pedido | Opera + Chrome | 2 | 1 |
| **Total** | | | **251** | **81** |

---

## Stack Tecnologico

| Capa | Herramientas |
|---|---|
| Lenguaje | Python 3.11+ |
| Framework de pruebas | pytest · pytest-html · pytest-ordering · pytest-metadata |
| UI Web | Playwright (Opera + Chromium) |
| REST API | requests |
| Movil | Appium-Python-Client · emulador Android |
| Base de datos | psycopg3 · paramiko · sshtunnel · pexpect |
| Reportes | openpyxl · Pillow |
| Gestion de bugs | Jira REST API v3 |
| Configuracion | python-dotenv |

---

## Flujo General

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

## Estructura del Proyecto

```
urban_scooter/
├── components/
│   ├── api/              # Clientes HTTP por recurso (courier, orders)
│   ├── web/              # Page Object Model — Playwright
│   └── mobile/           # Page Object Model — Appium
├── config/
│   └── settings.py       # Configuracion centralizada desde .env
├── models/
│   └── test_entities.py  # Dataclasses: Status, CourierCredentials, OrderResult
├── utils/
│   ├── db_connector.py   # PostgreSQL via tunel SSH (pexpect interactivo)
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
├── jira_uploader.py      # Adjunta capturas a issues via REST API
├── jira_bug_updater.py   # Actualiza issues: descripcion, captura, estado
├── launcher.py           # GUI tkinter para ejecutar suites y exportar bugs
├── pytest.ini
├── requirements.txt
├── .env.example
└── README.md
```

---

## Instalacion

### Requisitos previos

- Python 3.11+
- Opera Browser
- Android emulator + Appium Server (solo para pruebas moviles)
- Clave SSH configurada para el contenedor TripleTen

### Pasos

```bash
git clone https://github.com/alcalaeduardo-qa/urban-scooter-qa.git
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

## Ejecucion de Pruebas

```bash
# Suite individual
pytest tests/test_tarea_2_validacion_datos.py -v

# Todas las suites
pytest tests/ -v

# Con reporte HTML
pytest tests/ -v --html=results/report.html
```

Las pruebas moviles requieren el servidor Appium activo en `APPIUM_SERVER` con un emulador conectado.

---

## Exportacion a Jira

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

# 5. Actualizar issues existentes (descripcion + captura + estado)
python jira_bug_updater.py [--dry-run]
```

O usar el lanzador con interfaz grafica:

```bash
python launcher.py
```

---

## Notas de Arquitectura

- **Dual-browser** — T2 y T5 parametrizan Opera y Chrome en una sola ejecucion mediante fixtures de pytest.
- **Escritura incremental en Excel** — resultados persistidos tras cada prueba; sin perdida de datos ante interrupciones.
- **Acceso DB por SSH** — sesion pexpect interactiva sin port forwarding local.
- **Jira REST API v3** — pipeline completo: creacion de issue → adjuntar captura → transicion de estado.
- **Patron POM** — capas web y movil completamente desacopladas de la logica de pruebas.

---

## Seguridad

- Todas las credenciales y URLs se cargan exclusivamente desde `.env` (sin valores hardcodeados).
- `.env` esta en `.gitignore`; solo `.env.example` (sin valores reales) se incluye en el repositorio.
- Las credenciales de courier usan el patron `test_courier_<uuid>` para garantizar unicidad y no contaminar datos reales.
