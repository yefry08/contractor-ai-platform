"""Open calls to sell to the state, with the context a supplier needs to
decide whether to bid: how much this institution usually pays, and how often
its contracts get flagged.

The calls themselves come from scripts/ingest_opportunities.py. Here they are
only filtered, paged and enriched with what Contractor AI already knows
about the buyer -- matched by name within the same country, because the
portals that publish open calls don't share an institution id with the ones
that publish awarded contracts.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import models
from .stats import MIN_GROUP_SIZE

SOURCES = {
    "CO": "SECOP II · datos.gov.co",
    "BR": "PNCP · Portal Nacional de Contratações Públicas",
    "DO": "DGCP · datos abiertos",
}


@dataclass
class BuyerHistory:
    contracts: int
    median_amount: float | None
    currency: str | None
    anomaly_rate: float | None


def normalize(name: str | None) -> str:
    return (name or "").strip().lower()


def search(
    db: Session,
    *,
    country: str | None = None,
    q: str | None = None,
    for_smes: bool | None = None,
    closing_within_days: int | None = None,
    min_amount: float | None = None,
    limit: int = 20,
    offset: int = 0,
):
    now = datetime.utcnow()
    stmt = select(models.Opportunity).where(models.Opportunity.deadline > now)
    if country:
        stmt = stmt.where(models.Opportunity.country_code == country)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(models.Opportunity.title).like(like),
                func.lower(models.Opportunity.description).like(like),
                func.lower(models.Opportunity.buyer_name).like(like),
            )
        )
    if for_smes:
        stmt = stmt.where(models.Opportunity.for_smes.is_(True))
    if closing_within_days:
        stmt = stmt.where(models.Opportunity.deadline <= now + timedelta(days=closing_within_days))
    if min_amount:
        stmt = stmt.where(models.Opportunity.estimated_amount >= min_amount)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = db.execute(stmt.order_by(models.Opportunity.deadline.asc()).limit(limit).offset(offset)).scalars().all()
    return total, items


def buyer_histories(db: Session, items) -> dict[tuple[str, str], BuyerHistory]:
    """What the corpus knows about each buyer on this page, keyed by
    (country, normalized name). Buyers with too few contracts get no median:
    a median of three contracts isn't a reference price."""
    wanted = {(o.country_code, normalize(o.buyer_name)) for o in items if o.buyer_name}
    if not wanted:
        return {}
    rows = db.execute(
        select(
            models.Buyer.country_code,
            models.Buyer.normalized_name,
            models.Contract.id,
            models.Contract.amount_original,
            models.Contract.currency,
        )
        .join(models.Contract, models.Contract.buyer_id == models.Buyer.id)
        .where(models.Buyer.normalized_name.in_({name for _, name in wanted}))
        .where(models.Buyer.country_code.in_({c for c, _ in wanted}))
    ).all()
    contracts = defaultdict(list)
    for country, name, contract_id, amount, currency in rows:
        if (country, name) in wanted:
            contracts[(country, name)].append((contract_id, amount, currency))

    ids = [cid for v in contracts.values() for cid, _, _ in v]
    flagged = set()
    if ids:
        flagged = set(
            db.execute(
                select(models.Anomaly.contract_id).where(
                    models.Anomaly.contract_id.in_(ids), models.Anomaly.status == "open"
                )
            ).scalars()
        )

    out = {}
    for key, rows_ in contracts.items():
        currencies = defaultdict(list)
        for _, amount, currency in rows_:
            if amount and amount > 0:
                currencies[currency].append(amount)
        currency, amounts = max(currencies.items(), key=lambda kv: len(kv[1]), default=(None, []))
        out[key] = BuyerHistory(
            contracts=len(rows_),
            median_amount=statistics.median(amounts) if len(amounts) >= MIN_GROUP_SIZE else None,
            currency=currency,
            # Same minimum as the median: with one or two contracts, "100% flagged"
            # would brand an institution on a single data point.
            anomaly_rate=(sum(1 for cid, _, _ in rows_ if cid in flagged) / len(rows_))
            if len(rows_) >= MIN_GROUP_SIZE
            else None,
        )
    return out


def counts_by_country(db: Session) -> dict[str, int]:
    now = datetime.utcnow()
    rows = db.execute(
        select(models.Opportunity.country_code, func.count())
        .where(models.Opportunity.deadline > now)
        .group_by(models.Opportunity.country_code)
    ).all()
    return {c: n for c, n in rows}
