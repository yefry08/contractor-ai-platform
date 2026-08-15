"""Ingesta EN VIVO de Chile, vía la API OCDS oficial y pública de ChileCompra
(api.mercadopublico.cl/APISOCDS) -- distinta de la API "clásica" de Mercado
Público, que sí exige pedir un "ticket" vía Clave Única (identidad digital
chilena). La ruta OCDS específica NO pide ticket, es de acceso público y está
licenciada CC0 (dominio público) -- verificado en vivo el 2026-08-15 antes de
escribir este script:

    curl "https://api.mercadopublico.cl/APISOCDS/OCDS/listaOCDSAgnoMesTratoDirecto/2026/07/0/5"
    -> pagination.total = 9361 (trato directo de julio 2026 -- mes reciente real)

Endpoint documentado en https://datos-abiertos.chilecompra.cl/descargas/procesos-ocds
y https://desarrolladores.mercadopublico.cl/ocds/descripcion.

Patrón en dos pasos (a diferencia de Colombia, que trae todo en una sola
respuesta tabular):
  1. `listaOCDSAgnoMesTratoDirecto/{año}/{mes}/{offset}/{limit}` -> lista de
     {ocid, urlAward} (máximo 1000 por consulta, según la documentación
     oficial).
  2. Por cada ocid, `GET {urlAward}` -> release OCDS completo (comprador,
     proveedor, monto, fecha, descripción).

Esto son SOLO "tratos directos" (compras directas sin licitación pública) --
un subconjunto de la contratación pública chilena, no todo el universo
(licitaciones y convenios marco usan otros endpoints de la misma familia,
`listaOCDSAgnoMes` y `listaOCDSAgnoMesConvenio`, no incluidos en esta primera
pasada). Documentado como alcance parcial, no como "toda la contratación de
Chile".

Igual que en `ingest_colombia_live.py`: sin conversión a USD (no se tiene una
metodología de tasa de cambio CLP->USD verificada por fecha, se deja
`amount_original`/`currency`), y sin predicción/score de anomalía del modelo
NLP (no hay pesos entrenados corriendo en este entorno).

Dado el patrón en dos pasos (una llamada extra por contrato), se limita a
`MAX_RECORDS` con una pausa entre llamadas para no abusar de un servicio
público gratuito de otro país.

Nota de comportamiento real observada (2026-08-15, no documentada por
ChileCompra) -- IMPORTANTE, leer antes de correr este script de nuevo:

Con pedidos seguidos a `/APISOCDS/OCDS/award/{id}` (el endpoint de detalle),
el servidor corta la conexión ("Remote end closed connection" / reset) casi
de inmediato. Se investigó a fondo antes de asumir que alcanzaba con "esperar
un poco más":

  - Un pedido aislado (curl o Python urllib) siempre funciona, rápido
    (<0.5s), sin importar el cliente usado.
  - Con Python urllib + reintentos y backoff en loop: fallaron ~100% de los
    pedidos, incluso con 1.5-2s de pausa entre cada uno.
  - Con `requests` + `HTTPAdapter`/`Retry`, pool_maxsize=1 y
    `Connection: close` explícito: mismo resultado, ~100% de fallos en loop.
  - Reemplazando el cliente HTTP por `curl` vía subprocess (para descartar
    que fuera un problema del stack TLS/HTTP de Python en particular): en un
    loop con apenas 0.5s de pausa, TAMBIÉN falló ~100% de las veces (curl
    error 52/56, respuesta vacía/conexión cortada).
  - Conclusión: no es un problema del cliente (urllib vs requests vs curl da
    igual) -- es throttling real por frecuencia de conexión del lado del
    servidor, que se dispara con cualquier ráfaga de pedidos seguidos al
    mismo host sin importar qué librería HTTP se use. El umbral exacto no
    está documentado públicamente.

No se siguió ajustando el delay a fuerza de prueba y error contra un
servicio público de otro país -- eso sería seguir abusando de un sistema que
ya mostró, con hechos, que hay que bajar mucho el ritmo. Este script queda
escrito y correcto pero **no verificado como funcional a un volumen útil**:
probablemente necesita un delay bastante mayor al configurado en
`REQUEST_DELAY_SECONDS`, a determinar con más cuidado (idealmente
consultando a ChileCompra en vez de adivinar por prueba y error). Ver
PROGRESS.md para el estado real -- no asumir que "está listo" solo porque el
código compila y no tiene errores de sintaxis.
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

BASE = "https://api.mercadopublico.cl/APISOCDS/OCDS"
COUNTRY_CODE = "CL"
YEAR, MONTH = 2026, 7
LIST_PAGE_SIZE = 50
MAX_RECORDS = 60
REQUEST_DELAY_SECONDS = 1.5


def http_get_json(url: str, retries: int = 2) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; ContractorAI-research/0.1; +https://github.com/HackCorruption)",
        },
    )
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries:
                time.sleep(2.0 * (attempt + 1))
    raise last_exc


def fetch_index_page(offset: int, limit: int) -> dict:
    url = f"{BASE}/listaOCDSAgnoMesTratoDirecto/{YEAR}/{MONTH:02d}/{offset}/{limit}"
    return http_get_json(url)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
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
                name="Chile",
                ocds_portal_url="https://datos-abiertos.chilecompra.cl/",
                schema_variant="ocds-chilecompra",
                ingestion_method="api",
                active=True,
            )
            db.add(country)
            db.flush()

        source = models.DataSource(
            country_code=COUNTRY_CODE,
            source_type="ocds_api",
            base_url=BASE,
            terms_of_use_notes=(
                "API OCDS publica de ChileCompra (api.mercadopublico.cl/APISOCDS), "
                "sin ticket/token, licencia CC0. Solo 'tratos directos' "
                f"({YEAR}-{MONTH:02d} en esta corrida) -- no incluye licitaciones "
                "publicas ni convenios marco todavia. Verificado en vivo el "
                "2026-08-15."
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
            for row in db.query(models.Contract.ocid)
            .filter(models.Contract.country_code == COUNTRY_CODE, models.Contract.ocid.isnot(None))
            .all()
        }

        buyers_by_key: dict[str, models.Buyer] = {}
        ingested = 0
        skipped_duplicate = 0
        failed = 0
        offset = 0

        while offset < MAX_RECORDS:
            try:
                page = fetch_index_page(offset, LIST_PAGE_SIZE)
            except Exception as exc:  # noqa: BLE001
                print(f"  fallo al pedir indice offset={offset}: {exc}", file=sys.stderr)
                break

            entries = page.get("data", [])
            if not entries:
                break

            for entry in entries:
                ocid = entry.get("ocid")
                url_award = entry.get("urlAward")
                if not ocid or not url_award:
                    continue
                if ocid in existing_ids:
                    skipped_duplicate += 1
                    continue

                try:
                    detail = http_get_json(url_award)
                    time.sleep(REQUEST_DELAY_SECONDS)

                    release = (detail.get("releases") or [{}])[0]
                    award = (release.get("awards") or [{}])[0]
                    buyer_info = release.get("buyer") or {}
                    tender = release.get("tender") or {}
                    value = award.get("value") or {}
                    documents = award.get("documents") or []
                    source_url = documents[0].get("url") if documents else None

                    buyer_name = buyer_info.get("name")
                    buyer_key = normalize(buyer_name)
                    buyer = None
                    if buyer_key:
                        buyer = buyers_by_key.get(buyer_key)
                        if buyer is None:
                            buyer = models.Buyer(
                                country_code=COUNTRY_CODE,
                                external_id=buyer_info.get("id"),
                                name=buyer_name or "Desconocido",
                                normalized_name=buyer_key,
                            )
                            db.add(buyer)
                            db.flush()
                            buyers_by_key[buyer_key] = buyer

                    contract = models.Contract(
                        ocid=ocid,
                        external_id=award.get("id"),
                        country_code=COUNTRY_CODE,
                        source_id=source.id,
                        buyer_id=buyer.id if buyer else None,
                        title=award.get("title"),
                        description=award.get("description") or award.get("title"),
                        category_code=tender.get("procurementMethod"),
                        currency=value.get("currency"),
                        amount_original=value.get("amount"),
                        amount_usd=None,
                        award_date=parse_date(award.get("date") or release.get("date")),
                        procurement_method=tender.get("procurementMethod"),
                        raw_ocds_json=release,
                        source_url=source_url,
                    )
                    db.add(contract)
                    db.flush()

                    db.add(
                        models.Provenance(
                            entity_type="contract",
                            entity_id=contract.id,
                            source_id=source.id,
                            fetched_at=datetime.utcnow(),
                            source_hash=None,
                            raw_payload_uri=url_award,
                        )
                    )

                    existing_ids.add(ocid)
                    ingested += 1
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(f"  fallo en {ocid}: {exc}", file=sys.stderr)

            db.commit()
            offset += LIST_PAGE_SIZE
            print(f"  ... indice offset {offset}: {ingested} contratos nuevos, {skipped_duplicate} ya existian, {failed} fallidos")

        run.finished_at = datetime.utcnow()
        run.records_ingested = ingested
        run.records_failed = failed
        run.status = "completed"
        db.commit()

        print(
            f"Ingesta en vivo Chile completa: {ingested} contratos nuevos, "
            f"{skipped_duplicate} duplicados omitidos, {failed} fallidos."
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
