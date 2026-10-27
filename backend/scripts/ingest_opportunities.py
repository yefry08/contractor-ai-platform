"""Open calls to sell to the state, from the three national portals that
publish them as open data before they close (verified 2026-10-24):

  CO  SECOP II "Procesos de Contratación" on datos.gov.co (Socrata,
      dataset p6dx-8zbt): state "Publicado", opening "Abierto", offer
      deadline (fecha_de_recepcion_de) still ahead. Requests for
      information are skipped -- nobody sells anything in one.
  BR  PNCP, Portal Nacional de Contratações Públicas
      (/api/consulta/v1/contratacoes/proposta): contracting processes still
      taking proposals, with closing date and estimated value.
  DO  DGCP open data (/api-dgcp/v1/procesos), newest first: state
      "Proceso publicado" with fecha_fin_recepcion_ofertas ahead, and the
      MSME flag the agency publishes.

Checked and left out: Peru (OECE) and Guatemala (Guatecompras) publish a
process only after its offer period closes, in the API and in the monthly
files alike; Paraguay (DNCP) and Chile (Mercado Público) need a registered
API key; the rest have no open-calls feed we could find.

Each run upserts by (country, external id) and deletes calls whose deadline
has passed, so the table only ever holds what can still be bid on. The cap
per country keeps the nearest deadlines and the free database small.

    cd backend
    python scripts/ingest_opportunities.py               # all three
    python scripts/ingest_opportunities.py CO --cap 500  # one country
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

HEADERS = {"User-Agent": "ContractorAI-ingest/1.0 (+https://github.com/yefry08/contractor-ai-platform)"}
DEFAULT_CAP = 3000

# Deadlines arrive in each country's local time without an offset (CO, BR)
# or in UTC (DO). Stored as naive UTC, like every other timestamp here.
UTC_OFFSET_HOURS = {"CO": -5, "BR": -3}


def get_json(url: str, retries: int = 4):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=90) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            # PNCP answers 429 after ~10 quick pages; it wants a real pause.
            wait = 30 * (attempt + 1) if getattr(exc, "code", None) == 429 else 3 * (attempt + 1)
            print(f"  retry {attempt + 1} in {wait}s after {type(exc).__name__}", file=sys.stderr)
            time.sleep(wait)


def to_utc(value: str | None, country: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt - timedelta(hours=UTC_OFFSET_HOURS.get(country, 0))


def amount(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def fetch_co(cap: int):
    now = datetime.utcnow() + timedelta(hours=UTC_OFFSET_HOURS["CO"])
    where = (
        "estado_del_procedimiento='Publicado' AND estado_de_apertura_del_proceso='Abierto' "
        f"AND fecha_de_recepcion_de > '{now:%Y-%m-%dT%H:%M:%S}' "
        "AND modalidad_de_contratacion != 'Solicitud de información a los Proveedores'"
    )
    offset = 0
    while offset < cap:
        query = urllib.parse.urlencode(
            {"$where": where, "$order": "fecha_de_recepcion_de ASC", "$limit": min(1000, cap - offset), "$offset": offset}
        )
        rows = get_json(f"https://www.datos.gov.co/resource/p6dx-8zbt.json?{query}")
        if not rows:
            return
        for r in rows:
            url = (r.get("urlproceso") or {}).get("url")
            deadline = to_utc(r.get("fecha_de_recepcion_de"), "CO")
            # Some rows link to SECOP's login screen instead of the public
            # notice; a supplier sent there hits a wall, so they're skipped.
            if not url or "/Public/" not in url or not deadline:
                continue
            yield {
                "country_code": "CO",
                "source": "secop2",
                "external_id": r.get("id_del_proceso") or url,
                "title": r.get("nombre_del_procedimiento") or "(sin título)",
                "description": r.get("descripci_n_del_procedimiento"),
                "buyer_name": r.get("entidad"),
                "region": r.get("departamento_entidad"),
                "category": r.get("tipo_de_contrato") if r.get("tipo_de_contrato") not in (None, "No Especificado") else None,
                "procurement_method": r.get("modalidad_de_contratacion"),
                "currency": "COP",
                "estimated_amount": amount(r.get("precio_base")),
                "published_at": to_utc(r.get("fecha_de_publicacion_del"), "CO"),
                "deadline": deadline,
                "for_smes": None,
                "url": url,
            }
        offset += len(rows)


def fetch_br(cap: int):
    until = (datetime.utcnow() + timedelta(days=60)).strftime("%Y%m%d")
    page, seen = 1, 0
    while seen < cap:
        query = urllib.parse.urlencode({"dataFinal": until, "pagina": page, "tamanhoPagina": 50})
        data = get_json(f"https://pncp.gov.br/api/consulta/v1/contratacoes/proposta?{query}")
        rows = data.get("data") or []
        if not rows:
            return
        for r in rows:
            org = r.get("orgaoEntidade") or {}
            unit = r.get("unidadeOrgao") or {}
            deadline = to_utc(r.get("dataEncerramentoProposta"), "BR")
            if not deadline or not org.get("cnpj"):
                continue
            seen += 1
            region = ", ".join(x for x in (unit.get("municipioNome"), unit.get("ufSigla")) if x)
            yield {
                "country_code": "BR",
                "source": "pncp",
                "external_id": r.get("numeroControlePNCP"),
                "title": (r.get("objetoCompra") or "(sem título)").strip(),
                "description": r.get("informacaoComplementar"),
                "buyer_name": org.get("razaoSocial"),
                "region": region or None,
                "category": None,
                "procurement_method": r.get("modalidadeNome"),
                "currency": "BRL",
                "estimated_amount": amount(r.get("valorTotalEstimado")),
                "published_at": to_utc(r.get("dataPublicacaoPncp"), "BR"),
                "deadline": deadline,
                "for_smes": None,
                "url": f"https://pncp.gov.br/app/editais/{org['cnpj']}/{r.get('anoCompra')}/{r.get('sequencialCompra')}",
            }
        if page >= (data.get("totalPaginas") or page):
            return
        page += 1
        time.sleep(1.5)  # stay under PNCP's rate limit


def fetch_do(cap: int, max_pages: int = 120):
    now = datetime.utcnow()
    found = 0
    quiet_pages = 0
    for page in range(1, max_pages + 1):
        rows = (get_json(f"https://datosabiertos.dgcp.gob.do/api-dgcp/v1/procesos?page={page}&limit=100") or {}).get(
            "payload", {}
        ).get("content") or []
        if not rows:
            return
        open_here = 0
        for r in rows:
            deadline = to_utc(r.get("fecha_fin_recepcion_ofertas"), "DO")
            if r.get("estado_proceso") != "Proceso publicado" or not deadline or deadline <= now or not r.get("url"):
                continue
            open_here += 1
            found += 1
            yield {
                "country_code": "DO",
                "source": "dgcp",
                "external_id": r.get("codigo_proceso"),
                "title": (r.get("titulo") or "(sin título)").strip(),
                "description": r.get("descripcion"),
                "buyer_name": r.get("unidad_compra"),
                "region": None,
                "category": r.get("objeto_proceso"),
                "procurement_method": r.get("modalidad"),
                "currency": r.get("divisa") or "DOP",
                "estimated_amount": amount(r.get("monto_estimado")),
                "published_at": to_utc(r.get("fecha_publicacion"), "DO"),
                "deadline": deadline,
                "for_smes": (r.get("dirigido_mipymes") or "").strip().lower() == "si",
                "url": r["url"].replace("//Public/", "/Public/"),
            }
            if found >= cap:
                return
        # Newest first: once several pages in a row have nothing open, the
        # rest of the history is closed processes.
        quiet_pages = quiet_pages + 1 if open_here == 0 else 0
        if quiet_pages >= 10:
            return


FETCHERS = {"CO": fetch_co, "BR": fetch_br, "DO": fetch_do}


def main():
    parser = argparse.ArgumentParser(description="Ingesta de llamados abiertos (CO, BR, DO).")
    parser.add_argument("countries", nargs="*", default=list(FETCHERS))
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP)
    args = parser.parse_args()

    Base.metadata.create_all(engine)  # adds the opportunities/inquiries tables on first run
    db = SessionLocal()
    try:
        removed = db.execute(delete(models.Opportunity).where(models.Opportunity.deadline < datetime.utcnow())).rowcount
        db.commit()
        print(f"[limpieza] {removed} llamados vencidos eliminados")

        for code in args.countries:
            existing = {
                o.external_id: o
                for o in db.execute(select(models.Opportunity).where(models.Opportunity.country_code == code)).scalars()
            }
            new = updated = failed = 0
            try:
                for item in FETCHERS[code](args.cap):
                    if not item["external_id"]:
                        continue
                    item["title"] = item["title"][:2000]
                    item["url"] = item["url"][:600]
                    row = existing.get(item["external_id"])
                    if row is None:
                        row = models.Opportunity(**item)
                        db.add(row)
                        existing[item["external_id"]] = row
                        new += 1
                    else:
                        for k, v in item.items():
                            setattr(row, k, v)
                        row.fetched_at = datetime.utcnow()
                        updated += 1
                    if (new + updated) % 500 == 0:
                        db.commit()
            except Exception as exc:  # noqa: BLE001
                # One portal failing must not lose what the others brought.
                failed += 1
                print(f"[{code}] error: {type(exc).__name__}: {exc}", file=sys.stderr)
            db.commit()
            print(f"[{code}] nuevos={new} actualizados={updated} errores={failed}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
