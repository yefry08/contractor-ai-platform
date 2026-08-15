# Changelog

Formato libre, orden cronológico inverso (más reciente arriba). Referencia a
`docs/adr/` para el razonamiento detrás de decisiones de arquitectura.

## 2026-08-15 — Fase 1: backend + frontend mínimo sobre el dataset existente

- Inicializado el repositorio git (no existía) con un commit inicial del
  prototipo tal cual estaba + los entregables de Fase 0.
- Añadido `backend/` (FastAPI + SQLAlchemy 2.0): modelos del esquema de Fase 1
  (`app/models.py`), API de solo lectura `/countries`, `/contracts`,
  `/contracts/{id}`, `/anomalies` (`app/main.py`), y script de migración
  (`scripts/migrate_dataset.py`) que carga `Data/resultados finales/resultados.xlsx`
  a la base de datos. Probado end-to-end contra SQLite local: 5,282 contratos
  migrados, 0 fallidos.
- Corregidos dos hallazgos durante la migración (documentados en el docstring
  del script y en `PROGRESS.md`):
  1. El dataset de resultados tiene 5,282 filas, no 3.55M como se mencionó en el
     pedido original — esa cifra probablemente corresponde al corpus crudo de
     entrenamiento (`Data/records.csv` + `Data/zips/`), no al archivo de
     resultados ya procesado. Falta confirmar con el equipo original.
  2. La columna `value_million_dolar` del archivo fuente está mal nombrada: el
     valor real está en miles de USD ajustados por CPI, no en millones
     (verificado numéricamente contra `Code/pre_procesamiento.ipynb`). El script
     de migración corrige la escala al cargar los datos.
- Añadido `frontend/` (Next.js + TypeScript, App Router): listado/búsqueda de
  contratos, explorador de anomalías, vista de detalle por contrato — todo
  consumiendo la API del backend, sin datos hardcodeados.
- Añadido `docker-compose.yml` con Postgres para cuando haya Docker disponible
  (no lo había en este entorno de desarrollo — ver `PROGRESS.md`); el esquema de
  `backend/app/models.py` es agnóstico del motor (SQLite en dev, Postgres en
  producción vía `DATABASE_URL`).
- Verificado el frontend en navegador contra el backend real (no solo `curl` a
  la API) y encontrado ahí un bug que la prueba de API sola no mostraba: la
  migración marcaba el 100% de los contratos como "anomalía" porque no aplicaba
  ningún corte a `perc_error`. Corregido con un umbral provisional y documentado
  (`ABS_PERC_ERROR_THRESHOLD = 1.0` en `migrate_dataset.py`) — de 5,282 pasó a
  696 contratos marcados. Ver `PROGRESS.md` para el detalle.

## 2026-08-14 — Fase 0: Planificación de la plataforma pública

- Añadido `docs/architecture/PLANNING.md`: diagrama de arquitectura (mermaid),
  stack técnico recomendado, modelo de datos, roadmap por fases (1-6), riesgos y
  mitigaciones, estrategia de validación de precisión, y plan de despliegue.
- Añadidos `docs/adr/0001` (plataforma pública multi-país en vez de extender el
  Streamlit interno), `0002` (LiteLLM sobre OpenRouter para enrutamiento de LLM),
  `0003` (modelo estadístico interno independiente como validación cruzada del
  NLP/LLM).
- Añadido `PROGRESS.md` como estado vivo del desarrollo, con bloqueos registrados
  (clave OpenRouter, credenciales de object storage, alcance de países para Fase 2,
  inicialización de git) y el siguiente paso concreto (Fase 1: migrar el dataset
  existente de 3.55M contratos a Postgres + API de solo lectura).
- No se modificó código del prototipo existente (`main.py`, notebooks en `Code/`,
  `Models/modelxgboost.pkl`) — esta iteración fue puramente de planificación.
