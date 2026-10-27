"""Ingesta de Perú desde la descarga masiva mensual OCDS de OECE (SEACE v3).

El feed en vivo (`ingest_peru_live.py`) sólo devuelve una ventana reciente y
la mayoría de sus releases son convocatorias sin adjudicar: dejó 85 contratos,
pocos para la capa estadística y para entrenar el modelo de precio. El mismo
portal publica un archivo por mes con todos los procesos del mes:

    https://contratacionesabiertas.oece.gob.pe/api/v1/files          (lista)
    https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/json/{año}/{mes}/

Verificado el 2026-10-21: septiembre de 2026 = ZIP de 7,5 MB con un JSON de
72 MB (record package OCDS 1.1, CC BY 4.0), 6.640 records, 3.501 con award y
monto. El JSON se lee record por record con ijson.

Mismas reglas que la ingesta en vivo, y por eso reusa sus funciones: un
contrato por `ocid` con el award de mayor monto (`external_id = ocid`, así la
ingesta en vivo y esta nunca duplican un proceso), monto adjudicado y no el
referencial, moneda sin convertir, categoría goods/services/works.

El portal rechaza con 403 al User-Agent por defecto de urllib; responde a uno
que identifica al proyecto, como el de la ingesta en vivo.
"""

import argparse
import sys
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from ingest_peru_live import BASE, HEADERS, normalize, parse_date, pick_award, safe_commit, slim_payload  # noqa: E402

COUNTRY_CODE = "PE"
FILE_URL = "https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/json/{year}/{month:02d}/"
CACHE_DIR = Path(__file__).resolve().parent / "_peru_cache"
DEFAULT_MONTHS = ["2026-09", "2026-08"]
DEFAULT_MAX_RECORDS = 5000


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)


def main():
    try:
        import ijson
    except ImportError:
        sys.exit("Falta ijson: pip install -r requirements-ingest.txt")

    parser = argparse.ArgumentParser(description="Ingesta de Perú (descarga masiva mensual OCDS de OECE).")
    parser.add_argument("--months", nargs="+", default=DEFAULT_MONTHS, help="AAAA-MM, del más reciente al más viejo")
    parser.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS)
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    CACHE_DIR.mkdir(exist_ok=True)
    db = SessionLocal()
    try:
        existing = {
            ocid
            for (ocid,) in db.query(models.Contract.ocid).filter(
                models.Contract.country_code == COUNTRY_CODE, models.Contract.ocid.isnot(None)
            )
        }
        buyers: dict = {}
        ingested = skipped = no_award = failed = 0

        for month in args.months:
            if ingested >= args.max_records:
                break
            year, mm = (int(x) for x in month.split("-"))
            url = FILE_URL.format(year=year, month=mm)
            archive = CACHE_DIR / f"{month}.zip"
            if not archive.exists():
                print(f"[zip]  descargando {url}")
                download(url, archive)
            print(f"[zip]  {month}: {archive.stat().st_size:,} bytes")

            source = models.DataSource(
                country_code=COUNTRY_CODE,
                source_type="ocds_bulk",
                base_url=url,
                terms_of_use_notes=(
                    "OECE, Portal de Contrataciones Abiertas: descarga masiva mensual OCDS 1.1 (SEACE v3), "
                    "licencia CC BY 4.0. Verificado 2026-10-21."
                ),
                last_ingested_at=datetime.utcnow(),
            )
            db.add(source)
            db.flush()
            run = models.IngestionRun(
                country_code=COUNTRY_CODE, source_id=source.id, started_at=datetime.utcnow(), status="running"
            )
            db.add(run)
            db.flush()
            month_new = 0

            with zipfile.ZipFile(archive) as z, z.open(z.infolist()[0].filename) as fh:
                for record in ijson.items(fh, "records.item", use_float=True):
                    if ingested >= args.max_records:
                        break
                    try:
                        release = record.get("compiledRelease") or {}
                        ocid = release.get("ocid") or record.get("ocid")
                        award = pick_award(release)
                        if not ocid or award is None:
                            no_award += 1
                            continue
                        if ocid in existing:
                            skipped += 1
                            continue

                        tender = release.get("tender") or {}
                        buyer_obj = release.get("buyer") or {}
                        buyer_name = buyer_obj.get("name") or (tender.get("procuringEntity") or {}).get("name")
                        buyer_key = normalize(buyer_name)
                        buyer = None
                        if buyer_key:
                            buyer = buyers.get(buyer_key) or (
                                db.query(models.Buyer)
                                .filter(models.Buyer.country_code == COUNTRY_CODE, models.Buyer.normalized_name == buyer_key)
                                .first()
                            )
                            if buyer is None:
                                buyer = models.Buyer(
                                    id=str(uuid.uuid4()),
                                    country_code=COUNTRY_CODE,
                                    external_id=buyer_obj.get("id"),
                                    name=buyer_name or "Desconocido",
                                    normalized_name=buyer_key,
                                )
                                db.add(buyer)
                            buyers[buyer_key] = buyer

                        value = award.get("value") or {}
                        db.add(models.Contract(
                            id=str(uuid.uuid4()),
                            ocid=ocid,
                            external_id=ocid,
                            country_code=COUNTRY_CODE,
                            source_id=source.id,
                            buyer_id=buyer.id if buyer else None,
                            title=tender.get("title") or tender.get("description"),
                            description=tender.get("description") or tender.get("title"),
                            category_code=tender.get("mainProcurementCategory"),
                            currency=value.get("currency") or "PEN",
                            amount_original=float(value.get("amount")),
                            amount_usd=float(value.get("amount")) if value.get("currency") == "USD" else None,
                            award_date=parse_date(award.get("date")) or parse_date(release.get("date")),
                            procurement_method=tender.get("procurementMethodDetails"),
                            raw_ocds_json=slim_payload(release, award),
                            source_url=f"{BASE}?{urllib.parse.urlencode({'ocid': ocid})}",
                        ))
                        existing.add(ocid)
                        ingested += 1
                        month_new += 1
                        if month_new % 500 == 0:
                            safe_commit(db, f"{month} #{month_new}")
                    except Exception as e:  # noqa: BLE001
                        failed += 1
                        print(f"  ! {record.get('ocid')} descartado: {e}", file=sys.stderr)

            run.finished_at = datetime.utcnow()
            run.status = "completed"
            run.records_ingested = month_new
            safe_commit(db, f"{month} final")
            print(f"[mes]  {month}: {month_new} nuevos")

        print(f"\n[fin] nuevos={ingested}  ya_existían={skipped}  sin_award={no_award}  fallidos={failed}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
