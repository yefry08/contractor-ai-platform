"""Ingesta EN VIVO de Uruguay (ONCP - Oficina Nacional de Contrataciones Públicas).

Fuente: Oficina Nacional de Contrataciones Públicas (ONCP) de Uruguay.
Integración con el portal de contrataciones públicas de Uruguay para datos
de compras estatales.

Características:
- Ingesta idempotente usando external_id (ID de contrato único)
- Soporte para datos en español (Uruguay)
- Mapeo de campos a esquema OCDS interno
- Paginación automática con pausa entre requests
- Conversión de moneda (UYU a USD)
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

COUNTRY_CODE = "UY"
# API endpoint verificado 2026-09-09: Portal ONCP Uruguay
BASE_URL = "https://www.oncp.gub.uy/api/contratos"
PAGE_SIZE = 1000
MAX_RECORDS = 5000
REQUEST_DELAY_SECONDS = 0.5


def fetch_page(offset: int) -> list[dict]:
    """Fetch a page of contracts from ONCP API."""
    params = {
        "limit": PAGE_SIZE,
        "offset": offset,
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("results", []) if isinstance(data, dict) else data
    except Exception as e:
        print(f"✗ Error fetching page at offset {offset}: {e}")
        return []


def parse_date(value: str | None) -> str | None:
    """Parse Uruguayan date format (YYYY-MM-DD or DD/MM/YYYY)."""
    if not value:
        return None
    try:
        if "T" in value:  # ISO format
            return value.split("T")[0]
        if "-" in value and len(value) == 10:  # YYYY-MM-DD
            return value
        if "/" in value:  # DD/MM/YYYY
            parts = value.split("/")
            if len(parts) == 3:
                return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except Exception:
        pass
    return None


def to_float(value: str | int | float | None) -> float | None:
    """Convert string/int/float to float, handling None and invalid values."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def normalize(name: str | None) -> str:
    """Normalize buyer/supplier name to lowercase."""
    return (name or "").strip().lower()


def main():
    parser = argparse.ArgumentParser(description="Ingesta en vivo de Uruguay (ONCP).")
    parser.add_argument("--max-records", type=int, default=MAX_RECORDS)
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY_SECONDS)
    parser.add_argument("--test", action="store_true", help="Test mode: init country and exit")
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        # Initialize country if needed
        country = db.get(models.Country, COUNTRY_CODE)
        if country is None:
            country = models.Country(
                code=COUNTRY_CODE,
                name="Uruguay",
                ocds_portal_url="https://www.oncp.gub.uy",
                schema_variant="oncp-derivado",
                ingestion_method="api",
                active=True,
            )
            db.add(country)
            db.flush()
            print(f"✓ Country initialized: {country.name} ({country.code})")
        else:
            print(f"✓ Country exists: {country.name} ({country.code})")

        if args.test:
            db.commit()
            return

        # Initialize data source
        source = models.DataSource(
            country_code=COUNTRY_CODE,
            source_type="api",
            base_url=BASE_URL,
            terms_of_use_notes=(
                "Portal ONCP (Oficina Nacional de Contrataciones Públicas) - "
                "Datos públicos de contrataciones estatales de Uruguay. "
                "API pública sin token requerido. Verificado 2026-09-09."
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

        # Ingest contracts
        buyers_by_key: dict[str, models.Buyer] = {}
        ingested = 0
        failed = 0
        offset = 0

        print(f"\n📥 Ingesting contracts from {BASE_URL}...")
        print(f"   Max records: {args.max_records}, Delay: {args.delay}s\n")

        while ingested < args.max_records:
            records = fetch_page(offset)
            if not records:
                print("✓ Reached end of dataset")
                break

            for record in records:
                if ingested >= args.max_records:
                    break

                try:
                    # Extract fields (field names vary by API version)
                    contract_id = str(record.get("id") or record.get("contrato_id") or uuid.uuid4())
                    buyer_name = record.get("unidad_contratante", record.get("buyer", "Desconocido"))
                    contract_title = record.get("objeto", record.get("titulo", "Sin título"))
                    amount = to_float(record.get("monto", record.get("amount")))
                    award_date_str = record.get("fecha_firma", record.get("award_date"))
                    award_date = parse_date(award_date_str)

                    # Get or create buyer
                    buyer_key = normalize(buyer_name)
                    buyer = buyers_by_key.get(buyer_key)
                    if buyer is None and buyer_key:
                        buyer = models.Buyer(
                            id=str(uuid.uuid4()),
                            country_code=COUNTRY_CODE,
                            external_id=None,
                            name=buyer_name,
                            normalized_name=buyer_key,
                        )
                        db.add(buyer)
                        buyers_by_key[buyer_key] = buyer

                    # Check if contract already ingested (idempotent)
                    existing = db.execute(
                        models.select(models.Contract).where(
                            models.Contract.country_code == COUNTRY_CODE,
                            models.Contract.external_id == contract_id,
                        )
                    ).scalar_one_or_none()

                    if existing:
                        continue  # Skip if already ingested

                    # Create contract record
                    contract = models.Contract(
                        id=str(uuid.uuid4()),
                        ocid=None,
                        external_id=contract_id,
                        country_code=COUNTRY_CODE,
                        source_id=source.id,
                        buyer_id=buyer.id if buyer else None,
                        title=str(contract_title)[:500],
                        description=record.get("descripcion", contract_title)[:2000],
                        category_code=record.get("categoria", None),
                        currency="UYU",
                        amount_original=amount,
                        amount_usd=amount * 0.025 if amount else None,  # Approximate UYU->USD conversion
                        award_date=datetime.fromisoformat(award_date).date() if award_date else None,
                        procurement_method=record.get("modalidad", None),
                        raw_ocds_json=record,
                        source_url=None,
                    )
                    db.add(contract)
                    ingested += 1

                except Exception as e:
                    failed += 1
                    print(f"⚠ Error processing record: {e}")
                    continue

            offset += PAGE_SIZE
            time.sleep(args.delay)

        db.commit()
        run.finished_at = datetime.utcnow()
        run.status = "completed"
        run.records_ingested = ingested
        run.records_failed = failed
        db.commit()

        print(f"\n✓ Ingestion complete:")
        print(f"   Ingested: {ingested}")
        print(f"   Failed: {failed}")
        print(f"   Total: {ingested + failed}")

    except Exception as e:
        db.rollback()
        print(f"✗ Fatal error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
