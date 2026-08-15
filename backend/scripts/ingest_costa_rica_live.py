"""Ingesta EN VIVO de Costa Rica, vía el Observatorio de Compra Pública
(observatoriocomprapublica.go.cr, Ministerio de Hacienda).

Costa Rica NO tiene una API OCDS ni REST tradicional -- se investigó
(SICOP/Mer-Link no publica datos abiertos ni API, ver PROGRESS.md) -- pero el
Observatorio sí publica, de forma documentada y pública, un ZIP mensual con
CSVs de todo el sistema SICOP, actualizado DIARIAMENTE para el mes en curso:

    https://www.observatoriocomprapublica.go.cr/descargas-sicop/
    -> "los archivos mensuales del último mes (año presente) se actualiza
       diariamente a las 08:00 horas"
    -> patrón documentado: https://dlsaobservatorioprod.blob.core.windows.net/
       fs-synapse-observatorio-produccion/Zip/{yyyymm}.zip

Verificado en vivo el 2026-08-15: el archivo `202608.zip` (mes actual) tenía
`Last-Modified: Fri, 14 Aug 2026` -- actualizado ayer. Esto SÍ es una fuente
en vivo real, aunque no sea un endpoint de "pregunta y respuesta" como
Colombia/Panama -- es un archivo que se regenera todos los días.

El ZIP trae ~25 CSVs relacionales (todo el modelo de datos de SICOP: ofertas,
carteles, contratos, proveedores, etc.), no una tabla plana de "contratos".
Se usa `ProcedimientoAdjudicacion.csv`, que ya viene a nivel de línea
adjudicada con todo lo necesario: institución compradora, proveedor, monto
adjudicado (en CRC Y YA CONVERTIDO A USD por el propio SICOP -- se usa
`MONTO_ADJU_LINEA_USD` tal cual, no se inventa una tasa de cambio propia,
a diferencia de Colombia), fecha de adjudicación firme, tipo de procedimiento.

Cada fila de este CSV es una línea de un proceso de adjudicación (un mismo
`NUMERO_PROCEDIMIENTO` puede tener varias líneas/ítems) -- se migra cada
línea como un contrato separado, igual que se trató cada award de Chile como
un contrato separado. La codificación real del archivo es UTF-8 (confirmado
inspeccionando los bytes crudos) -- si se ve con caracteres corruptos en una
terminal Windows es un artefacto de la consola (cp1252), no del archivo.
"""

import csv
import io
import sys
import urllib.request
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

COUNTRY_CODE = "CR"
ZIP_BASE_URL = "https://dlsaobservatorioprod.blob.core.windows.net/fs-synapse-observatorio-produccion/Zip"
TARGET_CSV = "ProcedimientoAdjudicacion.csv"


def download_current_month_zip() -> bytes:
    yyyymm = datetime.utcnow().strftime("%Y%m")
    url = f"{ZIP_BASE_URL}/{yyyymm}.zip"
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def to_float(value: str | None) -> float | None:
    if value in (None, "", "NA"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_date_ddmmyyyy(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("\xa0", " ").strip() or None


def normalize(name: str | None) -> str:
    return (name or "").strip().lower()


def main():
    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        country = db.get(models.Country, COUNTRY_CODE)
        if country is None:
            country = models.Country(
                code=COUNTRY_CODE,
                name="Costa Rica",
                ocds_portal_url="https://www.observatoriocomprapublica.go.cr/",
                schema_variant="sicop-observatorio",
                ingestion_method="api",
                active=True,
            )
            db.add(country)
            db.flush()

        source = models.DataSource(
            country_code=COUNTRY_CODE,
            source_type="api",
            base_url=ZIP_BASE_URL,
            terms_of_use_notes=(
                "Observatorio de Compra Publica, Ministerio de Hacienda de "
                "Costa Rica. ZIP mensual de datos SICOP, actualizado "
                "diariamente para el mes en curso, patron de URL "
                "documentado publicamente. No es OCDS nativo -- se mapea "
                "ProcedimientoAdjudicacion.csv al esquema interno. "
                "Verificado en vivo el 2026-08-15 (Last-Modified: dia "
                "anterior)."
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

        print("Descargando ZIP del mes actual...")
        zip_bytes = download_current_month_zip()
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        with zf.open(TARGET_CSV) as f:
            text = f.read().decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text), delimiter=";"))
        print(f"{len(rows)} lineas adjudicadas encontradas en el archivo del mes actual.")

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

        for row in rows:
            try:
                external_id = f"{row.get('NUMERO_PROCEDIMIENTO')}-{row.get('LINEA')}"
                if external_id in existing_ids:
                    skipped_duplicate += 1
                    continue

                buyer_name = clean_text(row.get("INSTITUCION"))
                buyer_key = normalize(buyer_name)
                buyer = None
                if buyer_key:
                    buyer = buyers_by_key.get(buyer_key)
                    if buyer is None:
                        buyer = models.Buyer(
                            id=str(uuid.uuid4()),
                            country_code=COUNTRY_CODE,
                            external_id=row.get("CEDULA"),
                            name=buyer_name or "Desconocido",
                            normalized_name=buyer_key,
                        )
                        db.add(buyer)
                        buyers_by_key[buyer_key] = buyer

                title = clean_text(row.get("DESCR_PROCEDIMIENTO"))
                description = clean_text(row.get("DESCR_BIEN_SERVICIO")) or title

                contract_id = str(uuid.uuid4())
                contract = models.Contract(
                    id=contract_id,
                    ocid=None,
                    external_id=external_id,
                    country_code=COUNTRY_CODE,
                    source_id=source.id,
                    buyer_id=buyer.id if buyer else None,
                    title=title,
                    description=description,
                    category_code=clean_text(row.get("MODALIDAD_PROCEDIMIENTO")),
                    currency=row.get("MONEDA_ADJUDICADA") or "CRC",
                    amount_original=to_float(row.get("MONTO_ADJU_LINEA")),
                    amount_usd=to_float(row.get("MONTO_ADJU_LINEA_USD")),
                    award_date=parse_date_ddmmyyyy(row.get("FECHA_ADJUD_FIRME")),
                    procurement_method=clean_text(row.get("TIPO_PROCEDIMIENTO")),
                    raw_ocds_json={k: v for k, v in row.items() if v not in (None, "")},
                    source_url=None,
                )
                db.add(contract)

                db.add(
                    models.Provenance(
                        entity_type="contract",
                        entity_id=contract_id,
                        source_id=source.id,
                        fetched_at=datetime.utcnow(),
                        source_hash=None,
                        raw_payload_uri=f"{ZIP_BASE_URL}/{datetime.utcnow().strftime('%Y%m')}.zip#{TARGET_CSV}",
                    )
                )

                existing_ids.add(external_id)
                ingested += 1
                if ingested % 300 == 0:
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

        print(
            f"Ingesta en vivo Costa Rica completa: {ingested} contratos nuevos, "
            f"{skipped_duplicate} duplicados omitidos, {failed} fallidos."
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
