"""Ingesta EN VIVO de Colombia (esto sí es Fase 2, a diferencia de
migrate_colombia.py que carga en bloque un dataset ya procesado por un
tercero).

Fuente verificada el 2026-08-15: el portal oficial de datos abiertos del
gobierno colombiano, datos.gov.co, publica el dataset "SECOP II - Contratos
Electrónicos" (id `jbjy-vk9h`) sobre una API Socrata (SODA) pública, sin
necesidad de token para volúmenes moderados. Verificado en vivo antes de
escribir este script:

    curl "https://www.datos.gov.co/api/views/jbjy-vk9h.json"
    -> rowsUpdatedAt = 2026-08-15 08:17:30 UTC (actualizado el mismo día)
    -> ~5.95 millones de contratos totales

Esto reemplaza el intento anterior de usar la API OCDS "oficial" de Colombia
Compra Eficiente, cuyo endpoint real nunca se pudo verificar (ver
PROGRESS.md) -- datos.gov.co sí tiene URL, formato y disponibilidad
verificables en el momento de escribir este script.

No es formato OCDS nativo (es tabular/Socrata), así que se mapea campo a
campo al mismo esquema interno que ya usan Paraguay y Colombia (bulk). A
diferencia de migrate_colombia.py, esta fuente SÍ trae fecha real de firma
(`fecha_de_firma`) y un ID de contrato único (`id_contrato`) -- se usa ese ID
para hacer la ingesta idempotente (no duplica si se corre de nuevo).

No incluye predicción del modelo NLP: no hay pesos entrenados de BERT/XGBoost
para inferencia en vivo en este entorno (eso es un problema de Fase 2 en sí,
no algo que se deba simular). Los contratos quedan sin `Prediction`/`Anomaly`
hasta que exista un pipeline de inferencia -- igual de válidos para buscar/
navegar, simplemente no tienen todavía score de anomalía.

No se trae todo el dataset (5.95M filas sería irresponsable para una corrida
manual de este script). Por defecto trae los `MAX_RECORDS` contratos más
recientes por fecha de firma, paginando de a `PAGE_SIZE`. Sin token de app de
Socrata (no se tiene una credencial registrada, ver PROGRESS.md) el límite de
uso es más bajo -- se agrega una pausa entre páginas para no abusar de un
servicio público gratuito.
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

DATASET_ID = "jbjy-vk9h"
BASE_URL = f"https://www.datos.gov.co/resource/{DATASET_ID}.json"
COUNTRY_CODE = "CO"
PAGE_SIZE = 1000
# Techo por defecto, no un limite de la fuente: el dataset tiene ~5.95M filas.
# Se sube con --max-records. La corrida es idempotente (se saltean los
# `id_contrato` ya presentes), asi que re-correr con un techo mayor suma lo
# que falta en vez de duplicar.
MAX_RECORDS = 5000
REQUEST_DELAY_SECONDS = 0.3


def fetch_page(offset: int) -> list[dict]:
    params = {
        "$limit": PAGE_SIZE,
        "$offset": offset,
        "$order": "fecha_de_firma DESC",
        "$where": "fecha_de_firma IS NOT NULL",
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "")).date()
    except ValueError:
        return None


def to_float(value: str | None) -> float | None:
    if value in (None, "", "No Definido", "No definido"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def normalize(name: str | None) -> str:
    return (name or "").strip().lower()


def main():
    parser = argparse.ArgumentParser(description="Ingesta en vivo de Colombia (datos.gov.co / SECOP II).")
    parser.add_argument("--max-records", type=int, default=MAX_RECORDS)
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY_SECONDS)
    args = parser.parse_args()
    max_records = args.max_records
    delay = args.delay

    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        country = db.get(models.Country, COUNTRY_CODE)
        if country is None:
            country = models.Country(
                code=COUNTRY_CODE,
                name="Colombia",
                ocds_portal_url="https://www.colombiacompra.gov.co/",
                schema_variant="secop-ii-derivado",
                ingestion_method="manual",
                active=True,
            )
            db.add(country)
            db.flush()

        source = models.DataSource(
            country_code=COUNTRY_CODE,
            source_type="api",
            base_url=BASE_URL,
            terms_of_use_notes=(
                "Portal oficial de datos abiertos del gobierno de Colombia "
                "(datos.gov.co), dataset 'SECOP II - Contratos Electronicos' "
                f"({DATASET_ID}), API publica Socrata/SODA sin token. No es "
                "formato OCDS nativo -- se mapea campo a campo. Verificado "
                "en vivo el 2026-08-15, dataset actualizado el mismo dia."
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

        existing_ids = {
            row[0]
            for row in db.query(models.Contract.external_id)
            .filter(models.Contract.country_code == COUNTRY_CODE, models.Contract.external_id.isnot(None))
            .all()
        }

        buyers_by_key: dict[str, models.Buyer] = {}
        ingested = 0
        skipped_duplicate = 0
        failed = 0
        offset = 0

        while offset < max_records:
            try:
                rows = fetch_page(offset)
            except Exception as exc:  # noqa: BLE001
                print(f"  fallo al pedir offset={offset}: {exc}", file=sys.stderr)
                break

            if not rows:
                break

            for row in rows:
                try:
                    id_contrato = row.get("id_contrato")
                    if id_contrato and id_contrato in existing_ids:
                        skipped_duplicate += 1
                        continue

                    buyer_name = row.get("nombre_entidad")
                    buyer_key = normalize(buyer_name)
                    buyer = None
                    if buyer_key:
                        buyer = buyers_by_key.get(buyer_key)
                        if buyer is None:
                            buyer = models.Buyer(
                                id=str(uuid.uuid4()),
                                country_code=COUNTRY_CODE,
                                external_id=None,
                                name=buyer_name or "Desconocido",
                                normalized_name=buyer_key,
                            )
                            db.add(buyer)
                            buyers_by_key[buyer_key] = buyer

                    descripcion = row.get("descripcion_del_proceso") or row.get("objeto_del_contrato")
                    url_info = row.get("urlproceso") or {}
                    source_url = url_info.get("url") if isinstance(url_info, dict) else None

                    contract_id = str(uuid.uuid4())
                    contract = models.Contract(
                        id=contract_id,
                        ocid=None,
                        external_id=id_contrato,
                        country_code=COUNTRY_CODE,
                        source_id=source.id,
                        buyer_id=buyer.id if buyer else None,
                        title=descripcion,
                        description=descripcion,
                        category_code=row.get("tipo_de_contrato"),
                        currency="COP",
                        amount_original=to_float(row.get("valor_del_contrato")),
                        amount_usd=None,
                        award_date=parse_date(row.get("fecha_de_firma")),
                        procurement_method=row.get("modalidad_de_contratacion"),
                        raw_ocds_json={k: v for k, v in row.items() if v not in (None, "") and not isinstance(v, dict)},
                        source_url=source_url,
                    )
                    db.add(contract)

                    db.add(
                        models.Provenance(
                            entity_type="contract",
                            entity_id=contract_id,
                            source_id=source.id,
                            fetched_at=datetime.utcnow(),
                            source_hash=None,
                            raw_payload_uri=f"{BASE_URL}?id_contrato={id_contrato}",
                        )
                    )

                    if id_contrato:
                        existing_ids.add(id_contrato)
                    ingested += 1
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(f"  fila fallida: {exc}", file=sys.stderr)

            db.commit()
            offset += PAGE_SIZE
            print(f"  ... offset {offset}: {ingested} contratos nuevos, {skipped_duplicate} ya existian")
            time.sleep(delay)

        run.finished_at = datetime.utcnow()
        run.records_ingested = ingested
        run.records_failed = failed
        run.status = "completed"
        db.commit()

        print(
            f"Ingesta en vivo Colombia completa: {ingested} contratos nuevos, "
            f"{skipped_duplicate} duplicados omitidos, {failed} fallidos."
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
