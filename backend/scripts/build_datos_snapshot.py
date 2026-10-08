"""Numbers behind "Datos de los datos", the frontend's study section.

Every figure a published study quotes comes from this script, run against
the live database, so a reader can re-run it and get the same table. The
output is a dated snapshot (frontend/content/datos/snapshot.json): the
studies describe the corpus on that day, not whatever it holds later.

    cd backend
    python scripts/build_datos_snapshot.py

What it computes, per country:
  - benford: first-digit counts of the original amount and the mean
    absolute deviation from Benford's law, classified with Nigrini's
    first-digit thresholds (0.006 / 0.012 / 0.015).
  - round: share of amounts >= 1,000 written with at most two significant
    digits (150.000.000, 2.500). Counted in significant digits rather than
    "ends in 000" so a guaraní and a dólar are judged on the same scale.
  - concentration: share of the country's total amount taken by its top 1%
    and top 10% contracts, in the country's main currency only (amounts in
    different currencies can't be summed without a rate we don't have).
  - direction: open anomalies split into overcost / undercost, with the
    median amount of each group against the country's median.
  - weekday: contracts by day of the week of award_date (1 = Monday) and the
    busiest weekend dates, to tell steady weekend activity from one batch day.
  - calendar: contracts by year and month of award_date, for Paraguay (the
    only country with several full years) and Uruguay (to show it cannot be read).
  - signals: for the contracts that carry a prediction from Daniel Duque's
    BERT + XGBoost model, how often its flag and the statistical layer's
    flag agree.
"""

import json
import math
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "content" / "datos" / "snapshot.json"
BENFORD = [math.log10(1 + 1 / d) for d in range(1, 10)]


def nigrini(mad: float) -> str:
    if mad < 0.006:
        return "close"
    if mad < 0.012:
        return "acceptable"
    if mad < 0.015:
        return "marginal"
    return "nonconformity"


def first_digit(x: float) -> int:
    return int(f"{x:e}"[0])


def significant_digits(x: float) -> int:
    digits = f"{round(x):d}".rstrip("0")
    return len(digits)


def threshold_histogram(country: str, currency: str, low: int, high: int, step: int) -> dict:
    """Contract counts in equal bins from `low` up to and including `high`,
    plus the procurement methods inside the fullest bin."""
    with engine.connect() as conn:
        amounts = [
            a
            for (a,) in conn.execute(
                text(
                    "select amount_original from contracts where country_code = :c and currency = :cur "
                    "and amount_original >= :lo and amount_original <= :hi"
                ),
                {"c": country, "cur": currency, "lo": low, "hi": high},
            )
        ]
        bins = Counter(int((a - low) // step) for a in amounts)
        n_bins = (high - low) // step + 1
        counts = [bins.get(i, 0) for i in range(n_bins)]
        peak = max(range(n_bins), key=lambda i: counts[i])
        peak_lo = low + peak * step
        methods = conn.execute(
            text(
                "select coalesce(procurement_method, '(sin dato)'), count(*) from contracts "
                "where country_code = :c and currency = :cur and amount_original >= :lo and amount_original < :hi "
                "group by 1 order by 2 desc limit 4"
            ),
            {"c": country, "cur": currency, "lo": peak_lo, "hi": peak_lo + step},
        ).all()
        exact = conn.execute(
            text(
                "select amount_original, count(*) from contracts where country_code = :c and currency = :cur "
                "group by 1 order by 2 desc limit 3"
            ),
            {"c": country, "cur": currency},
        ).all()
        above = conn.execute(
            text("select count(*) from contracts where country_code = :c and currency = :cur and amount_original > :hi"),
            {"c": country, "cur": currency, "hi": high},
        ).scalar()
    return {
        "currency": currency,
        "low": low,
        "step": step,
        "counts": counts,
        "peak_bin": peak_lo,
        "peak_methods": [[m, n] for m, n in methods],
        "most_repeated": [[a, n] for a, n in exact],
        "above_high": above,
    }


def weekday_stats() -> dict:
    with engine.connect() as conn:
        days = conn.execute(
            text(
                "select country_code, extract(isodow from award_date)::int, count(*) from contracts "
                "where award_date is not null group by 1, 2"
            )
        ).all()
        methods = conn.execute(
            text(
                "select country_code, coalesce(procurement_method, '(sin dato)'), count(*) from contracts "
                "where extract(isodow from award_date) in (6, 7) group by 1, 2 order by 3 desc"
            )
        ).all()
        weekend = conn.execute(
            text(
                "select country_code, award_date, extract(isodow from award_date)::int, count(*) from contracts "
                "where extract(isodow from award_date) in (6, 7) group by 1, 2, 3 order by 4 desc"
            )
        ).all()
    out: dict = {}
    for country, day, n in days:
        out.setdefault(country, {"days": [0] * 7, "top_weekend_dates": []})["days"][day - 1] = n
    for country, day_date, dow, n in weekend:
        top = out[country]["top_weekend_dates"]
        if len(top) < 3:
            top.append([day_date.isoformat(), dow, n])
    for country, method, n in methods:
        out[country].setdefault("weekend_methods", [])
        if len(out[country]["weekend_methods"]) < 3:
            out[country]["weekend_methods"].append([method, n])
    return dict(sorted(out.items()))


def calendar_stats(country: str) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select extract(year from award_date)::int, extract(month from award_date)::int, count(*) "
                "from contracts where country_code = :c and award_date is not null group by 1, 2"
            ),
            {"c": country},
        ).all()
    years: dict[str, list[int]] = {}
    for year, month, n in rows:
        years.setdefault(str(year), [0] * 12)[month - 1] = n
    return {"years": dict(sorted(years.items()))}


