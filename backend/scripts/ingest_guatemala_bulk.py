"""Ingesta de Guatemala desde la descarga mensual OCDS de Guatecompras.

Fuente oficial: https://ocds.guatecompras.gt/descarga-datos (Ministerio de
Finanzas Públicas - DGAE), un ZIP por mes con un solo JSON (record package
OCDS 1.1), actualizado a diario, licencia CC BY 4.0. URL de cada mes:

    https://ocds.guatecompras.gt/file/json/{año}/{mes}

Verificado el 2026-10-07: septiembre de 2026 = 35 MB comprimido, 257 MB de
JSON. Por ese tamaño el JSON se lee registro por registro con ijson en vez de
cargarlo entero (requirements-ingest.txt).

Una fila por adjudicación activa con monto. Montos en quetzales (GTQ), sin
conversión a USD: no hay tasa verificada por fecha.

Guatecompras publica el código UNSPSC de cada ítem pero no su nombre. La
categoría es el segmento (los dos primeros dígitos) con el nombre en español
que publica ChileCompra para ese mismo segmento: es la misma norma
internacional, solo que Guatemala omite la descripción. Un segmento que no
esté en la tabla queda como "UNSPSC segmento NN".
"""

import argparse
import sys
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

COUNTRY_CODE = "GT"
PORTAL_URL = "https://www.guatecompras.gt/"
ARCHIVE_URL = "https://ocds.guatecompras.gt/file/json/{year}/{month}"
CACHE_DIR = Path(__file__).resolve().parent / "_guatemala_cache"

DEFAULT_YEAR, DEFAULT_MONTH = 2026, 9
DEFAULT_MAX_RECORDS = 5000

# Nombres de segmento UNSPSC tal como los publica ChileCompra en sus records
# OCDS (primer tramo de la descripción jerárquica de cada ítem), extraídos de
# las 8.472 licitaciones de abril de 2026. Ningún código tenía nombres en
# conflicto.
UNSPSC_SEGMENTS = {
    "10": "Artículos para plantas y animales",
    "11": "Productos derivados de minerales, plantas y animales",
    "12": "Productos químicos industriales",
    "13": "Resinas, cauchos, espumas y elastómeros",
    "14": "Productos de papel",
    "15": "Combustibles, lubricantes y anticorrosivos",
    "20": "Maquinaria para minería y perforación",
    "21": "Maquinaria para agricultura, pesca y silvicultura",
    "22": "Maquinaria para construcción y edificación",
    "23": "Maquinaria para fabricación y transformación industrial",
    "24": "Equipamiento para manejo y estiba de materiales",
    "25": "Vehículos y equipamiento en general",
    "26": "Maquinaria para generación y distribución de energía",
    "27": "Herramientas y maquinaria en general",
    "30": "Artículos para estructuras, obras y construcciones",
    "31": "Artículos de fabricación y producción",
    "32": "Artículos de electrónica",
    "39": "Artículos eléctricos y de iluminación",
    "40": "Equipamiento para el acondicionamiento, distribución y filtrado de fluidos",
    "41": "Equipamiento para laboratorios",
    "42": "Equipamiento y suministros médicos",
    "43": "Tecnologías de la información, telecomunicaciones y radiodifusión",
    "44": "Equipos, accesorios y suministros de oficina",
    "45": "Equipos y suministros de imprenta, fotográficos y audiovisuales",
    "46": "Equipos y suministros de defensa, orden público, protección y seguridad",
    "47": "Equipos y suministros de limpieza",
    "48": "Maquinarias, equipos y suministros para la industria de servicios",
    "49": "Equipos, suministros y accesorios deportivos y recreativos",
    "50": "Alimentos, bebidas y tabaco",
    "51": "Medicamentos y productos farmacéuticos",
    "52": "Muebles, accesorios, electrodomésticos y productos electrónicos",
    "53": "Ropa, maletas y productos de aseo personal",
    "54": "Productos para relojería, joyería y gemas",
    "55": "Productos impresos y publicaciones",
    "56": "Muebles y mobiliario",
    "60": "Instrumentos musicales, juegos, juguetes, artesanías y materiales educativos",
    "70": "Servicios agrícolas, pesqueros, forestales y relacionados con la fauna",
    "71": "Servicios de perforación de minería, petróleo y gas",
    "72": "Servicios de construcción y mantenimiento",
    "73": "Servicios de producción y fabricación industrial",
    "76": "Servicios de limpieza industrial",
    "77": "Servicios medioambientales",
    "78": "Servicios de transporte, almacenaje y correo",
    "80": "Servicios profesionales, administrativos y consultorías de gestión empresarial",
    "81": "Servicios basados en ingeniería, ciencias sociales y tecnología de la información",
    "82": "Servicios editoriales, de diseño, publicidad, gráficos y artistas",
    "83": "Servicios básicos y de información pública",
    "84": "Servicios financieros, pensiones y seguros",
    "85": "Salud, servicios sanitarios y alimentación",
    "86": "Educación, formación, entrenamiento y capacitación",
    "90": "Servicios de Viajes, alimentación, alojamiento y entretenimiento",
    "91": "Servicios de cuidado personal y domésticos",
    "92": "Servicios de defensa nacional, orden público y seguridad",
    "93": "Organizaciones y consultorías políticas, demográficas, económicas, sociales y de administración pública",
    "94": "Organizaciones sociales, laborales y clubes",
}


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "ContractorAI-ingest/1.0"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)


def parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def category(release: dict) -> str | None:
    for item in (release.get("tender") or {}).get("items") or []:
        code = str((item.get("classification") or {}).get("id") or "")
        if len(code) >= 2 and code[:2].isdigit():
            return UNSPSC_SEGMENTS.get(code[:2], f"UNSPSC segmento {code[:2]}")
    return None


def trimmed(record: dict, release: dict, award: dict) -> dict:
    tender = release.get("tender") or {}
    return {
        "ocid": record.get("ocid"),
        "tender": {k: tender.get(k) for k in ("id", "title", "status", "procurementMethodDetails", "mainProcurementCategory")},
        "buyer": release.get("buyer"),
        "award": {
            "id": award.get("id"),
            "date": award.get("date"),
            "status": award.get("status"),
            "value": award.get("value"),
            "suppliers": award.get("suppliers"),
        },
        "items": [
            {k: item.get(k) for k in ("description", "classification", "quantity")}
            for item in (tender.get("items") or [])[:5]
        ],
    }


def get_buyer(db, cache: dict, info: dict):
    name = (info.get("name") or "").strip()
    if not name:
        return None
    key = name.lower()[:500]
    buyer = cache.get(key)
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
                external_id=str(info.get("id") or "") or None,
                name=name[:500],
                normalized_name=key,
            )
            db.add(buyer)
            db.flush()
        cache[key] = buyer
    return buyer


def main():
    try:
        import ijson
    except ImportError:
        sys.exit("Falta ijson: pip install -r requirements-ingest.txt")

    parser = argparse.ArgumentParser(description="Ingesta de Guatemala (descarga mensual OCDS de Guatecompras).")
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--month", type=int, default=DEFAULT_MONTH)
    parser.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS)
    args = parser.parse_args()

    url = ARCHIVE_URL.format(year=args.year, month=args.month)
    CACHE_DIR.mkdir(exist_ok=True)
    archive = CACHE_DIR / f"{args.year}-{args.month:02d}.zip"
    if not archive.exists():
        print(f"[zip]  descargando {url}")
        download(url, archive)
    print(f"[zip]  {archive.stat().st_size:,} bytes")

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.get(models.Country, COUNTRY_CODE) is None:
            db.add(models.Country(
                code=COUNTRY_CODE,
                name="Guatemala",
                ocds_portal_url=PORTAL_URL,
                schema_variant="ocds-1.1-guatecompras",
                ingestion_method="bulk",
                active=True,
            ))
            db.flush()
            print("[país] creado: Guatemala (GT)")

        source = models.DataSource(
            country_code=COUNTRY_CODE,
            source_type="ocds_bulk",
            base_url=url,
            terms_of_use_notes=(
                "Guatecompras, descarga mensual OCDS (ocds.guatecompras.gt/descarga-datos), "
                "Ministerio de Finanzas Públicas - DGAE. OCDS 1.1, licencia CC BY 4.0. "
                "Verificado 2026-10-07."
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

        with zipfile.ZipFile(archive) as z, z.open(z.infolist()[0].filename) as fh:
            for record in ijson.items(fh, "records.item", use_float=True):
                if ingested >= args.max_records:
                    break
                try:
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
                        external_id = str(award.get("id") or f"{tender.get('id')}::{award.get('date')}")
                        if external_id in existing:
                            skipped += 1
                            continue
                        if buyer is None:
                            buyer = get_buyer(db, buyers, release.get("buyer") or {})
                        # El link a la ficha de guatecompras.gt pasa por un captcha
                        # que no se pudo verificar; el release OCDS oficial sí abre.
                        releases = record.get("releases") or []
                        release_url = (releases[-1].get("url") if releases else None) or PORTAL_URL
                        db.add(models.Contract(
                            id=str(uuid.uuid4()),
                            ocid=record.get("ocid"),
                            external_id=external_id[:200],
                            country_code=COUNTRY_CODE,
                            source_id=source.id,
                            buyer_id=buyer.id if buyer else None,
                            title=(tender.get("title") or award.get("title") or "Sin título")[:300],
                            description=tender.get("description"),
                            category_code=category(release),
                            currency=value.get("currency"),
                            amount_original=float(amount),
                            amount_usd=float(amount) if value.get("currency") == "USD" else None,
                            award_date=parse_date(award.get("date")) or parse_date(release.get("date")),
                            procurement_method=(tender.get("procurementMethodDetails") or tender.get("procurementMethod") or "")[:200] or None,
                            raw_ocds_json=trimmed(record, release, award),
                            source_url=release_url[:500],
                        ))
                        existing.add(external_id)
                        ingested += 1
                except Exception as e:  # noqa: BLE001
                    failed += 1
                    print(f"  ! {record.get('ocid')} descartado: {e}")
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
