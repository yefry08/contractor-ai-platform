"""Contractor AI, offline: is this contract's amount unusual?

Standard library only. Gives the same verdict as the platform's
"Analizar contratos" page (backend/app/analysis.py:compare_amount), using
the reference groups frozen in reference.json instead of the database.

    python analyzer.py --country GT --amount 89500
    python analyzer.py --country PY --currency PYG --amount 950000000 --buyer "municipalidad de asuncion"
    python analyzer.py --list GT            # categories and buyers available

As a library:

    from analyzer import Analyzer
    Analyzer().compare("CL", 12_500_000, category="Servicios de construcción")

A verdict is a signal to look closer, never a finding of wrongdoing.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent


@dataclass
class Comparison:
    country: str
    currency: str
    reference_group: str
    group_size: int
    median_amount: float
    typical_low: float
    typical_high: float
    submitted_amount: float
    deviation_pct: float
    zscore: float
    zscore_flagged: bool
    iqr_flagged: bool
    verdict: str  # normal | revisar | alta


class Analyzer:
    def __init__(self, reference: str | Path | dict | None = None):
        if isinstance(reference, dict):
            self.model = reference
        else:
            path = Path(reference) if reference else HERE / "reference.json"
            self.model = json.loads(path.read_text(encoding="utf-8"))
        self.countries = self.model["countries"]

    def currencies(self, country: str) -> list[str]:
        refs = self.countries[country]["currencies"]
        return sorted(refs, key=lambda c: -refs[c]["country"]["n"])

    def categories(self, country: str, currency: str | None = None) -> list[str]:
        return sorted(self._ref(country, currency)["category"])

    def buyers(self, country: str, currency: str | None = None) -> list[str]:
        return sorted(b["name"] for b in self._ref(country, currency)["buyer"].values())

    def _ref(self, country: str, currency: str | None) -> dict:
        if country not in self.countries:
            raise ValueError(f"Unknown country {country!r}; available: {', '.join(sorted(self.countries))}")
        currency = currency or self.currencies(country)[0]
        refs = self.countries[country]["currencies"]
        if currency not in refs:
            raise ValueError(f"No reference for {country} in {currency}; available: {', '.join(refs)}")
        return refs[currency]

    def compare(
        self,
        country: str,
        amount: float,
        currency: str | None = None,
        category: str | None = None,
        buyer: str | None = None,
    ) -> Comparison:
        if amount <= 0:
            raise ValueError("amount must be greater than 0")
        country = country.upper()
        currency = (currency or self.currencies(country)[0]).upper()
        ref = self._ref(country, currency)

        # Narrowest group with enough history: buyer, then category, then country.
        # A buyer matches by the platform's normalized key or by its published name.
        key = (buyer or "").strip().lower()
        by_name = {b["name"].strip().lower(): b for b in ref["buyer"].values()}
        buyer_stats = ref["buyer"].get(key) or by_name.get(key)
        if key and buyer_stats:
            stats, group = buyer_stats, f"{country}:comprador"
        elif category and category in ref["category"]:
            stats, group = ref["category"][category], f"{country}:categoría"
        else:
            stats, group = ref["country"], f"{country}:country"

        log_amount = math.log(amount)
        mad = stats["mad"]
        z = 0.0 if mad == 0 else 0.6745 * (log_amount - stats["median"]) / mad
        z = max(-50.0, min(50.0, z))
        zscore_flagged = abs(z) > self.model["zscore_threshold"]

        iqr = stats["iqr"]
        k = self.model["iqr_multiplier"]
        iqr_flagged = bool(iqr > 0 and not (stats["q1"] - k * iqr <= log_amount <= stats["q3"] + k * iqr))

        median_amount = math.exp(stats["median"])
        if zscore_flagged and abs(z) > 5:
            verdict = "alta"
        elif zscore_flagged or iqr_flagged:
            verdict = "revisar"
        else:
            verdict = "normal"

        return Comparison(
            country=country,
            currency=currency,
            reference_group=group,
            group_size=stats["n"],
            median_amount=median_amount,
            typical_low=math.exp(stats["q1"]),
            typical_high=math.exp(stats["q3"]),
            submitted_amount=amount,
            deviation_pct=(amount - median_amount) / median_amount * 100,
            zscore=z,
            zscore_flagged=zscore_flagged,
            iqr_flagged=iqr_flagged,
            verdict=verdict,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare a public contract amount against similar contracts.")
    parser.add_argument("--country", help="ISO code: PY CO CR DO PE SV BR UY CL GT")
    parser.add_argument("--amount", type=float)
    parser.add_argument("--currency", help="defaults to the country's main currency")
    parser.add_argument("--category")
    parser.add_argument("--buyer", help="buyer's name as published")
    parser.add_argument("--list", metavar="COUNTRY", help="print the categories and buyers for a country")
    parser.add_argument("--reference", help="path to reference.json")
    args = parser.parse_args()

    analyzer = Analyzer(args.reference)
    if args.list:
        code = args.list.upper()
        for cur in analyzer.currencies(code):
            print(f"[{code} · {cur}]")
            print("  categories:", "; ".join(analyzer.categories(code, cur)) or "—")
            print("  buyers:", "; ".join(analyzer.buyers(code, cur)) or "—")
        return
    if not args.country or not args.amount:
        parser.error("--country and --amount are required (or use --list COUNTRY)")
    result = analyzer.compare(args.country, args.amount, args.currency, args.category, args.buyer)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