def main() -> None:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select country_code, currency, amount_original from contracts "
                "where amount_original is not null and amount_original > 0"
            )
        ).all()
        directions = conn.execute(
            text(
                "select c.country_code, a.anomaly_type, c.amount_original, c.currency "
                "from anomalies a join contracts c on c.id = a.contract_id "
                "where a.status = 'open' and a.anomaly_type in ('overcost', 'undercost')"
            )
        ).all()
        signals = conn.execute(
            text(
                """
                select c.country_code,
                       exists(select 1 from anomalies a where a.contract_id = c.id
                              and a.nlp_component is not null) as nlp,
                       exists(select 1 from statistical_flags f where f.contract_id = c.id
                              and f.flagged) as stat
                from contracts c
                where exists(select 1 from predictions p where p.contract_id = c.id)
                """
            )
        ).all()

    by_country: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for country, currency, amount in rows:
        by_country[country].append((currency, amount))

    countries = {}
    for country, items in sorted(by_country.items()):
        main_currency = Counter(c for c, _ in items).most_common(1)[0][0]
        amounts = [a for _, a in items]
        main_amounts = sorted((a for c, a in items if c == main_currency), reverse=True)

        # Benford needs amounts spanning several orders of magnitude; below 10
        # units the leading digit is mostly the price list, not the law.
        benford_amounts = [a for a in amounts if a >= 10]
        digits = Counter(first_digit(a) for a in benford_amounts)
        n_b = len(benford_amounts)
        observed = [digits.get(d, 0) / n_b if n_b else 0 for d in range(1, 10)]
        mad = sum(abs(o - e) for o, e in zip(observed, BENFORD)) / 9

        big = [a for a in amounts if a >= 1000]
        round_count = sum(1 for a in big if significant_digits(a) <= 2)

        total = sum(main_amounts)
        top1 = main_amounts[: max(1, len(main_amounts) // 100)]
        top10 = main_amounts[: max(1, len(main_amounts) // 10)]

        countries[country] = {
            "contracts": len(items),
            "main_currency": main_currency,
            "median_main": statistics.median(main_amounts),
            "benford": {
                "n": n_b,
                "observed": [round(o, 4) for o in observed],
                "mad": round(mad, 4),
                "class": nigrini(mad),
            },
            "round": {"n": len(big), "round": round_count, "share": round(round_count / len(big), 4) if big else 0},
            "concentration": {
                "n": len(main_amounts),
                "largest_share": round(main_amounts[0] / total, 4) if total else 0,
                "top1_share": round(sum(top1) / total, 4) if total else 0,
                "top10_share": round(sum(top10) / total, 4) if total else 0,
            },
        }

    dir_groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for country, kind, amount, currency in directions:
        if amount and currency == countries[country]["main_currency"]:
            dir_groups[country][kind].append(amount)
    dir_counts = Counter((country, kind) for country, kind, _, _ in directions)
    for country, info in countries.items():
        info["direction"] = {
            kind: {
                "count": dir_counts.get((country, kind), 0),
                "median_main": statistics.median(dir_groups[country][kind]) if dir_groups[country][kind] else None,
            }
            for kind in ("overcost", "undercost")
        }

    sig: dict[str, Counter] = defaultdict(Counter)
    for country, nlp, stat in signals:
        sig[country][("nlp" if nlp else "") + ("stat" if stat else "") or "none"] += 1
    signals_out = {
        country: {"both": c["nlpstat"], "nlp_only": c["nlp"], "stat_only": c["stat"], "neither": c["none"]}
        for country, c in sorted(sig.items())
    }

    snapshot = {
        "generated": date.today().isoformat(),
        "total_contracts": len(rows),
        "benford_expected": [round(e, 4) for e in BENFORD],
        "countries": countries,
        "signals": signals_out,
        "weekday": weekday_stats(),
        "calendar": {"PY": calendar_stats("PY"), "UY": calendar_stats("UY")},
        "thresholds": {
            # Guatemala's direct purchase (Art. 43 b LCE) tops out at Q90,000;
            # the Dominican Republic's "Compras por Debajo del Umbral" thins
            # out around RD$270,000. Same bins on both sides of each ceiling.
            "GT": threshold_histogram("GT", "GTQ", 40_000, 100_000, 1_000),
            "DO": threshold_histogram("DO", "DOP", 100_000, 400_000, 10_000),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(snapshot, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
