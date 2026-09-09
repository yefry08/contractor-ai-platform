"""Ingesta de Uruguay (ARCE — Agencia Reguladora de Compras Estatales).

Fuente verificada el 2026-09-09 contra el servicio real. Uruguay publica sus
compras en **OCDS 1.1 nativo**, que es justo el estándar sobre el que está
construido este proyecto, así que acá no hace falta mapear campo a campo
desde un formato tabular ajeno como en Colombia o Brasil.

Los datos NO salen de una API REST de contratos (no existe tal endpoint: el
dominio oncp.gub.uy que este archivo usaba antes ni siquiera resuelve). Salen
del catálogo de datos abiertos, dataset `arce-datos-historicos-de-compras`,
que expone un ZIP por año desde 2002 hasta hoy. Este script resuelve la URL
de cada año por la API de CKAN en vez de hardcodearla, para que un cambio de
UUID del recurso no lo rompa en silencio.

Forma real de los datos, comprobada sobre ocds-2025.zip (27 MB, 8.795
releases sólo en enero):

    ZIP -> AAAA/a-MM-AAAA.json -> {"version":"1.1", "releases":[...]}
    release: ocid, id, date, tag, buyer{id,name}, awards[], parties[]
    award:   id, title, date, status, suppliers[], items[]
    item:    quantity, classification{description,scheme}, unit.value{amount,currency}

Dos detalles que sólo se ven mirando los datos:

1. El monto NO está en `award.value` (ese campo no existe acá). Está por
   ítem, en `unit.value.amount`, y hay que multiplicarlo por `quantity`.
   609 de ~11.500 adjudicaciones de enero directamente no tienen ítems, o
   sea que no tienen monto: quedan con amount_original en None en vez de 0,
   que significaría "salió gratis".

2. Es multimoneda: UYU manda, pero también hay USD, EUR y UYI (unidad
   indexada). El 0,14% de las adjudicaciones mezcla monedas dentro de la
   misma adjudicación; para ésas se usa la moneda con mayor monto total y se
   deja el resto en raw_ocds_json, que se guarda entero igual.

Cuando la moneda ya es USD se completa amount_usd directamente, porque no hay
conversión de por medio. Para UYU/EUR/UYI se deja en None: no hay una tasa
verificable por fecha de contrato en este entorno, y la convención del
proyecto es mostrar la moneda original antes que inventar un número.
"""

import argparse
import io
import json
import sys
import urllib.parse
import urllib.request
import uuid
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

COUNTRY_CODE = "UY"
CKAN_ROOT = "https://catalogodatos.gub.uy"
DATASET_ID = "arce-datos-historicos-de-compras"
PORTAL_URL = "https://www.comprasestatales.gub.uy/"

DEFAULT_YEAR = 2025
DEFAULT_MAX_RECORDS = 5000


def resolve_year_url(year: int) -> str | None:
    """URL del ZIP de un año, resuelta por CKAN en vez de hardcodeada."""
    url = f"{CKAN_ROOT}/api/3/action/package_show?{urllib.parse.urlencode({'id': DATASET_ID})}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        pkg = json.loads(resp.read().decode("utf-8"))["result"]

    for res in pkg.get("resources", []):
        target = f"ocds-{year}.zip"
        if (res.get("url") or "").endswith(target):
            return res["url"]
    return None


def award_amount(award: dict) -> tuple[float | None, str | None]:
    """Monto y moneda de una adjudicación, sumando sus ítems.

    Los ítems traen precio unitario y cantidad por separado. Si una misma
    adjudicación mezcla monedas (raro, ~0,14%), gana la de mayor total.
    """
    totals: dict[str, float] = defaultdict(float)
    for item in award.get("items") or []:
        value = (item.get("unit") or {}).get("value") or {}
        amount = value.get("amount")
        currency = value.get("currency")
        if amount is None or not currency:
            continue
        try:
            qty = float(item.get("quantity") or 1.0)
            totals[currency] += float(amount) * qty
        except (TypeError, ValueError):
            continue

    if not totals:
        return None, None
    currency = max(totals, key=lambda c: totals[c])
    return totals[currency], currency


def parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def normalize(name: str | None) -> str:
    return (name or "").strip().lower()


