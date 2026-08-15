# Contractor AI — Backend (Fase 1)

API de solo lectura sobre el dataset histórico de Paraguay ya procesado por el
prototipo (BERT + XGBoost). Ver [`docs/architecture/PLANNING.md`](../docs/architecture/PLANNING.md)
para el diseño completo.

## Arrancar en local

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; usar .venv/bin/activate en Linux/Mac
pip install -r requirements.txt

python scripts/migrate_dataset.py   # crea contractor.db (SQLite) y carga los 5,282 contratos
uvicorn app.main:app --reload --port 8000
```

Documentación interactiva (OpenAPI): http://localhost:8000/docs

## Base de datos

Por defecto usa SQLite (`contractor.db`) porque este entorno de desarrollo no
tenía Docker/Postgres disponible (ver `PROGRESS.md` en la raíz). Para usar
Postgres (recomendado para staging/producción, ver ADR 0001):

```bash
pip install psycopg2-binary
export DATABASE_URL=postgresql+psycopg2://contractor:contractor@localhost:5432/contractor
docker compose up -d   # desde la raíz del repo
python scripts/migrate_dataset.py
```

El esquema (`app/models.py`) es agnóstico del motor — SQLite y Postgres
funcionan sin cambios de código.

## Nota sobre `amount_usd`

Los montos en USD están ajustados por CPI al año de referencia que usaba el
pipeline original del modelo, no son el monto nominal al momento de la firma
del contrato. Ver el docstring de `scripts/migrate_dataset.py` para la
verificación numérica de esta conversión — es intencional (así el valor real y
el valor predicho quedan en la misma base para poder compararse), pero hay que
tenerlo presente al mostrar cifras al usuario final.
