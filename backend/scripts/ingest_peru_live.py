"""Ingesta EN VIVO de Perú, vía la API OCDS nativa del Portal de Contrataciones
Abiertas de la compra pública peruana (OECE, ex-OSCE), sobre datos de SEACE.

    https://contratacionesabiertas.oece.gob.pe/api/v1/releases

OJO CON EL DOMINIO: el relevamiento de Fase 2
(`docs/architecture/fase2-relevamiento-paises.md`) apunta a
`contratacionesabiertas.osce.gob.pe`, que hoy **no resuelve** -- el organismo
pasó de llamarse OSCE a OECE y el dominio cambió con él. Verificado el
2026-09-04: el dominio viejo devuelve error de conexión, el nuevo responde 200.

Verificado en vivo antes de escribir este script (2026-09-04):

    curl "https://contratacionesabiertas.oece.gob.pe/api/v1/releases?page=500"
    -> release package OCDS 1.1, 20 releases, 6 con `awards`

Qué se ingiere, y qué NO
------------------------
El feed mezcla etapas: la mayoría de los releases recientes son
`planning`+`tender` (convocatorias), y sólo una fracción llega a `award`.
Este script ingiere **únicamente releases con `awards`**, y toma el monto de
`award.value.amount` -- el monto EFECTIVAMENTE adjudicado.

Esa distinción no es cosmética. `tender.value` es el valor referencial
(presupuesto estimado antes de licitar) y suele diferir del adjudicado: en la
muestra verificada, un proceso con valor referencial 197.176,62 PEN se
adjudicó en 197.100,00 PEN. Mezclar valores referenciales de Perú con montos
adjudicados del resto de los países rompería la comparación de
`/analyze/compare`, que asume que todos los montos son de la misma naturaleza.
Ante la duda, se prefiere menos volumen antes que un monto que no significa lo
mismo que el de al lado.

Moneda: PEN, sin convertir. No hay una tasa PEN->USD verificable por fecha en
este proyecto, así que se guarda `amount_original` + `currency` y se deja
`amount_usd` en NULL -- igual criterio que Colombia, Paraguay y R. Dominicana.

Lo que Perú aporta y los otros cuatro países no tienen
------------------------------------------------------
1. `tender.mainProcurementCategory` con un reparto real (goods/services/works).
   Es el primer país del corpus con un eje de categoría que de verdad
   discrimina: Paraguay tiene una sola categoría para sus 5.282 contratos.
2. `parties[].roles=[supplier]` con RUC (identificador tributario). Es la
   primera fuente del proyecto con proveedor identificado, lo que hoy falta
   para que "Favoritismo de Proveedores" mida proveedores y no compradores.
3. `items[].classification` con esquema CUBSO (Catálogo Único de Bienes,
   Servicios y Obras) -- el objeto de compra real.

Nada de (2) ni (3) tiene todavía columna en el modelo. Para no perderlo y no
tener que volver a bajar todo cuando exista la migración, el release completo
se guarda en `raw_ocds_json`.

Paginación
----------
`?page=N`, 20 releases por página. La API deja de devolver resultados alrededor
de la página ~500-900 (verificado: 500 devuelve datos, 900 devuelve vacío), así
que no es un backfill histórico completo sino una ventana reciente. El script
pagina hasta que la API devuelve vacío o hasta `--max-pages`, lo que ocurra
primero.

Uso:
    python backend/scripts/ingest_peru_live.py
    python backend/scripts/ingest_peru_live.py --max-pages 400 --delay 0.5
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

BASE = "https://contratacionesabiertas.oece.gob.pe/api/v1/releases"
COUNTRY_CODE = "PE"
DEFAULT_MAX_PAGES = 500
DEFAULT_DELAY_SECONDS = 0.4
# Tras esta cantidad de páginas fallidas seguidas se corta. Una API pública y
# gratuita de otro país que empieza a fallar en serie está pidiendo que pares
# (ver la investigación de throttling en ingest_chile_live.py), no que insistas.
MAX_CONSECUTIVE_FAILURES = 3

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; ContractorAI-research/0.1; +https://github.com/HackCorruption)",
}


def fetch_page(page: int, retries: int = 2) -> dict:
    url = f"{BASE}?{urllib.parse.urlencode({'page': page})}"
    req = urllib.request.Request(url, headers=HEADERS)
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last  # type: ignore[misc]


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def normalize(name: str | None) -> str:
    return (name or "").strip().lower()


def safe_commit(db, label: str) -> bool:
    """Confirma lo acumulado; ante un corte de conexión hace rollback y sigue.

    La base de este proyecto corta conexiones de forma intermitente (plan
    gratuito). Sin esto, el primer corte deja la sesión en estado inválido y
    *todos* los commits siguientes fallan con PendingRollbackError: una corrida
    de 500 páginas se perdía entera a partir del minuto en que se cayó la
    conexión. Verificado: la corrida inicial murió en la página 393 por
    exactamente eso.

    Se pierde como mucho el lote no confirmado, y la próxima corrida lo vuelve
    a traer porque la ingesta es idempotente por `ocid`.
    """
    try:
        db.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  commit fallido en {label}: {type(exc).__name__}; rollback y sigo", file=sys.stderr)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False


def pick_award(release: dict) -> dict | None:
    """El award adjudicado con monto positivo, o None.

    Un release puede traer varios awards (lotes). Se toma el de mayor monto:
    ingerir el proceso una sola vez con su adjudicación principal es preferible
    a inventar N contratos que comparten ocid y romperían la idempotencia.
    """
    best = None
    best_amount = 0.0
    for award in release.get("awards") or []:
        amount = ((award or {}).get("value") or {}).get("amount")
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            continue
        if amount > best_amount:
            best, best_amount = award, amount
    return best


def suppliers_of(release: dict, award: dict) -> list[dict]:
    """Proveedores con su RUC, del award o de `parties` como respaldo."""
    by_id = {
        p.get("id"): p
        for p in (release.get("parties") or [])
        if "supplier" in (p.get("roles") or [])
    }
    out: list[dict] = []
    for s in award.get("suppliers") or []:
        party = by_id.get(s.get("id")) or {}
        ident = party.get("identifier") or {}
        out.append(
            {
                "name": s.get("name") or party.get("name"),
                "id": s.get("id") or party.get("id"),
                "scheme": ident.get("scheme"),
                "identifier": ident.get("id"),
            }
        )
    if not out:
        for p in by_id.values():
            ident = p.get("identifier") or {}
            out.append(
                {
                    "name": p.get("name"),
                    "id": p.get("id"),
                    "scheme": ident.get("scheme"),
                    "identifier": ident.get("id"),
                }
            )
    return out


def slim_payload(release: dict, award: dict) -> dict:
    """Sólo lo que todavía no tiene columna propia y costaría caro re-bajar.

    Guardar el release entero salía 10,5 KB por contrato -- 15 veces lo que
    ocupa República Dominicana, y ~26 MB proyectados sobre una base de plan
    gratuito. El 90% de ese peso son `parties` (22 por release), `documents` y
    períodos que ninguna consulta lee. Esto conserva proveedor (con RUC) y
    clasificación CUBSO, que son las dos cosas que hoy no tienen columna y que
    habría que volver a descargar entero el feed para recuperar.
    """
    tender = release.get("tender") or {}
    items = []
    for it in (tender.get("items") or [])[:5]:
        cls = it.get("classification") or {}
        items.append(
            {
                "description": it.get("description"),
                "classification_id": cls.get("id"),
                "classification_scheme": cls.get("scheme"),
                "classification_description": cls.get("description"),
                "quantity": it.get("quantity"),
                "unit": (it.get("unit") or {}).get("name"),
            }
        )
    return {
        "ocid": release.get("ocid"),
        "tag": release.get("tag"),
        "suppliers": suppliers_of(release, award),
        "items": items,
        "tender_value": (tender.get("value") or {}).get("amount"),
        "award_value": (award.get("value") or {}).get("amount"),
        "procuring_entity_id": (tender.get("procuringEntity") or {}).get("id"),
        "sources": [s.get("id") for s in (release.get("sources") or [])],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingesta en vivo de Perú (OECE/SEACE, OCDS).")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        country = db.get(models.Country, COUNTRY_CODE)
        if country is None:
            country = models.Country(
                code=COUNTRY_CODE,
                name="Perú",
                ocds_portal_url="https://contratacionesabiertas.oece.gob.pe/",
                schema_variant="ocds-1.1-oece",
                ingestion_method="api",
                active=True,
            )
            db.add(country)
            db.flush()

        source = models.DataSource(
            country_code=COUNTRY_CODE,
            source_type="api",
            base_url=BASE,
            terms_of_use_notes=(
                "Portal de Contrataciones Abiertas de la compra publica del Peru "
                "(OECE, ex-OSCE), OCDS 1.1 nativo sobre SEACE v1/v2/v3. "
                "Dominio verificado 2026-09-04: osce.gob.pe ya no resuelve, "
                "oece.gob.pe si. Paginacion ?page=N, 20 releases por pagina, "
                "se agota alrededor de la pagina 500-900. Solo se ingieren "
                "releases con `awards`, usando award.value.amount (monto "
                "adjudicado), nunca tender.value (valor referencial)."
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

        existing_ocids = {
            row[0]
            for row in db.query(models.Contract.ocid)
            .filter(models.Contract.country_code == COUNTRY_CODE, models.Contract.ocid.isnot(None))
            .all()
        }

        buyers_by_key: dict[str, models.Buyer] = {}
        ingested = 0
        skipped_duplicate = 0
        skipped_no_award = 0
        failed = 0
        consecutive_failures = 0
        page = args.start_page
        last_page = page

        while page < args.start_page + args.max_pages:
            try:
                data = fetch_page(page)
                consecutive_failures = 0
            except Exception as exc:  # noqa: BLE001
                consecutive_failures += 1
                print(f"  fallo al pedir pagina {page}: {exc}", file=sys.stderr)
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print(f"  {consecutive_failures} fallos seguidos, se corta", file=sys.stderr)
                    break
                page += 1
                time.sleep(args.delay * 3)
                continue

            releases = data.get("releases") or []
            if not releases:
                break
            last_page = page

            for release in releases:
                try:
                    ocid = release.get("ocid")
                    award = pick_award(release)
                    if not ocid or award is None:
                        skipped_no_award += 1
                        continue
                    # El mismo ocid aparece una vez por etapa (planning, tender,
                    # award...). Sin este corte se insertaria el mismo proceso
                    # varias veces dentro de una sola corrida.
                    if ocid in existing_ocids:
                        skipped_duplicate += 1
                        continue

                    tender = release.get("tender") or {}
                    buyer_obj = release.get("buyer") or {}
                    buyer_name = buyer_obj.get("name") or (tender.get("procuringEntity") or {}).get("name")
                    buyer_key = normalize(buyer_name)

                    buyer = None
                    if buyer_key:
                        buyer = buyers_by_key.get(buyer_key)
                        if buyer is None:
                            buyer = (
                                db.query(models.Buyer)
                                .filter(
                                    models.Buyer.country_code == COUNTRY_CODE,
                                    models.Buyer.normalized_name == buyer_key,
                                )
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
                        buyers_by_key[buyer_key] = buyer

                    value = award.get("value") or {}
                    title = tender.get("title") or tender.get("description")
                    description = tender.get("description") or tender.get("title")

                    contract_id = str(uuid.uuid4())
                    contract = models.Contract(
                        id=contract_id,
                        ocid=ocid,
                        external_id=ocid,
                        country_code=COUNTRY_CODE,
                        source_id=source.id,
                        buyer_id=buyer.id if buyer else None,
                        title=title,
                        description=description,
                        # Unico pais del corpus con un reparto real
                        # goods/services/works en vez de una constante.
                        category_code=tender.get("mainProcurementCategory"),
                        currency=value.get("currency") or "PEN",
                        amount_original=float(value.get("amount")),
                        amount_usd=None,
                        award_date=parse_date(award.get("date")) or parse_date(release.get("date")),
                        procurement_method=tender.get("procurementMethodDetails"),
                        raw_ocds_json=slim_payload(release, award),
                        source_url=f"{BASE}?{urllib.parse.urlencode({'ocid': ocid})}",
                    )
                    db.add(contract)

                    db.add(
                        models.Provenance(
                            entity_type="contract",
                            entity_id=contract_id,
                            source_id=source.id,
                            fetched_at=datetime.utcnow(),
                            source_hash=None,
                            raw_payload_uri=f"{BASE}?page={page}",
                        )
                    )

                    existing_ocids.add(ocid)
                    ingested += 1
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(f"  release fallido: {exc}", file=sys.stderr)

            if ingested and ingested % 200 < 20:
                if safe_commit(db, f"pagina {page}"):
                    print(f"  ... pagina {page}: {ingested} adjudicaciones ingeridas")
                else:
                    # El rollback descarta lo pendiente, incluidos los compradores
                    # nuevos de este lote. Si se conservara la cache, los
                    # siguientes contratos apuntarian a filas que ya no existen.
                    buyers_by_key.clear()

            page += 1
            time.sleep(args.delay)

        run.finished_at = datetime.utcnow()
        run.status = "ok" if failed == 0 else "partial"
        run.records_ingested = ingested
        run.records_failed = failed
        # IngestionRun no tiene columna de notas: el desglose va al stdout de la
        # corrida, no a la base. Asignar run.notes aqui no fallaria, pero
        # SQLAlchemy lo dejaria como atributo suelto de Python y el dato se
        # perderia en silencio al cerrar la sesion.
        safe_commit(db, "cierre de la corrida")

        print(
            f"\nPeru: {ingested} adjudicaciones ingeridas "
            f"({skipped_duplicate} duplicadas, {skipped_no_award} sin adjudicacion, {failed} fallidas) "
            f"hasta la pagina {last_page}"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
