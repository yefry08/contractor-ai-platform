"""Fills category_code and procurement_method for República Dominicana --
0 of 2000 ingested contracts had either (see PROGRESS.md 2026-08-18), which
is why the /tenders price-benchmark module couldn't show DR data.

Source: the official PIDA dataset "Datos de procesos publicados en el
Sistema Electrónico de Contrataciones Públicas (SECP)", published by the
DGCP on datos.gob.do (https://datos.gob.do/dataset/datos-procesos-publicados,
tipped by the user, ODbL license, ~233MB CSV, 2015-2026, updated semestrally).
It's PROCESS-level data (OBJETO_PROCESO: "Servicios"/"Bienes", MODALIDAD:
"Contratación Menor"/"Comparación de Precios"/etc.), distinct from the
CONTRACT-level `/contratos` endpoint the live ingestion script uses -- joined
here via `codigo_proceso`, which the live ingestion already stores in each
contract's raw_ocds_json but never surfaced into a real column.

Purely additive: only fills category_code/procurement_method where they're
currently NULL. Never touches amount_original/currency/anything else --
MONTO_ESTIMADO in this dataset is an *estimate* at publication time, not the
actual contracted amount, and conflating the two would be a real data
integrity regression, not an enrichment.

dgcp.gob.do (unlike datosabiertos.dgcp.gob.do, the API host the live
ingestion uses) sits behind Cloudflare's basic bot-fight mode: blocks
urllib's default User-Agent outright, passes fine with a real browser one --
same finding as ingest_dominican_republic_live.py, not re-litigated here.
"""

import csv
import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.db import SessionLocal  # noqa: E402

CSV_URL = (
    "https://www.dgcp.gob.do/new_dgcp/documentos/da/"
    "Procesos%20publicados%20en%20el%20Sistema%20Electro%CC%81nico%20de%20"
    "Contrataciones%20Pu%CC%81blicas%20(SECP),%20DGCP,%202015%20-%202026.csv"
)
# Same live API the main ingestion (ingest_dominican_republic_live.py) uses
# for /contratos -- /procesos carries the same objeto_proceso/modalidad
# fields as the PIDA CSV but current-day, closing the gap the semi-annual
# CSV snapshot leaves for anything published after its last refresh.
PROCESOS_API = "https://datosabiertos.dgcp.gob.do/api-dgcp/v1/procesos"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}
CACHE_PATH = Path(__file__).resolve().parent / "_pida_secp_processes.csv"
COUNTRY_CODE = "DO"
REQUEST_DELAY_SECONDS = 0.25


def download(path: Path) -> None:
    print(f"Downloading {CSV_URL} ...")
    req = urllib.request.Request(CSV_URL, headers=HEADERS)
    total = 0
    with urllib.request.urlopen(req, timeout=180) as resp, open(path, "wb") as f:
        while chunk := resp.read(1024 * 1024):
            f.write(chunk)
            total += len(chunk)
    print(f"Downloaded {total / 1_000_000:.1f} MB")


def build_csv_lookup(path: Path) -> dict[str, tuple[str | None, str | None]]:
    """codigo_proceso -> (objeto_proceso, modalidad)"""
    lookup: dict[str, tuple[str | None, str | None]] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = row.get("CODIGO_PROCESO")
            if code:
                lookup[code] = (row.get("OBJETO_PROCESO") or None, row.get("MODALIDAD") or None)
    return lookup


def fetch_live_lookup(oldest_needed: date, page_size: int = 500, max_pages: int = 400) -> dict[str, tuple[str | None, str | None]]:
    """Same fields as the CSV, from the live /procesos endpoint the main
    ingestion script already uses for /contratos -- pages are ordered
    newest-first, so this stops as soon as a page's publication dates drop
    below what's still needed instead of paginating all 600k+ records."""
    lookup: dict[str, tuple[str | None, str | None]] = {}
    page = 1
    while page <= max_pages:
        req = urllib.request.Request(f"{PROCESOS_API}?limit={page_size}&page={page}", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
        content = body.get("payload", {}).get("content", [])
        if not content:
            break
        oldest_on_page = None
        for row in content:
            code = row.get("codigo_proceso")
            if code:
                lookup[code] = (row.get("objeto_proceso") or None, row.get("modalidad") or None)
            pub = row.get("fecha_publicacion")
            if pub:
                pub_date = date.fromisoformat(pub[:10])
                oldest_on_page = pub_date if oldest_on_page is None else min(oldest_on_page, pub_date)
        print(f"  live page {page}: {len(content)} records, oldest fecha_publicacion {oldest_on_page}")
        if oldest_on_page is not None and oldest_on_page < oldest_needed:
            break
        page += 1
        time.sleep(REQUEST_DELAY_SECONDS)
    return lookup


def apply_lookup(db, rows: list, lookup: dict[str, tuple[str | None, str | None]], source_label: str) -> tuple[int, int, int]:
    matched = filled_category = filled_method = 0
    for contract in rows:
        if contract.category_code is not None and contract.procurement_method is not None:
            continue  # already fully filled by an earlier pass
        codigo_proceso = (contract.raw_ocds_json or {}).get("codigo_proceso")
        if not codigo_proceso or codigo_proceso not in lookup:
            continue
        matched += 1
        objeto, modalidad = lookup[codigo_proceso]
        if objeto and contract.category_code is None:
            contract.category_code = objeto
            filled_category += 1
        if modalidad and contract.procurement_method is None:
            contract.procurement_method = modalidad
            filled_method += 1
    db.commit()
    print(f"[{source_label}] matched {matched:,}, filled category_code on {filled_category:,}, procurement_method on {filled_method:,}")
    return matched, filled_category, filled_method


def main() -> None:
    if not CACHE_PATH.exists():
        download(CACHE_PATH)
    else:
        print(f"Reusing already-downloaded {CACHE_PATH} (delete it to force a fresh download)")

    csv_lookup = build_csv_lookup(CACHE_PATH)
    print(f"Loaded {len(csv_lookup):,} process records from the PIDA/SECP CSV snapshot")

    db = SessionLocal()
    try:
        rows = db.execute(
            select(models.Contract).where(
                models.Contract.country_code == COUNTRY_CODE,
                models.Contract.raw_ocds_json.isnot(None),
            )
        ).scalars().all()
        print(f"{len(rows):,} DR contracts in the database")

        apply_lookup(db, rows, csv_lookup, "CSV snapshot")

        still_missing = [r for r in rows if r.category_code is None or r.procurement_method is None]
        if still_missing:
            oldest_needed = min(
                r.award_date for r in still_missing if r.award_date is not None
            ) if any(r.award_date for r in still_missing) else date.today()
            print(f"\n{len(still_missing):,} contracts still missing data -- trying the live /procesos API back to {oldest_needed}")
            live_lookup = fetch_live_lookup(oldest_needed)
            print(f"Loaded {len(live_lookup):,} process records from the live API")
            apply_lookup(db, still_missing, live_lookup, "live API")

        final_missing_category = sum(1 for r in rows if r.category_code is None)
        final_missing_method = sum(1 for r in rows if r.procurement_method is None)
        print(f"\nStill missing category_code: {final_missing_category:,} / {len(rows):,}")
        print(f"Still missing procurement_method: {final_missing_method:,} / {len(rows):,}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
