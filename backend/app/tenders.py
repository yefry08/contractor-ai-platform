"""Support code for a bidder preparing to apply to a public tender: what did
similar contracts in this country/category actually pay historically (so a
bid can be priced competitively instead of guessed), and where to go submit
one for real.

Deliberately does NOT pretend to list live open tenders or to submit a bid
on anyone's behalf -- this environment has no scraper wired up and no
country's e-procurement API credentials, and even with those, "submit a bid
for a business" is a much bigger trust/legal surface than a civic
transparency tool should take on unilaterally. What this *can* do honestly,
using data already ingested: show the price benchmark, and point to the
real official portal where the actual open tenders and submission live.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .stats import MIN_GROUP_SIZE, compute_group_stats

# One entry per supported country -- the official e-procurement/tendering
# portal (not the open-data portal used for ingestion, which is a different
# destination: Country.ocds_portal_url). Verified to resolve with a 200
# before being hardcoded here, not guessed.
OFFICIAL_PORTALS: dict[str, dict[str, str]] = {
    "PY": {"name": "DNCP — Dirección Nacional de Contrataciones Públicas", "url": "https://www.contrataciones.gov.py/"},
    "CO": {"name": "Colombia Compra Eficiente (SECOP)", "url": "https://www.colombiacompra.gov.co/"},
    "CR": {"name": "SICOP — Sistema Integrado de Compras Públicas", "url": "https://www.sicop.go.cr/"},
    "DO": {"name": "DGCP — Dirección General de Contrataciones Públicas", "url": "https://www.dgcp.gob.do/"},
}


@dataclass
class TenderCategory:
    category_code: str
    contracts: int


@dataclass
class PriceBenchmark:
    country_code: str
    category_code: str
    currency: str | None
    sample_size: int
    median_amount: float
    typical_low: float
    typical_high: float


def get_categories(db: Session, country_code: str) -> list[TenderCategory]:
    """Categories with enough contracts to form an honest benchmark,
    largest first."""

    stmt = (
        select(models.Contract.category_code, func.count().label("n"))
        .where(
            models.Contract.country_code == country_code,
            models.Contract.category_code.isnot(None),
            models.Contract.amount_original.isnot(None),
            models.Contract.amount_original > 0,
        )
        .group_by(models.Contract.category_code)
        .having(func.count() >= MIN_GROUP_SIZE)
        .order_by(func.count().desc())
    )
    return [TenderCategory(category_code=r.category_code, contracts=r.n) for r in db.execute(stmt).all()]


def get_price_benchmark(db: Session, country_code: str, category_code: str) -> PriceBenchmark | None:
    """Median + a typical (IQR) range per currency actually used in this
    country/category, so a bidder sees "most contracts like this cost
    between X and Y" instead of a single number implying false precision.
    Picks the currency with the most contracts when a category has more
    than one (shouldn't normally happen within one country, but the schema
    allows it)."""

    base_stmt = select(models.Contract).where(
        models.Contract.country_code == country_code,
        models.Contract.category_code == category_code,
        models.Contract.amount_original.isnot(None),
        models.Contract.amount_original > 0,
    )
    rows = db.execute(base_stmt).unique().scalars().all()
    if len(rows) < MIN_GROUP_SIZE:
        return None

    currency_counts: dict[str | None, int] = {}
    for r in rows:
        currency_counts[r.currency] = currency_counts.get(r.currency, 0) + 1
    dominant_currency = max(currency_counts, key=lambda c: currency_counts[c])
    group = [r for r in rows if r.currency == dominant_currency]
    if len(group) < MIN_GROUP_SIZE:
        return None

    log_amounts = [math.log(r.amount_original) for r in group]
    stats = compute_group_stats(log_amounts)

    return PriceBenchmark(
        country_code=country_code,
        category_code=category_code,
        currency=dominant_currency,
        sample_size=len(group),
        median_amount=math.exp(stats["median"]),
        typical_low=math.exp(stats["q1"]),
        typical_high=math.exp(stats["q3"]),
    )
