"""Exports the statistical reference model published on Hugging Face.

The live /analyze/compare endpoint judges an amount against the contracts
already ingested: same buyer if it has enough of them, else same category,
else the whole country (app/analysis.py:compare_amount). This script freezes
those reference groups -- median, MAD and quartiles of log(amount) -- into
one JSON file, so huggingface/analyzer.py can give the same verdict with no
database, no API and no internet connection.

    cd backend
    python scripts/export_reference_model.py

Only aggregates leave the database: per-group statistics and the buyer's
public name. No contract rows, no amounts of individual contracts.
"""

import json
import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402
from app.stats import IQR_MULTIPLIER, MIN_GROUP_SIZE, ZSCORE_THRESHOLD, compute_group_stats  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "huggingface" / "model" / "reference.json"


def rounded(stats: dict) -> dict:
    return {k: (v if k == "n" else round(v, 5)) for k, v in stats.items()}


def main() -> None:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select c.country_code, c.currency, c.category_code, b.normalized_name, b.name, c.amount_original "
                "from contracts c left join buyers b on b.id = c.buyer_id "
                "where c.amount_original > 0 and c.currency is not null"
            )
        ).all()
        names = dict(conn.execute(text("select code, name from countries")).all())

    groups: dict[tuple, dict] = {}
    for country, currency, category, buyer_key, buyer_name, amount in rows:
        g = groups.setdefault((country, currency), {"all": [], "category": {}, "buyer": {}, "buyer_name": {}})
        value = math.log(amount)
        g["all"].append(value)
        if category:
            g["category"].setdefault(category, []).append(value)
        if buyer_key:
            g["buyer"].setdefault(buyer_key, []).append(value)
            g["buyer_name"][buyer_key] = buyer_name

    countries: dict[str, dict] = {}
    for (country, currency), g in sorted(groups.items()):
        if len(g["all"]) < MIN_GROUP_SIZE:
            continue
        entry = countries.setdefault(country, {"name": names.get(country, country), "currencies": {}})
        entry["currencies"][currency] = {
            "country": rounded(compute_group_stats(g["all"])),
            "category": {
                k: rounded(compute_group_stats(v)) for k, v in sorted(g["category"].items()) if len(v) >= MIN_GROUP_SIZE
            },
            "buyer": {
                k: {"name": g["buyer_name"][k], **rounded(compute_group_stats(v))}
                for k, v in sorted(g["buyer"].items())
                if len(v) >= MIN_GROUP_SIZE
            },
        }

    model = {
        "name": "contractor-ai-reference",
        "version": date.today().isoformat(),
        "space": "log(amount_original), same currency as the contract",
        "min_group_size": MIN_GROUP_SIZE,
        "zscore_threshold": ZSCORE_THRESHOLD,
        "iqr_multiplier": IQR_MULTIPLIER,
        "contracts": len(rows),
        "countries": countries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for code, entry in countries.items():
        for cur, ref in entry["currencies"].items():
            print(code, cur, ref["country"]["n"], "categories", len(ref["category"]), "buyers", len(ref["buyer"]))
    print(OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
