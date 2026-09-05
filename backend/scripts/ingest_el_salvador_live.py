"""Ingesta EN VIVO de El Salvador, vía la API pública de COMPRASAL (DINAC).

    https://www.comprasal.gob.sv/api/v1/publico/obtener/procesos/publicos

Cómo se encontró (importa, porque no se adivina)
------------------------------------------------
El relevamiento previo dio "hay API pero sus rutas no son públicas": cualquier
ruta bajo `/api/v1/` devuelve `{"message":"Recurso no encontrado"}` en JSON, o
sea que el backend está y contesta, pero no hay documentación y probar nombres
(`/api/v1/releases`, `/api/ocds`, `/api/v1/contratos`) no acertó ninguno.

Se resolvió abriendo el portal en un navegador y leyendo sus propias llamadas
de red. La ruta real es `/api/v1/publico/obtener/procesos/publicos` — el
namespace `publico` es explícito y no requiere autenticación. Se llega ahí
desde el enlace "Registro de adjudicaciones" de la portada (`/procesos-publicos`).
No se usó ninguna parte autenticada del sistema.

Qué es cada fila
----------------
Un **renglón adjudicado**, no un contrato entero: varias filas comparten
`codigo_proceso` con montos distintos (verificado: `1700-2026-P0119` aparece con
875, 975 y 2.646). El `id` de la fila es único y se usa como clave de
idempotencia.

Moneda
------
No hay campo de moneda en la respuesta. El Salvador está dolarizado desde 2001,
así que `monto` es USD. Es **el primer país del corpus con montos nativos en
dólares**: a diferencia de Paraguay, Colombia, R. Dominicana y Perú, acá se
puede llenar `amount_usd` sin inventar una tasa de cambio, y a diferencia de
Costa Rica no hace falta que un sistema externo lo convierta.

Datos personales que esta fuente publica y este script NO guarda
----------------------------------------------------------------
La respuesta trae `accionistas` y `beneficiario` con nombres completos de
personas físicas (accionistas de la empresa proveedora y beneficiario final).
Es información pública, publicada por el propio Estado para transparencia, y
para investigación de corrupción es valiosa.

Aun así **no se almacena**, por dos razones concretas: ningún análisis de la
plataforma la usa (la comparación de precios y la concentración de mercado
funcionan a nivel empresa), y guardar datos personales de particulares implica
obligaciones de retención, exactitud y rectificación que este proyecto no tiene
resueltas. Se guarda sólo la razón social del proveedor, igual que en el resto
de los países.

Si en algún momento se decide incorporarla, que sea una decisión explícita con
su propia política de datos, no un efecto colateral de este conector.

Ritmo
-----
La API tarda ~9-10 s por página de 100. No devuelve `total`, así que se pagina
hasta que una página venga incompleta. Con ese costo por pedido, el techo por
defecto es conservador; se sube con --max-pages.

Uso:
    python backend/scripts/ingest_el_salvador_live.py
    python backend/scripts/ingest_el_salvador_live.py --max-pages 100 --delay 1.0
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

BASE = "https://www.comprasal.gob.sv/api/v1/publico/obtener/procesos/publicos"
TIPOS_URL = "https://www.comprasal.gob.sv/api/v1/publico/tipos/contrato"
COUNTRY_CODE = "SV"
PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 40
# La API responde en ~9-10 s por pagina de 100. Sumar una pausa larga encima no
# aporta: el propio costo del pedido ya espacia las llamadas de sobra.
DEFAULT_DELAY_SECONDS = 0.5
MAX_CONSECUTIVE_FAILURES = 3

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; ContractorAI-research/0.1; +https://github.com/HackCorruption)",
}


def http_get_json(url: str, retries: int = 2) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < retries:
                time.sleep(2.0 * (attempt + 1))
    raise last  # type: ignore[misc]


def fetch_page(page: int) -> list[dict]:
    qs = urllib.parse.urlencode({"pagination": "true", "page": page, "per_page": PAGE_SIZE})
    data = http_get_json(f"{BASE}?{qs}")
    return data.get("data") or []


def fetch_contract_types() -> dict[int, str]:
    """id_forma_contratacion -> nombre legible. Sin esto queda un entero suelto."""
    try:
        payload = http_get_json(TIPOS_URL)
    except Exception as exc:  # noqa: BLE001
        print(f"  no se pudo traer tipos/contrato ({exc}); se guardan sin nombre", file=sys.stderr)
        return {}
    rows = payload.get("data") if isinstance(payload, dict) else payload
    return {r["id"]: r.get("nombre", "").strip() for r in (rows or []) if r.get("id") is not None}


def to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def normalize(name: str | None) -> str:
    return (name or "").strip().lower()


def safe_commit(db, label: str) -> bool:
    """Igual que en el conector de Perú: esta base corta conexiones de forma
    intermitente y, sin rollback, el primer corte invalida la sesión y hace
    fallar todos los commits siguientes."""
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


def slim_payload(row: dict, method_name: str | None) -> dict:
    """Sólo lo que no tiene columna todavía.

    Se excluyen a proposito `accionistas` y `beneficiario`: son nombres de
    personas fisicas y ningun analisis de la plataforma los usa (ver el
    docstring del modulo).
    """
    proceso = row.get("proceso_compra") or {}
    proveedor = row.get("proveedor") or {}
    return {
        "row_id": row.get("id"),
        "codigo_proceso": proceso.get("codigo_proceso"),
        "proveedor": {
            "id": proveedor.get("id_proveedor") or proveedor.get("id"),
            "nombre": proveedor.get("nombre"),
            "nombre_comercial": proveedor.get("nombre_comercial"),
        },
        "forma_contratacion": method_name,
        "id_forma_contratacion": proceso.get("id_forma_contratacion"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingesta en vivo de El Salvador (COMPRASAL).")
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
                name="El Salvador",
                ocds_portal_url="https://www.comprasal.gob.sv/",
                schema_variant="comprasal-publico-v1",
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
                "COMPRASAL (DINAC, El Salvador), namespace /api/v1/publico -- "
                "publico, sin autenticacion. La ruta no esta documentada: se "
                "encontro leyendo las llamadas de red que hace el propio portal "
                "en /procesos-publicos ('Registro de adjudicaciones'). No se uso "
                "ninguna parte autenticada. Cada fila es un renglon adjudicado, "
                "no un contrato completo. Sin campo de moneda: El Salvador esta "
                "dolarizado desde 2001, los montos son USD. La respuesta incluye "
                "accionistas y beneficiario final con nombres de personas "
                "fisicas, que este conector deliberadamente no almacena. "
                "Verificado en vivo el 2026-09-04: ~9-10 s por pagina de 100."
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

        methods = fetch_contract_types()
        print(f"  formas de contratacion: {len(methods)}")

        existing_ids = {
            row[0]
            for row in db.query(models.Contract.external_id)
            .filter(models.Contract.country_code == COUNTRY_CODE, models.Contract.external_id.isnot(None))
            .all()
        }

        buyers_by_key: dict[str, models.Buyer] = {}
        ingested = 0
        skipped_duplicate = 0
        skipped_no_amount = 0
        failed = 0
        consecutive_failures = 0
        page = args.start_page
        last_page = page

        while page < args.start_page + args.max_pages:
            try:
                rows = fetch_page(page)
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

            if not rows:
                break
            last_page = page

            for row in rows:
                try:
                    external_id = str(row.get("id")) if row.get("id") is not None else None
                    if not external_id or external_id in existing_ids:
                        skipped_duplicate += 1
                        continue

                    amount = to_float(row.get("monto"))
                    if amount is None or amount <= 0:
                        skipped_no_amount += 1
                        continue

                    proceso = row.get("proceso_compra") or {}
                    institucion = row.get("institucion") or proceso.get("Institucion") or {}
                    buyer_name = institucion.get("nombre")
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
                                external_id=str(institucion.get("codigo") or institucion.get("id") or "") or None,
                                name=buyer_name or "Desconocido",
                                normalized_name=buyer_key,
                            )
                            db.add(buyer)
                        buyers_by_key[buyer_key] = buyer

                    method_name = methods.get(proceso.get("id_forma_contratacion"))
                    title = proceso.get("nombre_proceso")

                    contract_id = str(uuid.uuid4())
                    contract = models.Contract(
                        id=contract_id,
                        ocid=None,
                        external_id=external_id,
                        country_code=COUNTRY_CODE,
                        source_id=source.id,
                        buyer_id=buyer.id if buyer else None,
                        title=title,
                        description=title,
                        category_code=None,
                        currency="USD",
                        amount_original=amount,
                        # Unico pais del corpus donde amount_usd no necesita una
                        # tasa de cambio: el pais esta dolarizado, el monto YA
                        # esta en dolares.
                        amount_usd=amount,
                        award_date=parse_date(proceso.get("fecha_adjudicacion")),
                        procurement_method=method_name,
                        raw_ocds_json=slim_payload(row, method_name),
                        source_url="https://www.comprasal.gob.sv/procesos-publicos",
                    )
                    db.add(contract)

                    db.add(
                        models.Provenance(
                            entity_type="contract",
                            entity_id=contract_id,
                            source_id=source.id,
                            fetched_at=datetime.utcnow(),
                            source_hash=None,
                            raw_payload_uri=f"{BASE}?page={page}&per_page={PAGE_SIZE}",
                        )
                    )

                    existing_ids.add(external_id)
                    ingested += 1
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(f"  fila fallida: {exc}", file=sys.stderr)

            if safe_commit(db, f"pagina {page}"):
                print(f"  ... pagina {page}: {ingested} renglones ingeridos")
            else:
                buyers_by_key.clear()

            if len(rows) < PAGE_SIZE:
                break

            page += 1
            time.sleep(args.delay)

        run.finished_at = datetime.utcnow()
        run.status = "ok" if failed == 0 else "partial"
        run.records_ingested = ingested
        run.records_failed = failed
        safe_commit(db, "cierre de la corrida")

        print(
            f"\nEl Salvador: {ingested} renglones ingeridos "
            f"({skipped_duplicate} duplicados, {skipped_no_amount} sin monto, {failed} fallidos) "
            f"hasta la pagina {last_page}"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