def main():
    parser = argparse.ArgumentParser(description="Ingesta de Uruguay (ARCE, OCDS nativo).")
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS)
    parser.add_argument("--months", type=int, default=12,
                        help="Cuántos meses del año procesar (1 = sólo enero).")
    parser.add_argument("--init-only", action="store_true")
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        country = db.get(models.Country, COUNTRY_CODE)
        if country is None:
            country = models.Country(
                code=COUNTRY_CODE,
                name="Uruguay",
                ocds_portal_url=PORTAL_URL,
                schema_variant="ocds-1.1-arce",
                ingestion_method="api",
                active=True,
            )
            db.add(country)
            db.flush()
            print(f"[país] creado: {country.name} ({COUNTRY_CODE})")
        else:
            print(f"[país] ya existía: {country.name} ({COUNTRY_CODE})")

        if args.init_only:
            db.commit()
            return

        print(f"[ckan] resolviendo ZIP de {args.year}...")
        zip_url = resolve_year_url(args.year)
        if not zip_url:
            raise SystemExit(f"El dataset no publica un ocds-{args.year}.zip.")
        print(f"[zip]  {zip_url}")

        with urllib.request.urlopen(zip_url, timeout=300) as resp:
            blob = resp.read()
        print(f"[zip]  {len(blob):,} bytes descargados")

        source = models.DataSource(
            country_code=COUNTRY_CODE,
            source_type="api",
            base_url=zip_url,
            terms_of_use_notes=(
                "Catalogo Nacional de Datos Abiertos de Uruguay "
                "(catalogodatos.gub.uy), dataset ARCE "
                f"'{DATASET_ID}'. OCDS 1.1 nativo, un ZIP por anio, "
                "licencia abierta ODC-UY. Verificado 2026-09-09."
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

        buyers_by_key: dict[str, models.Buyer] = {}
        ingested = 0
        skipped_existing = 0
        no_amount = 0
        failed = 0

        zf = zipfile.ZipFile(io.BytesIO(blob))
        members = sorted(n for n in zf.namelist() if n.endswith(".json"))[: args.months]
        print(f"[zip]  {len(members)} archivos mensuales a procesar\n")

        for member in members:
            if ingested >= args.max_records:
                break

            package = json.loads(zf.read(member).decode("utf-8"))
            releases = package.get("releases") or []
            print(f"[{member}] {len(releases)} releases")

            for release in releases:
                if ingested >= args.max_records:
                    break
                try:
                    buyer_info = release.get("buyer") or {}
                    buyer_name = (buyer_info.get("name") or "").strip()
                    buyer = None
                    if buyer_name:
                        key = normalize(buyer_name)
                        buyer = buyers_by_key.get(key)
                        if buyer is None:
                            buyer = db.execute(
                                select(models.Buyer).where(
                                    models.Buyer.country_code == COUNTRY_CODE,
                                    models.Buyer.normalized_name == key,
                                )
                            ).scalars().first()
                            if buyer is None:
                                buyer = models.Buyer(
                                    id=str(uuid.uuid4()),
                                    country_code=COUNTRY_CODE,
                                    external_id=str(buyer_info.get("id") or "") or None,
                                    name=buyer_name[:500],
                                    normalized_name=key[:500],
                                )
                                db.add(buyer)
                                db.flush()
                            buyers_by_key[key] = buyer

                    for award in release.get("awards") or []:
                        if ingested >= args.max_records:
                            break

                        # Una adjudicación por contrato: el ocid identifica el
                        # procedimiento y puede repetirse entre adjudicaciones.
                        external_id = f"{release.get('id')}::{award.get('id')}"

                        already = db.execute(
                            select(models.Contract.id).where(
                                models.Contract.country_code == COUNTRY_CODE,
                                models.Contract.external_id == external_id,
                            )
                        ).first()
                        if already:
                            skipped_existing += 1
                            continue

                        amount, currency = award_amount(award)
                        if amount is None:
                            no_amount += 1

                        items = award.get("items") or []
                        description = None
                        if items:
                            description = ((items[0].get("classification") or {})
                                           .get("description"))

                        title = (award.get("title") or description or "Sin objeto")

                        db.add(models.Contract(
                            id=str(uuid.uuid4()),
                            ocid=release.get("ocid"),
                            external_id=external_id,
                            country_code=COUNTRY_CODE,
                            source_id=source.id,
                            buyer_id=buyer.id if buyer else None,
                            title=str(title)[:300],
                            description=description,
                            category_code=None,
                            currency=currency,
                            amount_original=amount,
                            # Sólo cuando la fuente ya publica en USD: no hay
                            # tasa UYU/USD verificable por fecha acá.
                            amount_usd=amount if currency == "USD" else None,
                            award_date=parse_dt(award.get("date")) or parse_dt(release.get("date")),
                            procurement_method=(release.get("tender") or {}).get("procurementMethod"),
                            raw_ocds_json=release,
                            source_url=PORTAL_URL,
                        ))
                        ingested += 1

                except Exception as e:
                    failed += 1
                    print(f"  ! release descartado: {e}")
                    continue

            db.commit()

        run.finished_at = datetime.utcnow()
        run.status = "completed"
        run.records_ingested = ingested
        run.records_failed = failed
        db.commit()

        print(f"\n[fin] nuevos={ingested}  ya_existían={skipped_existing}  "
              f"sin_monto={no_amount}  fallidos={failed}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
