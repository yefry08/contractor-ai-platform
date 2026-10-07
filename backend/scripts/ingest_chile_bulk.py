"""Ingesta de Chile desde la descarga masiva OCDS de ChileCompra.

Reemplaza en la práctica a `ingest_chile_live.py`, que pide cada contrato a
la API por separado y choca con el throttling del servidor (ver su
docstring). Acá se baja un solo archivo por mes:

    https://ocds-lic-files.da.mercadopublico.cl/{año}/{año}{mes}.7z

URL tomada del botón "Descargar archivo" de
https://datos-abiertos.chilecompra.cl/descargas/procesos-ocds (pestaña
"Descarga masiva de licitaciones"), verificada el 2026-10-06. Licencia CC0.
Cada .7z trae un JSON por licitación (record OCDS 1.1 con compiledRelease);
abril de 2026 = 8.472 licitaciones, 29 MB comprimido, 213 MB descomprimido.

Alcance: SOLO licitaciones (no tratos directos ni convenio marco). Una fila
por adjudicación activa con monto. Sin conversión a USD, igual que Colombia:
no hay tasa CLP->USD verificada por fecha.

La categoría es el segmento UNSPSC oficial del ítem adjudicado (la primera
parte de la descripción jerárquica que publica ChileCompra, p. ej.
"Vehículos y equipamiento en general"), no una inferencia.

`raw_ocds_json` guarda un recorte del record: completo pesa ~25 KB por
licitación, 15 veces más que en otros países, y el plan gratis de Neon tiene
512 MB.

Requiere py7zr (requirements-ingest.txt), que no va en la imagen de la API.
"""

import argparse
import json
import multiprocessing
import sys
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

COUNTRY_CODE = "CL"
PORTAL_URL = "https://www.mercadopublico.cl/"
TENDER_URL = "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion={}"
ARCHIVE_URL = "https://ocds-lic-files.da.mercadopublico.cl/{year}/{year}{month:02d}.7z"
CACHE_DIR = Path(__file__).resolve().parent / "_chile_cache"

DEFAULT_YEAR, DEFAULT_MONTH = 2026, 4
DEFAULT_MAX_RECORDS = 5000
EXTRACT_BATCH = 100


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "ContractorAI-ingest/1.0"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)


def _extract_batch(archive: str, dest: str, batch: list[str]) -> None:
    import py7zr

    # Pasar el archivo abierto, no la ruta, evita que py7zr lance un hilo por JSON.
    with open(archive, "rb") as fh, py7zr.SevenZipFile(fh) as z:
        z.extract(path=dest, targets=batch)


def extract(archive: Path, dest: Path) -> None:
    try:
        import py7zr
    except ImportError:
        sys.exit("Falta py7zr: pip install -r requirements-ingest.txt")
    dest.mkdir(parents=True, exist_ok=True)
    with open(archive, "rb") as fh, py7zr.SevenZipFile(fh) as z:
        names = z.getnames()
    pending = [n for n in names if not (dest / n).exists()]
    # Cada JSON es su propia "carpeta" 7z y py7zr crea un descompresor LZMA por
    # carpeta que no se libera ni al cerrar el archivo: en un solo proceso se
    # agota la RAM (MemoryError) a las ~250 carpetas, aun por tandas. Cada
    # tanda corre en su propio proceso, que al terminar devuelve toda la memoria.
    ctx = multiprocessing.get_context("spawn")
    for start in range(0, len(pending), EXTRACT_BATCH):
        batch = pending[start:start + EXTRACT_BATCH]
        proc = ctx.Process(target=_extract_batch, args=(str(archive), str(dest), batch))
        proc.start()
        proc.join()
        if proc.exitcode != 0:
            sys.exit(f"Falló la extracción de la tanda que empieza en {start} (código {proc.exitcode}).")
        print(f"[7z]   {min(start + EXTRACT_BATCH, len(pending)):,}/{len(pending):,} extraídos")


def parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def unspsc_segment(release: dict, award: dict) -> str | None:
    """Segmento UNSPSC del primer ítem adjudicado que tenga clasificación."""
    names = {}
    for item in (release.get("tender") or {}).get("items") or []:
        cls = item.get("classification") or {}
        if cls.get("id") and item.get("description"):
            names[cls["id"]] = item["description"]
    for item in award.get("items") or []:
        cls_id = (item.get("classification") or {}).get("id")
        path = names.get(cls_id)
        if path:
            return path.split(" / ")[0].strip()[:120] or None
    return None


def trimmed(record: dict, release: dict, award: dict) -> dict:
    tender = release.get("tender") or {}
    return {
        "ocid": record.get("ocid"),
        "tender": {
            "id": tender.get("id"),
            "title": tender.get("title"),
            "status": tender.get("status"),
            "procurementMethodDetails": tender.get("procurementMethodDetails"),
        },
        "buyer": release.get("buyer"),
        "award": {
            "id": award.get("id"),
            "date": award.get("date"),
            "status": award.get("status"),
            "value": award.get("value"),
            "suppliers": award.get("suppliers"),
            "items": [
                {k: item.get(k) for k in ("id", "quantity", "unit", "classification")}
                for item in (award.get("items") or [])[:5]
            ],
        },
    }


