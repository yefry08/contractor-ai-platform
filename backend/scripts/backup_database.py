"""Dump every table to CSV, plus a manifest of row counts.

Written for a host migration: Render's free PostgreSQL is deleted when it
expires, not merely stopped, so the ingested corpus has to leave the instance
before that happens. Uses server-side COPY through psycopg2 rather than pg_dump,
because the Postgres client binaries are not installed on every machine that
needs to run this -- and the moment you need a backup is a bad moment to be
installing tooling.

The output is plain CSV with headers, which restores into any Postgres (Neon,
Supabase, Aiven, a local instance) via \\copy, and stays readable even if no
Postgres is available at all.

    python backend/scripts/backup_database.py
    python backend/scripts/backup_database.py --out ./somewhere-else

DATABASE_URL is read from backend/.env (or the environment). Nothing is written
to the database: this is read-only.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def list_tables(cur) -> list[str]:
    cur.execute(
        """
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
        """
    )
    return [r[0] for r in cur.fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None, help="output directory (default: backups/<timestamp>)")
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out) if args.out else REPO_ROOT / "backups" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    url = load_database_url()
    # Never print the URL: it carries the password.
    print(f"connecting… (host hidden)\nwriting to {out_dir}")

    conn = psycopg2.connect(url)
    conn.set_session(readonly=True)
    manifest: dict[str, object] = {"taken_at": stamp, "tables": {}}
    total = 0

    try:
        with conn.cursor() as cur:
            tables = list_tables(cur)
            if not tables:
                print("no tables found in schema 'public' -- nothing to back up")
                return 1

            for table in tables:
                cur.execute(f'SELECT count(*) FROM "{table}"')
                rows = cur.fetchone()[0]

                target = out_dir / f"{table}.csv"
                buf = io.StringIO()
                # COPY runs server-side and streams, so a wide table (raw_ocds_json
                # in particular) does not have to be materialised in Python first.
                cur.copy_expert(f'COPY "{table}" TO STDOUT WITH CSV HEADER', buf)
                target.write_text(buf.getvalue(), encoding="utf-8", newline="")

                # Round-trip the header so a truncated or mis-quoted dump is caught
                # here rather than at restore time, when the source may be gone.
                with target.open(encoding="utf-8", newline="") as fh:
                    header = next(csv.reader(fh), [])

                manifest["tables"][table] = {
                    "rows": rows,
                    "columns": header,
                    "bytes": target.stat().st_size,
                }
                total += rows
                print(f"  {table:24s} {rows:>8,} rows  {target.stat().st_size/1024:>8.0f} KB")
    finally:
        conn.close()

    manifest["total_rows"] = total
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n{total:,} rows across {len(manifest['tables'])} tables -> {out_dir}")
    print("restore into any Postgres with, per table:")
    print('  \\copy "<table>" FROM \'<table>.csv\' WITH CSV HEADER')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
