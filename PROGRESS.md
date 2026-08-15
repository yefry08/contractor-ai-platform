# PROGRESS

Estado vivo del desarrollo de Contractor AI (plataforma pública). Leer al inicio de
cada iteración; actualizar al final con qué se completó, qué falta y el siguiente
paso concreto. Ver `CHANGELOG.md` para el historial y `docs/adr/` para decisiones
de arquitectura.

## Completado

- **Fase 0 — Planificación** (2026-08-14): arquitectura, stack, modelo de datos,
  roadmap, riesgos, estrategia de validación y plan de despliegue documentados en
  [`docs/architecture/PLANNING.md`](docs/architecture/PLANNING.md). Decisiones
  clave registradas en `docs/adr/0001` a `0003`.
- **Repositorio git inicializado** (2026-08-15): commit inicial con el prototipo
  existente tal cual estaba + los entregables de Fase 0.
- **Fase 1 — backend** (2026-08-15): esquema SQLAlchemy (`backend/app/models.py`),
  script de migración (`backend/scripts/migrate_dataset.py`) y API FastAPI de solo
  lectura (`/countries`, `/contracts`, `/contracts/{id}`, `/anomalies`) probada
  end-to-end contra SQLite local. Ver `backend/README.md`.
  - **Corrección importante encontrada durante la migración**: el dataset
    `Data/resultados finales/resultados.xlsx` (el que ya sirve al Streamlit en
    producción) tiene **5,282 filas, no 3.55M**. La cifra de 3.55M+ contratos
    mencionada en el pedido original no corresponde a este archivo — es
    probablemente el tamaño del corpus crudo de entrenamiento/exploración
    (`Data/records.csv` + `Data/zips/`, ~210MB de CSVs OCDS sin procesar). Falta
    confirmar con el equipo original a qué corresponde exactamente esa cifra; no
    se asumió nada y se migró el archivo real tal como está.
  - **Corrección de unidades verificada numéricamente**: la columna
    `value_million_dolar` del archivo dice "million" pero en realidad está en
    miles de USD ajustados por CPI (verificado fila por fila contra
    `Code/pre_procesamiento.ipynb`: `value_million_dolar == (monto/tipo_cambio/CPI_avg)/1000`,
    diferencia < 1e-9). El script de migración lo corrige explícitamente — ver el
    docstring de `backend/scripts/migrate_dataset.py` para el detalle. Esto es
    relevante porque un error de escala de 1000x en montos es exactamente el tipo
    de cosa que una herramienta anti-corrupción no puede darse el lujo de mostrar
    mal.
- **Fase 1 — frontend**: Next.js mínimo (`frontend/`) con listado de contratos,
  explorador de anomalías y detalle de contrato, consumiendo la API. Instalación
  de dependencias en curso/verificación pendiente — ver siguiente sección si sigue
  bloqueado al leer esto.

## Bloqueado — pendiente de credencial/decisión humana

- **Clave de API de OpenRouter** (o proveedor LLM equivalente) — necesaria para
  cualquier tarea de extracción/resumen vía LLM (ADR 0002). No simular respuestas
  de LLM sin esta clave.
- **Credenciales de object storage de producción** (S3/MinIO) — necesarias antes de
  poder desplegar el flujo de carga multimodal (Fase 3) fuera de dev local.
- **Confirmación de alcance de países para Fase 2** — más allá de Paraguay y
  Colombia (ya presentes en el prototipo), falta relevar qué otros países del
  listado (R. Dominicana, Argentina, Perú, Chile, Ecuador, Honduras, Costa Rica,
  Nicaragua) tienen API OCDS suficientemente limpia vs. requieren scraper (Fase 4).
  Esto es una decisión de alcance, no una credencial, pero bloquea planificar el
  detalle de Fase 2 conector por conector.
- **Postgres/Docker no disponibles en este entorno de desarrollo**: no hay
  `docker`, `psql` ni `pg_ctl` instalados en la máquina donde se corrió Fase 1.
  El backend usa SQLite localmente (`backend/contractor.db`, gitignored) con
  `DATABASE_URL` configurable — el esquema es agnóstico del motor, así que migrar
  a Postgres real (`docker-compose.yml` ya en la raíz) es solo cuestión de
  levantar el contenedor y correr `migrate_dataset.py` de nuevo. No usar SQLite en
  producción (ver ADR 0001 / PLANNING.md stack).

## Siguiente paso concreto

Verificar que el frontend (`frontend/`) levanta y muestra datos reales del
backend (`npm run dev`, backend corriendo en :8000). Si ya funciona al leer esto:
pasar a Fase 2 (ingesta multi-país en vivo, ver roadmap en PLANNING.md) — el
primer paso ahí es relevar qué países más allá de Paraguay/Colombia tienen API
OCDS limpia (bloqueo de alcance de arriba).

## Notas de operación

- El único gate humano explícito del flujo autónomo es el **despliegue a
  producción** (ver §7 del plan) — el resto de las fases puede avanzar sin
  aprobación paso a paso.
- No inventar ni simular credenciales, datos de países no verificados, ni
  resultados de modelos. Si falta algo, se registra arriba y se continúa con la
  siguiente tarea no bloqueada.