def get_buyer(db, cache: dict, info: dict):
    name = (info.get("name") or "").strip()
    if not name:
        return None
    key = name.lower()
    buyer = cache.get(key)
    if buyer is None:
        buyer = db.execute(
            select(models.Buyer).where(
                models.Buyer.country_code == COUNTRY_CODE,
                models.Buyer.normalized_name == key[:500],
            )
        ).scalars().first()
        if buyer is None:
            buyer = models.Buyer(
                id=str(uuid.uuid4()),
                country_code=COUNTRY_CODE,
                external_id=str(info.get("id") or "") or None,
                name=name[:500],
                normalized_name=key[:500],
            )
            db.add(buyer)
            db.flush()
        cache[key] = buyer
    return buyer


def main():
    parser = argparse.ArgumentParser(description="Ingesta de Chile (descarga masiva OCDS de ChileCompra).")
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--month", type=int, default=DEFAULT_MONTH)
    parser.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS)
    args = parser.parse_args()

    url = ARCHIVE_URL.format(year=args.year, month=args.month)
    tag = f"{args.year}{args.month:02d}"
    CACHE_DIR.mkdir(exist_ok=True)
    archive = CACHE_DIR / f"{tag}.7z"
    folder = CACHE_DIR / tag

    if not archive.exists():
        print(f"[7z]   descargando {url}")
        download(url, archive)
    print(f"[7z]   {archive.stat().st_size:,} bytes")
    print("[7z]   extrayendo (tarda varios minutos)...")
    extract(archive, folder)
    files = sorted(folder.glob("*.json"))
    print(f"[7z]   {len(files):,} licitaciones")

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.get(models.Country, COUNTRY_CODE) is None:
            db.add(models.Country(
                code=COUNTRY_CODE,
                name="Chile",
                ocds_portal_url=PORTAL_URL,
                schema_variant="ocds-1.1-chilecompra",
                ingestion_method="bulk",
                active=True,
            ))
            db.flush()
            print("[país] creado: Chile (CL)")

        source = models.DataSource(
            country_code=COUNTRY_CODE,
            source_type="ocds_bulk",
            base_url=url,
            terms_of_use_notes=(
                "ChileCompra, descarga masiva OCDS de licitaciones "
                "(datos-abiertos.chilecompra.cl/descargas/procesos-ocds). "
                "OCDS 1.1, un .7z por mes, licencia CC0. Verificado 2026-10-06."
            ),
            last_ingested_at=datetime.utcnow(),
        )
        db.add(source)
        db.flush()
        run = models.IngestionRun(
            country_code=COUNTRY_CODE, source_id=source.id,
            started_at=datetime.utcnow(), status="running",
        )
        db.add(run)
        db.flush()

        existing = set(db.execute(
            select(models.Contract.external_id).where(models.Contract.country_code == COUNTRY_CODE)
        ).scalars())
        buyers: dict = {}
        ingested = skipped = no_amount = failed = last_commit = 0

        for path in files:
            if ingested >= args.max_records:
                break
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                record = (doc.get("records") or [{}])[0]
                release = record.get("compiledRelease") or {}
                tender = release.get("tender") or {}
                buyer = None
                for award in release.get("awards") or []:
                    if ingested >= args.max_records:
                        break
                    if award.get("status") != "active":
                        continue
                    value = award.get("value") or {}
                    amount = value.get("amount")
                    if not amount or amount <= 0:
                        no_amount += 1
                        continue
                    external_id = f"{tender.get('id')}::{award.get('id')}"
                    if external_id in existing:
                        skipped += 1
                        continue
                    if buyer is None:
                        buyer = get_buyer(db, buyers, release.get("buyer") or {})
                    db.add(models.Contract(
                        id=str(uuid.uuid4()),
                        ocid=record.get("ocid"),
                        external_id=external_id,
                        country_code=COUNTRY_CODE,
                        source_id=source.id,
                        buyer_id=buyer.id if buyer else None,
                        title=(tender.get("title") or award.get("title") or "Sin título")[:300],
                        description=tender.get("description"),
                        category_code=unspsc_segment(release, award),
                        currency=value.get("currency"),
                        amount_original=float(amount),
                        amount_usd=float(amount) if value.get("currency") == "USD" else None,
                        award_date=parse_date(award.get("date")) or parse_date(release.get("date")),
                        procurement_method=tender.get("procurementMethodDetails") or tender.get("procurementMethod"),
                        raw_ocds_json=trimmed(record, release, award),
                        source_url=TENDER_URL.format(tender.get("id")) if tender.get("id") else PORTAL_URL,
                    ))
                    existing.add(external_id)
                    ingested += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"  ! {path.name} descartado: {e}")
            if ingested - last_commit >= 500:
                db.commit()
                last_commit = ingested

        run.finished_at = datetime.utcnow()
        run.status = "completed"
        run.records_ingested = ingested
        run.records_failed = failed
        db.commit()
        print(f"\n[fin] nuevos={ingested}  ya_existían={skipped}  sin_monto={no_amount}  fallidos={failed}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
