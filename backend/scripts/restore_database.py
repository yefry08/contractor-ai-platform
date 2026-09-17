"""Restore a dump made by backup_database.py into an empty Postgres database.

Companion to backup_database.py, whose own docstring already anticipated
needing this: "Render's free PostgreSQL is deleted when it expires, not
merely stopped" -- which is exactly what happened to contractor-ai-db on
2026-09-16, forcing a migration to a new host.

Tables load in FK dependency order (parents before children); loading a
child first would fail on its foreign key the moment a row references a
parent id that doesn't exist yet:

    countries -> data_sources, buyers -> contracts -> predictions,
    statistical_flags, anomalies, citizen_reports, contract_documents
    -> provenance, api_keys

The target database must already have the schema (run once beforehand:
`python -c "from app.db import Base, engine; from app import models;
Base.metadata.create_all(engine)"`, or let any ingest script's own
Base.metadata.create_all(engine) call do it) -- this script only loads
rows, it never creates tables, so restoring into a database with the wrong
or missing schema fails loudly on the first COPY rather than silently
creating something inconsistent with the ORM models.

    python backend/scripts/restore_database.py backups/20260903T133311Z

DATABASE_URL is read from backend/.env (or the environment) -- the same
convention as backup_database.py. Prints a per-table row count next to the
manifest's recorded count so a short or truncated CSV is caught immediately
rather than discovered later as a mysteriously incomplete corpus.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[2]

# Parents before children, matching the FK graph in app/models.py.
TABLE_ORDER = [
    "countries",
    "data_sources",
    "buyers",
    "contracts",
    "ingestion_runs",
    "predictions",
    "statistical_flags",
    "anomalies",
    "citizen_reports",
    "contract_documents",
    "provenance",
    "api_keys",
]


def load_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    env_path = REPO_ROOT / "backend" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip("'\"")

    sys.exit("DATABASE_URL not set and not found in backend/.env")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup_dir", help="directory produced by backup_database.py")
    parser.add_argument(
        "--yes", action="store_true",
        help="skip the confirmation prompt (for non-interactive runs)",
    )
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir)
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        sys.exit(f"no manifest.json in {backup_dir} -- is this a backup_database.py output dir?")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    missing = [t for t in TABLE_ORDER if t not in manifest["tables"]]
    extra = [t for t in manifest["tables"] if t not in TABLE_ORDER]
    if missing or extra:
        sys.exit(
            f"TABLE_ORDER is out of sync with the backup's schema -- missing {missing}, "
            f"unexpected {extra}. Update TABLE_ORDER (and its FK ordering) before restoring."
        )

    url = load_database_url()
    # Never print the URL: it carries the password.
    print(f"restoring {backup_dir} (taken {manifest['taken_at']}) into database (host hidden)")

    if not args.yes:
        answer = input("This writes into the CURRENTLY CONFIGURED DATABASE_URL. Continue? [y/N] ")
        if answer.strip().lower() != "y":
            print("aborted")
            return 1

    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            # Confirms the target is actually empty before writing, rather
            # than silently duplicating rows into a database that already
            # has some -- a restore is meant to run once, into a fresh schema.
            for table in TABLE_ORDER:
                cur.execute(f'SELECT count(*) FROM "{table}"')
                existing = cur.fetchone()[0]
                if existing > 0:
                    conn.rollback()
                    sys.exit(
                        f'"{table}" already has {existing} rows. Refusing to restore into a '
                        f"non-empty table -- truncate it first if this is intentional."
                    )

            total = 0
            for table in TABLE_ORDER:
                csv_path = backup_dir / f"{table}.csv"
                expected = manifest["tables"][table]["rows"]
                if not csv_path.exists():
                    if expected == 0:
                        print(f"  {table:24s} {'0':>8s} rows  (no csv, none expected)")
                        continue
                    conn.rollback()
                    sys.exit(f"{csv_path} missing but manifest expects {expected} rows")

                with csv_path.open(encoding="utf-8", newline="") as fh:
                    cur.copy_expert(f'COPY "{table}" FROM STDIN WITH CSV HEADER', fh)

                cur.execute(f'SELECT count(*) FROM "{table}"')
                loaded = cur.fetchone()[0]
                total += loaded
                flag = "" if loaded == expected else "  <-- MISMATCH vs manifest"
                print(f"  {table:24s} {loaded:>8,} rows  (manifest: {expected:,}){flag}")

        conn.commit()
        print(f"\n{total:,} rows restored across {len(TABLE_ORDER)} tables")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
