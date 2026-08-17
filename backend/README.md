# Contractor AI — Backend

FastAPI service over public procurement data from 4 countries (Paraguay,
Colombia, Costa Rica, República Dominicana — see the root README for the
full picture). Read-only contract/anomaly endpoints, a live statistical
comparison for contracts that aren't in the dataset yet, an aggregated
dashboard, and a public citizen-reports channel. See
[`docs/architecture/PLANNING.md`](../docs/architecture/PLANNING.md) for the
original design doc and [`../docs/adr/`](../docs/adr/) for architecture
decisions.

## Run locally

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; use .venv/bin/activate on Linux/Mac
pip install -r requirements.txt

python scripts/migrate_dataset.py   # creates contractor.db (SQLite) and loads Paraguay's contracts
uvicorn app.main:app --reload --port 8000
```

Interactive API docs (OpenAPI): http://localhost:8000/docs

To pull in the other 3 countries' live data, run the matching
`scripts/ingest_*_live.py` script for each, then
`scripts/compute_statistical_anomalies.py` to score every contract that
doesn't have an anomaly signal yet (idempotent — safe to re-run after
ingesting more data).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests run against an isolated, throwaway SQLite file
(`backend/tests/conftest.py` sets `DATABASE_URL` before any app module is
imported) — never against whatever `DATABASE_URL` is configured in your
`.env`, even if that happens to be a real Postgres instance.

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./contractor.db` | Any SQLAlchemy-compatible DSN. Schema is engine-agnostic (`app/models.py`) — SQLite and Postgres both work with no code changes. |
| `CORS_ALLOW_ORIGINS` | `["http://localhost:3000"]` | JSON list. The deployed Vercel frontend and any `localhost`/`127.0.0.1` port are additionally allowed via a regex in `app/main.py`, regardless of this value. |
| `API_KEY_HEADER_NAME` | `X-API-Key` | Reserved for a future authenticated tier (`models.ApiKey` exists but no endpoint uses it yet). |

Local Postgres instead of SQLite (recommended for anything resembling
staging, see ADR 0001):

```bash
docker compose up -d   # from the repo root
export DATABASE_URL=postgresql+psycopg2://contractor:contractor@localhost:5432/contractor
python scripts/migrate_dataset.py
```

## API surface

- `GET /countries`, `GET /contracts`, `GET /contracts/{id}`, `GET /anomalies`
  — read-only, paginated, filterable.
- `POST /analyze/extract`, `POST /analyze/compare` — submit a contract
  that isn't ingested yet (PDF, link, or photo) and compare its amount
  statistically against similar ingested contracts. No live ML inference —
  see `app/analysis.py`'s module docstring for exactly what this does and
  doesn't do, deliberately.
- `GET /contracts/{id}/reports`, `POST /contracts/{id}/reports` — public,
  unauthenticated citizen comments on a contract (flag a concern, or add
  context). Rate-limited; see [`../SECURITY.md`](../SECURITY.md).
- `GET /dashboard/summary`, `GET /rankings/buyers`, `GET /export/contracts.csv`
  — aggregate metrics, an institution ranking, and a CSV export, all backed
  by `app/dashboard.py`.

Full request/response shapes: `/docs` (Swagger UI) or `/openapi.json`.

## Note on `amount_usd`

Paraguay's USD amounts are CPI-adjusted to the model pipeline's reference
year, not the nominal amount at the time of signing — see
`scripts/migrate_dataset.py`'s docstring for the numeric verification. This
is intentional (it keeps the real value and the predicted value on the same
basis for comparison) but worth remembering when displaying figures.
Colombia, Costa Rica, and República Dominicana don't have a verified
exchange rate per contract date, so their amounts are shown in their
original currency instead of being converted.
