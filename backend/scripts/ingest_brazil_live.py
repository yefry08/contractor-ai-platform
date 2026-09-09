"""Ingesta EN VIVO de Brasil (API de Dados Abertos de Compras.gov.br).

Fuente verificada el 2026-09-09 contra la API real, no asumida. El endpoint
que se usa acá salió del propio contrato OpenAPI del servicio
(https://dadosabertos.compras.gov.br/v3/api-docs, 77 rutas), y cada
restricción documentada abajo se comprobó ejecutando la consulta:

    GET https://dadosabertos.compras.gov.br/modulo-contratos/1_consultarContratos

Tres cosas que la API impone y que no son evidentes desde afuera:

1. `codigoOrgao` es OBLIGATORIO. No existe "traeme todos los contratos":
   hay que consultar órgano por órgano. Por eso este script primero lista
   órganos (/modulo-uasg/2_consultarOrgao, que a su vez exige `statusOrgao`)
   y recién después itera. Son ~11.960 órganos, así que --orgs acota cuántos
   se recorren por corrida en vez de pretender barrer todo de una.

2. La ventana `dataVigenciaInicialMin`..`Max` no puede superar 365 días. La
   API responde texto plano "Período inicial e final maior que 365 dias."
   (no un JSON de error), así que un rango más largo rompe el parseo.

3. Cuando falta un parámetro obligatorio devuelve 404 con
   {"statusCode":404,"message":"Resource not found"} -- o sea, un 404 acá no
   significa "no hay datos" sino "consulta mal formada".

La respuesta es UTF-8 pese a que el Content-Type no declara charset: se
verificó a nivel de bytes (b'Preg\\xc3\\xa3o' -> U+00E3), no por cómo se ve
en una consola.

`amount_usd` queda en None a propósito: no hay una tasa BRL/USD verificable
por fecha de contrato en este entorno, y la convención del proyecto es
mostrar la moneda original antes que inventar una conversión (mismo criterio
que Colombia y República Dominicana, ver README).
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

COUNTRY_CODE = "BR"
API_ROOT = "https://dadosabertos.compras.gov.br"
CONTRACTS_PATH = "/modulo-contratos/1_consultarContratos"
ORGAOS_PATH = "/modulo-uasg/2_consultarOrgao"

# 500 es el máximo aceptado que se probó (tamanhoPagina=500 devuelve 500 filas).
PAGE_SIZE = 500
MAX_WINDOW_DAYS = 365
DEFAULT_ORGS = 40
DEFAULT_MAX_RECORDS = 5000
REQUEST_DELAY_SECONDS = 0.3


def _get_json(path: str, params: dict) -> dict | None:
    """GET que distingue 'consulta mal formada' de 'no hay datos'.

    Devuelve None cuando la respuesta no es JSON (la API contesta errores de
    validación en texto plano) para que el llamador pueda seguir de largo en
    vez de explotar a mitad de una corrida larga.
    """
    url = f"{API_ROOT}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"  ! HTTP {e.code} en {path} ({params.get('codigoOrgao', '')})")
        return None
    except Exception as e:
        print(f"  ! error de red en {path}: {e}")
        return None

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        print(f"  ! respuesta no-JSON: {body[:120]}")
        return None


def list_orgaos(limit: int) -> list[int]:
    """Códigos de órgano, que son la clave obligatoria para pedir contratos."""
    codes: list[int] = []
    page = 1
    while len(codes) < limit:
        data = _get_json(ORGAOS_PATH, {"pagina": page, "statusOrgao": "true"})
        if not data or not data.get("resultado"):
            break
        for row in data["resultado"]:
            code = row.get("codigoOrgao")
            if code is not None:
                codes.append(code)
                if len(codes) >= limit:
                    break
        if page >= data.get("totalPaginas", 0):
            break
        page += 1
        time.sleep(REQUEST_DELAY_SECONDS)
    return codes


def parse_dt(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def to_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize(name: str | None) -> str:
    return (name or "").strip().lower()


def main():
    parser = argparse.ArgumentParser(description="Ingesta en vivo de Brasil (Compras.gov.br).")
    parser.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS)
    parser.add_argument("--orgs", type=int, default=DEFAULT_ORGS,
                        help="Cuántos órganos recorrer (la API exige consultar de a uno).")
    parser.add_argument("--orgaos", type=str, default=None,
                        help="Códigos de órgano separados por coma, ej. 26000,36000. "
                             "Buena parte del catálogo son entidades paraguas sin "
                             "contratos propios, así que apuntar a órganos concretos "
                             "rinde mucho más que barrer la lista desde el principio.")
    parser.add_argument("--days", type=int, default=MAX_WINDOW_DAYS,
                        help=f"Ventana hacia atrás en días (máximo {MAX_WINDOW_DAYS} por regla de la API).")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY_SECONDS)
    parser.add_argument("--init-only", action="store_true",
                        help="Sólo crear/verificar el registro de país y salir.")
    args = parser.parse_args()

    if args.days > MAX_WINDOW_DAYS:
        raise SystemExit(f"--days no puede superar {MAX_WINDOW_DAYS}: la API rechaza el rango.")

    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        country = db.get(models.Country, COUNTRY_CODE)
        if country is None:
            country = models.Country(
                code=COUNTRY_CODE,
                name="Brasil",
                ocds_portal_url="https://dadosabertos.compras.gov.br/",
                schema_variant="compras-gov-br",
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

        source = models.DataSource(
            country_code=COUNTRY_CODE,
            source_type="api",
            base_url=f"{API_ROOT}{CONTRACTS_PATH}",
            terms_of_use_notes=(
                "API de Dados Abertos de Compras.gov.br (Governo Federal do "
                "Brasil), modulo-contratos. Publica, sin token. Exige "
                "codigoOrgao y una ventana de fechas de hasta 365 dias. "
                "Verificada en vivo el 2026-09-09."
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

        hasta = date.today()
        desde = hasta - timedelta(days=args.days)

        print(f"[api]  {API_ROOT}{CONTRACTS_PATH}")
        print(f"[rango] {desde} .. {hasta}  ({args.days} días)")
        if args.orgaos:
            orgaos = [int(c.strip()) for c in args.orgaos.split(",") if c.strip()]
            print(f"[órganos] {len(orgaos)} indicados a mano")
        else:
            print(f"[órganos] listando hasta {args.orgs}...")
            orgaos = list_orgaos(args.orgs)
            print(f"[órganos] {len(orgaos)} a recorrer")
        print()

        buyers_by_key: dict[str, models.Buyer] = {}
        seen_ids: set[str] = set()
        ingested = 0
        skipped_existing = 0
        failed = 0

        for idx, codigo_orgao in enumerate(orgaos, 1):
            if ingested >= args.max_records:
                break

            page = 1
            while ingested < args.max_records:
                data = _get_json(CONTRACTS_PATH, {
                    "pagina": page,
                    "tamanhoPagina": PAGE_SIZE,
                    "codigoOrgao": codigo_orgao,
                    "dataVigenciaInicialMin": desde.isoformat(),
                    "dataVigenciaInicialMax": hasta.isoformat(),
                })
                if not data:
                    break

                rows = data.get("resultado") or []
                if not rows:
                    break

                for row in rows:
                    if ingested >= args.max_records:
                        break
                    try:
                        if row.get("contratoExcluido") is True:
                            continue

                        external_id = (
                            row.get("numeroControlePncpContrato")
                            or f"{row.get('codigoOrgao')}-{row.get('numeroContrato')}"
                        )
                        if not external_id or external_id in seen_ids:
                            continue

                        already = db.execute(
                            select(models.Contract.id).where(
                                models.Contract.country_code == COUNTRY_CODE,
                                models.Contract.external_id == external_id,
                            )
                        ).first()
                        if already:
                            skipped_existing += 1
                            seen_ids.add(external_id)
                            continue

                        # La unidad gestora es quien realmente compra; el órgano
                        # es el paraguas administrativo por encima.
                        buyer_name = (
                            row.get("nomeUnidadeGestora")
                            or row.get("nomeOrgao")
                            or "Desconhecido"
                        )
                        buyer_key = normalize(buyer_name)
                        buyer = buyers_by_key.get(buyer_key)
                        if buyer is None and buyer_key:
                            buyer = db.execute(
                                select(models.Buyer).where(
                                    models.Buyer.country_code == COUNTRY_CODE,
                                    models.Buyer.normalized_name == buyer_key,
                                )
                            ).scalars().first()
                            if buyer is None:
                                buyer = models.Buyer(
                                    id=str(uuid.uuid4()),
                                    country_code=COUNTRY_CODE,
                                    external_id=str(row.get("codigoUnidadeGestora") or "") or None,
                                    name=buyer_name[:500],
                                    normalized_name=buyer_key[:500],
                                )
                                db.add(buyer)
                                db.flush()
                            buyers_by_key[buyer_key] = buyer

                        objeto = (row.get("objeto") or "").strip()

                        db.add(models.Contract(
                            id=str(uuid.uuid4()),
                            ocid=None,
                            external_id=external_id,
                            country_code=COUNTRY_CODE,
                            source_id=source.id,
                            buyer_id=buyer.id if buyer else None,
                            title=(objeto or row.get("numeroContrato") or "Sem objeto")[:300],
                            description=objeto or None,
                            category_code=row.get("nomeCategoria"),
                            currency="BRL",
                            amount_original=to_float(row.get("valorGlobal")),
                            # Sin tasa BRL/USD verificable por fecha: se deja
                            # el monto en su moneda original.
                            amount_usd=None,
                            award_date=parse_dt(row.get("dataVigenciaInicial")),
                            procurement_method=row.get("nomeModalidadeCompra"),
                            raw_ocds_json=row,
                            source_url=None,
                        ))
                        seen_ids.add(external_id)
                        ingested += 1

                    except Exception as e:
                        failed += 1
                        print(f"  ! fila descartada: {e}")
                        continue

                db.commit()

                if page >= data.get("totalPaginas", 0):
                    break
                page += 1
                time.sleep(args.delay)

            print(f"[{idx}/{len(orgaos)}] órgano {codigo_orgao}: acumulado {ingested}")
            time.sleep(args.delay)

        run.finished_at = datetime.utcnow()
        run.status = "completed"
        run.records_ingested = ingested
        run.records_failed = failed
        db.commit()

        print(f"\n[fin] nuevos={ingested}  ya_existían={skipped_existing}  fallidos={failed}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
