"""Migra los datos de Colombia desde el repositorio público de Daniel Duque
(github.com/Daniel-Duque/cont_front_don), enlazado desde su propia app pública
en Streamlit (https://contfrontdon.streamlit.app/) — mismo autor del prototipo
original de Paraguay ("@author: dduque" en main.py). El usuario pidió
explícitamente sacar los datos de Colombia de esa app.

Cadena de procedencia (importante, se guarda en `Provenance`): SECOP
(portal oficial de Colombia) -> pipeline propio de Daniel Duque (modelo ya
entrenado, predicciones ya calculadas) -> archivos `data/cleaned{0..39}.csv`
de ese repo -> esta migración. Esto NO es una conexión en vivo a la API OCDS
de Colombia (eso sigue pendiente, ver
docs/architecture/fase2-relevamiento-paises.md) — es una carga en bloque de un
dataset ya procesado por otro equipo, igual que Paraguay en Fase 1 fue una
carga en bloque de un xlsx ya procesado, no una ingesta en vivo.

Limitaciones de este dataset que NO se deben forzar ni inventar:

1. **Sin fecha por contrato.** Los archivos `cleaned{N}.csv` no traen fecha de
   firma ni de publicación (a diferencia del dataset de Paraguay). El
   directorio `data/particular/` del mismo repo sí tiene `Fecha de Firma` por
   municipio, pero está partido en cientos de archivos por
   departamento-municipio sin una clave de unión confiable hacia
   `cleaned{N}.csv` (no comparten un ID de contrato). No se intenta ese cruce
   acá — `award_date` queda NULL para Colombia. Registrado como limitación
   conocida en PROGRESS.md, no oculto.
2. **Sin tasa de cambio verificable por fecha.** Sin fecha no hay forma
   responsable de convertir COP a USD para comparar con Paraguay (usar una
   tasa "actual" para contratos de años distintos daría cifras falsas). Por
   eso `amount_usd` / `predictions.predicted_value_usd` quedan NULL para
   Colombia; se puebla en cambio `amount_original` (COP) y
   `predictions.predicted_value_original` (COP). La detección de anomalías no
   se ve afectada: es un ratio (real/predicho) que no depende de la moneda.
3. **`veces la predicción` verificado como Valor real / Valor Proyectado**
   (comprobado numéricamente fila por fila antes de usarlo). Se usa
   perc_error = veces_la_prediccion - 1, exactamente la misma definición que
   perc_error en el dataset de Paraguay ((real-predicho)/predicho), así que el
   score de anomalía es comparable entre países pese a estar en monedas
   distintas.
4. **Sin deduplicar entre los 40 archivos.** No hay un ID de contrato único en
   estos CSVs para detectar duplicados con confianza; se migran tal cual.
"""

import csv
import io
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

REPO = "Daniel-Duque/cont_front_don"
BASE_RAW_URL = f"https://raw.githubusercontent.com/{REPO}/main/data"
NUM_CHUNKS = 40
COUNTRY_CODE = "CO"
ABS_PERC_ERROR_THRESHOLD = 1.0  # misma definición que backend/scripts/migrate_dataset.py


def fetch_chunk(i: int) -> list[dict]:
    url = f"{BASE_RAW_URL}/cleaned{i}.csv"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = resp.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(data)))


def to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


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
            source_type="manual_upload",
            base_url=f"https://github.com/{REPO}",
            terms_of_use_notes=(
                "Dataset ya procesado por un tercero (mismo autor del prototipo "
                "original, Daniel Duque), obtenido del repositorio publico "
                f"github.com/{REPO}, enlazado desde su app publica en Streamlit "
                "(https://contfrontdon.streamlit.app/). No es una ingesta en vivo "
                "de la API OCDS de Colombia -- ver docs/architecture/"
                "fase2-relevamiento-paises.md para ese trabajo pendiente."
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
        failed = 0

        for i in range(NUM_CHUNKS):
            try:
                rows = fetch_chunk(i)
            except Exception as exc:  # noqa: BLE001
                print(f"  chunk {i} fallo al descargar: {exc}", file=sys.stderr)
                continue

            for row in rows:
                try:
                    buyer_name = row.get("Nombre Entidad")
                    buyer_key = normalize(buyer_name)

                    buyer = None
                    if buyer_key:
                        buyer = buyers_by_key.get(buyer_key)
                        if buyer is None:
                            buyer = models.Buyer(
                                country_code=COUNTRY_CODE,
                                external_id=None,
                                name=buyer_name or "Desconocido",
                                normalized_name=buyer_key,
                            )
                            db.add(buyer)
                            db.flush()
                            buyers_by_key[buyer_key] = buyer

                    valor_real = to_float(row.get("Valor real"))
                    valor_predicho = to_float(row.get("Valor Proyectado"))
                    veces_prediccion = to_float(row.get("veces la predicción"))
                    similarity = to_float(row.get("similarity"))
                    descripcion = row.get("Descripcion del Proceso")
                    url_proceso = row.get("URLProceso") or None

                    contract = models.Contract(
                        ocid=None,
                        external_id=None,
                        country_code=COUNTRY_CODE,
                        source_id=source.id,
                        buyer_id=buyer.id if buyer else None,
                        title=descripcion,
                        description=descripcion,
                        category_code=row.get("Tipo de Contrato"),
                        currency="COP",
                        amount_original=(valor_real * 1_000_000) if valor_real is not None else None,
                        amount_usd=None,
                        award_date=None,
                        procurement_method=None,
                        raw_ocds_json={k: v for k, v in row.items() if v not in (None, "")},
                        source_url=url_proceso,
                    )
                    db.add(contract)
                    db.flush()

                    if valor_predicho is not None:
                        db.add(
                            models.Prediction(
                                contract_id=contract.id,
                                model_name="bert-multilingual-xgboost",
                                model_version="cont_front_don-daniel-duque",
                                predicted_value_usd=None,
                                predicted_value_original=valor_predicho * 1_000_000,
                                range_low=None,
                                range_high=None,
                                likelihood_score=similarity,
                            )
                        )

                    perc_error = (veces_prediccion - 1) if veces_prediccion is not None else None
                    if perc_error is not None and abs(perc_error) >= ABS_PERC_ERROR_THRESHOLD:
                        db.add(
                            models.Anomaly(
                                contract_id=contract.id,
                                anomaly_type="overcost" if perc_error >= 0 else "undercost",
                                composite_score=abs(perc_error),
                                nlp_component=perc_error,
                                stat_component=None,
                                llm_narrative=None,
                                confidence=similarity,
                                status="open",
                            )
                        )

                    db.add(
                        models.Provenance(
                            entity_type="contract",
                            entity_id=contract.id,
                            source_id=source.id,
                            fetched_at=datetime.utcnow(),
                            source_hash=None,
                            raw_payload_uri=f"{BASE_RAW_URL}/cleaned{i}.csv",
                        )
                    )

                    ingested += 1
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(f"  fila fallida (chunk {i}): {exc}", file=sys.stderr)

            db.commit()
            print(f"  ... chunk {i} listo ({ingested} contratos acumulados)")

        run.finished_at = datetime.utcnow()
        run.records_ingested = ingested
        run.records_failed = failed
        run.status = "completed"
        db.commit()

        print(f"Migración Colombia completa: {ingested} contratos, {failed} fallidos.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
