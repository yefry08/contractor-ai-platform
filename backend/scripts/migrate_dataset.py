"""Migra el dataset ya procesado del prototipo (Data/resultados finales/resultados.xlsx)
a las tablas de Fase 1 (ver docs/architecture/PLANNING.md §3).

No hace ingesta en vivo ni llama a ningún LLM: es una carga batch de datos que el
prototipo Streamlit ya había calculado (BERT + XGBoost). Todo el registro se
preserva sin tocar en `raw_ocds_json` para no perder información al mapear.

Nota importante sobre unidades (verificado numéricamente contra el archivo fuente,
no asumido):
    La columna `value_million_dolar` del archivo original está mal nombrada: pese a
    decir "million", el valor real es (monto en moneda local / tipo de cambio anual
    promedio) / CPI_promedio_del_año / 1000 — es decir, está en MILES de dólares
    ajustados por inflación (CPI) a un año de referencia, no en millones nominales.
    Se verificó fila por fila: value_million_dolar == (amount/exchange_rate/cpi_avg)/1000
    con una diferencia menor a 1e-9. Lo mismo aplica a `predict`, `range-` y `range+`,
    que salen del mismo pipeline (Code/pre_procesamiento.ipynb).

    Por eso este script multiplica esas columnas por 1000 al migrarlas a
    `amount_usd` / `predicted_value_usd` — así quedan en dólares reales ajustados
    por CPI, en la MISMA base entre el valor real y el valor predicho (condición
    necesaria para que la comparación de sobre/subcosto tenga sentido). El monto
    original sin tocar (moneda local) se preserva en `amount_original`/`currency`.

    Las columnas crudas `range-`/`range+`/`in_range` del archivo resultaron
    inconsistentes con la definición que usa el propio `main.py` del prototipo
    (que las redefine sobre la marcha), así que NO se usan para decidir qué es
    anomalía. En su lugar se expone `perc_error` (fórmula verificada:
    perc_error == (valor_real - predicho) / predicho) como score continuo, y se
    deja la curación de un umbral formal para la Fase 5 (ver ADR 0003).
"""

import hashlib
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

SOURCE_XLSX = Path(__file__).resolve().parent.parent.parent / "Data" / "resultados finales" / "resultados.xlsx"
COUNTRY_CODE = "PY"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value[:10]).date()
        except ValueError:
            return None
    return None


def normalize(name: str | None) -> str:
    return (name or "").strip().lower()


def main():
    if not SOURCE_XLSX.exists():
        raise SystemExit(f"No se encontró el archivo fuente: {SOURCE_XLSX}")

    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        country = db.get(models.Country, COUNTRY_CODE)
        if country is None:
            country = models.Country(
                code=COUNTRY_CODE,
                name="Paraguay",
                ocds_portal_url="https://www.contrataciones.gov.py/datos/",
                schema_variant="ocds-dncp",
                ingestion_method="manual",
                active=True,
            )
            db.add(country)
            db.flush()

        source = models.DataSource(
            country_code=COUNTRY_CODE,
            source_type="manual_upload",
            base_url=None,
            terms_of_use_notes=(
                "Dataset historico ya procesado por el prototipo (BERT+XGBoost), "
                "cargado en batch para Fase 1. No es una ingesta en vivo del "
                "portal DNCP."
            ),
            last_ingested_at=datetime.utcnow(),
        )
        db.add(source)
        db.flush()

        run = models.IngestionRun(
            country_code=COUNTRY_CODE,
            source_id=source.id,
            started_at=datetime.utcnow(),
            status="running",
        )
        db.add(run)
        db.flush()

        source_hash = sha256_of_file(SOURCE_XLSX)

        wb = openpyxl.load_workbook(SOURCE_XLSX, read_only=True)
        ws = wb["Sheet1"]
        rows = ws.iter_rows(min_row=1, values_only=True)
        header = next(rows)
        col = {name: i for i, name in enumerate(header)}

        buyers_by_key: dict[str, models.Buyer] = {}
        ingested = 0
        failed = 0

        for row in rows:
            try:
                buyer_id = row[col["compiledRelease/buyer/id"]]
                buyer_name = row[col["compiledRelease/buyer/name"]]
                buyer_key = buyer_id or normalize(buyer_name)

                buyer = None
                if buyer_key:
                    buyer = buyers_by_key.get(buyer_key)
                    if buyer is None:
                        buyer = models.Buyer(
                            country_code=COUNTRY_CODE,
                            external_id=str(buyer_id) if buyer_id else None,
                            name=buyer_name or "Desconocido",
                            normalized_name=normalize(buyer_name),
                        )
                        db.add(buyer)
                        db.flush()
                        buyers_by_key[buyer_key] = buyer

                raw = {str(k): v for k, v in zip(header, row) if v is not None}

                contract = models.Contract(
                    ocid=row[col["compiledRelease/ocid"]],
                    external_id=str(row[col["compiledRelease/id"]]) if row[col["compiledRelease/id"]] else None,
                    country_code=COUNTRY_CODE,
                    source_id=source.id,
                    buyer_id=buyer.id if buyer else None,
                    title=row[col["compiledRelease/tender/title"]],
                    description=row[col["compiledRelease/planning/budget/description"]]
                    or row[col["compiledRelease/tender/title"]],
                    category_code=row[col["compiledRelease/tender/mainProcurementCategory"]],
                    currency=row[col["compiledRelease/tender/value/currency"]],
                    amount_original=row[col["compiledRelease/tender/value/amount"]],
                    amount_usd=(row[col["value_million_dolar"]] * 1000) if row[col["value_million_dolar"]] is not None else None,
                    award_date=parse_date(row[col["compiledRelease/tender/awardPeriod/startDate"]] or row[col["compiledRelease/date"]]),
                    procurement_method=row[col["compiledRelease/tender/procurementMethod"]],
                    raw_ocds_json=raw,
                    source_url=None,
                )
                db.add(contract)
                db.flush()

                predict = row[col["predict"]]
                range_low = row[col["range-"]]
                range_high = row[col["range+"]]
                likelihood = row[col["likelihood"]]
                perc_error = row[col["perc_error"]]

                if predict is not None:
                    db.add(
                        models.Prediction(
                            contract_id=contract.id,
                            model_name="bert-multilingual-xgboost",
                            model_version="prototype-2024",
                            predicted_value_usd=predict * 1000,
                            range_low=(range_low * 1000) if range_low is not None else None,
                            range_high=(range_high * 1000) if range_high is not None else None,
                            likelihood_score=likelihood,
                        )
                    )

                if perc_error is not None and predict is not None:
                    db.add(
                        models.Anomaly(
                            contract_id=contract.id,
                            anomaly_type="overcost" if perc_error >= 0 else "undercost",
                            composite_score=abs(perc_error),
                            nlp_component=perc_error,
                            stat_component=None,
                            llm_narrative=None,
                            confidence=likelihood,
                            status="open",
                        )
                    )

                db.add(
                    models.Provenance(
                        entity_type="contract",
                        entity_id=contract.id,
                        source_id=source.id,
                        fetched_at=datetime.utcnow(),
                        source_hash=source_hash,
                        raw_payload_uri=str(SOURCE_XLSX),
                    )
                )

                ingested += 1
                if ingested % 500 == 0:
                    db.commit()
                    print(f"  ... {ingested} contratos migrados")

            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  fila fallida: {exc}", file=sys.stderr)

        db.commit()

        run.finished_at = datetime.utcnow()
        run.records_ingested = ingested
        run.records_failed = failed
        run.status = "completed"
        db.commit()

        print(f"Migración completa: {ingested} contratos, {failed} fallidos.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
