"""Provider favoritism & market concentration analysis.

Metrics:
- Herfindahl-Hirschman Index (HHI): Market concentration (0-10000)
- Provider concentration: Top N providers' share of total contracts/spending
- Repeat provider patterns: How often same supplier gets consecutive awards
- Price favoritism: Contracts to favored suppliers vs market baseline
- Geographic favoritism: Provider distribution across regions/departments
- Temporal patterns: Provider awards clustering over time
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select, and_, or_
from sqlalchemy.orm import Session

from . import models


@dataclass
class ProviderStats:
    """Overall provider market statistics"""
    total_providers: int
    total_contracts: int
    total_spending_usd: float
    hhi_concentration: float  # 0-10000 (perfect competition=0, monopoly=10000)
    top_10_share: float  # % of spending going to top 10


@dataclass
class ProviderDetail:
    """Individual provider record"""
    provider_name: str
    country_code: str
    total_contracts: int
    total_spending_usd: float
    market_share: float  # % of total contracts
    spending_share: float  # % of total spending
    avg_contract_value_usd: float
    anomaly_rate: float
    repeat_buyer_count: int  # How many buyers work with them


@dataclass
class PriceFavoritismPoint:
    """Price analysis for a provider over time"""
    provider_name: str
    year: int
    avg_contract_value_usd: float
    market_baseline_usd: float  # avg for all contracts that year
    markup_percent: float  # (avg_contract_value - baseline) / baseline * 100


@dataclass
class GeographicPattern:
    """Provider presence by country/region"""
    provider_name: str
    country_code: str
    contracts: int
    total_spending_usd: float
    market_share_in_country: float


@dataclass
class TemporalCluster:
    """Temporal clustering of provider awards"""
    provider_name: str
    award_date: date
    buyer_name: str
    contract_amount_usd: float
    consecutive_awards: int  # How many awards to same provider in same month


def calculate_hhi(db: Session, country_code: str | None = None) -> float:
    """Herfindahl-Hirschman Index: 0 (perfect competition) to 10000 (monopoly).

    Formula: sum((market_share_i)^2) * 10000
    where market_share_i is each provider's share of total spending.
    """
    contract_filter = []
    if country_code:
        contract_filter.append(models.Contract.country_code == country_code)

    # Get total spending
    total_spending = db.execute(
        select(func.coalesce(func.sum(models.Contract.amount_usd), 0.0))
        .select_from(models.Contract)
        .where(*contract_filter, models.Contract.amount_usd.isnot(None))
    ).scalar_one()

    if total_spending == 0:
        return 0.0

    # For now, use buyer as proxy for provider (actual supplier in OCDS JSON not extracted yet)
    # TODO: Extract supplier/provider from raw_ocds_json once that's implemented
    provider_spending = db.execute(
        select(
            models.Contract.buyer_id,
            func.sum(models.Contract.amount_usd).label("spending")
        )
        .select_from(models.Contract)
        .where(*contract_filter, models.Contract.buyer_id.isnot(None), models.Contract.amount_usd.isnot(None))
        .group_by(models.Contract.buyer_id)
    ).all()

    hhi = sum(
        ((row.spending / total_spending) ** 2) * 10000
        for row in provider_spending
    )
    return float(hhi)


def get_provider_stats(db: Session, country_code: str | None = None) -> ProviderStats:
    """Get overall provider market concentration statistics."""
    contract_filter = []
    if country_code:
        contract_filter.append(models.Contract.country_code == country_code)

    # Total unique providers (buyers as proxy)
    total_providers = db.execute(
        select(func.count(func.distinct(models.Contract.buyer_id)))
        .select_from(models.Contract)
        .where(*contract_filter, models.Contract.buyer_id.isnot(None))
    ).scalar_one()

    # Total contracts
    total_contracts = db.execute(
        select(func.count())
        .select_from(models.Contract)
        .where(*contract_filter)
    ).scalar_one()

    # Total spending
    total_spending_usd = db.execute(
        select(func.coalesce(func.sum(models.Contract.amount_usd), 0.0))
        .select_from(models.Contract)
        .where(*contract_filter, models.Contract.amount_usd.isnot(None))
    ).scalar_one()

    # HHI concentration index
    hhi = calculate_hhi(db, country_code)

    # Top 10 share of spending
    top_10_stmt = (
        select(
            models.Contract.buyer_id,
            func.sum(models.Contract.amount_usd).label("spending")
        )
        .select_from(models.Contract)
        .where(*contract_filter, models.Contract.buyer_id.isnot(None), models.Contract.amount_usd.isnot(None))
        .group_by(models.Contract.buyer_id)
        .order_by(func.sum(models.Contract.amount_usd).desc())
        .limit(10)
    )
    top_10_spending = sum(row.spending or 0 for row in db.execute(top_10_stmt).all())
    top_10_share = (top_10_spending / total_spending_usd * 100) if total_spending_usd > 0 else 0.0

    return ProviderStats(
        total_providers=total_providers,
        total_contracts=total_contracts,
        total_spending_usd=total_spending_usd,
        hhi_concentration=hhi,
        top_10_share=top_10_share,
    )


def get_top_providers(
    db: Session,
    country_code: str | None = None,
    limit: int = 20,
    min_contracts: int = 2,
) -> list[ProviderDetail]:
    """Get top providers by spending (as proxy, using buyers)."""
    contract_filter = []
    if country_code:
        contract_filter.append(models.Contract.country_code == country_code)

    # Get provider totals
    provider_stmt = (
        select(
            models.Contract.buyer_id,
            func.count().label("contracts"),
            func.coalesce(func.sum(models.Contract.amount_usd), 0.0).label("spending"),
        )
        .select_from(models.Contract)
        .where(*contract_filter, models.Contract.buyer_id.isnot(None))
        .group_by(models.Contract.buyer_id)
        .having(func.count() >= min_contracts)
        .order_by(func.sum(models.Contract.amount_usd).desc().nullslast())
        .limit(limit)
    )
    provider_rows = db.execute(provider_stmt).all()
    buyer_ids = [row.buyer_id for row in provider_rows]

    if not buyer_ids:
        return []

    # Get buyer names
    buyers = {b.id: b for b in db.execute(select(models.Buyer).where(models.Buyer.id.in_(buyer_ids))).scalars().all()}

    # Get anomaly counts
    anomaly_stmt = (
        select(models.Contract.buyer_id, func.count(func.distinct(models.Anomaly.contract_id)))
        .select_from(models.Anomaly)
        .join(models.Contract)
        .where(models.Anomaly.status == "open", models.Contract.buyer_id.in_(buyer_ids))
        .group_by(models.Contract.buyer_id)
    )
    anomalies_by_buyer = dict(db.execute(anomaly_stmt).all())

    # Get total spending and contracts (for market share calculation)
    total_contracts = db.execute(
        select(func.count())
        .select_from(models.Contract)
        .where(*contract_filter, models.Contract.buyer_id.isnot(None))
    ).scalar_one()

    total_spending_usd = db.execute(
        select(func.coalesce(func.sum(models.Contract.amount_usd), 0.0))
        .select_from(models.Contract)
        .where(*contract_filter, models.Contract.buyer_id.isnot(None), models.Contract.amount_usd.isnot(None))
    ).scalar_one()

    # Get distinct buyer count for each provider (repeat customer indicator)
    buyer_count_stmt = (
        select(
            models.Contract.buyer_id,
            func.count(func.distinct(models.Contract.buyer_id)).label("unique_buyers")
        )
        .select_from(models.Contract)
        .where(models.Contract.buyer_id.in_(buyer_ids))
        .group_by(models.Contract.buyer_id)
    )
    buyers_per_provider = dict(db.execute(buyer_count_stmt).all())

    results = []
    for row in provider_rows:
        buyer = buyers.get(row.buyer_id)
        if not buyer:
            continue

        anomalies = anomalies_by_buyer.get(row.buyer_id, 0)
        anomaly_rate = (anomalies / row.contracts) if row.contracts else 0.0

        results.append(
            ProviderDetail(
                provider_name=buyer.name,
                country_code=buyer.country_code,
                total_contracts=row.contracts,
                total_spending_usd=row.spending,
                market_share=(row.contracts / total_contracts * 100) if total_contracts else 0.0,
                spending_share=(row.spending / total_spending_usd * 100) if total_spending_usd else 0.0,
                avg_contract_value_usd=(row.spending / row.contracts) if row.contracts else 0.0,
                anomaly_rate=anomaly_rate,
                repeat_buyer_count=buyers_per_provider.get(row.buyer_id, 1),
            )
        )

    return results


def get_price_favoritism_trends(
    db: Session,
    country_code: str | None = None,
    start_year: int = 2023,
    end_year: int = 2025,
) -> list[PriceFavoritismPoint]:
    """Identify price favoritism: do certain providers get higher-than-market prices?"""
    contract_filter = [
        models.Contract.amount_usd.isnot(None),
        models.Contract.award_date.isnot(None),
    ]
    if country_code:
        contract_filter.append(models.Contract.country_code == country_code)

    year_expr = func.extract("year", models.Contract.award_date)

    # Get yearly baseline prices (median contract value per year)
    baseline_stmt = (
        select(
            year_expr.label("year"),
            func.avg(models.Contract.amount_usd).label("baseline"),
        )
        .select_from(models.Contract)
        .where(*contract_filter)
        .group_by(year_expr)
    )
    baseline_by_year = {int(row.year): row.baseline for row in db.execute(baseline_stmt).all()}

    # Get provider pricing by year
    provider_stmt = (
        select(
            models.Contract.buyer_id,
            year_expr.label("year"),
            func.avg(models.Contract.amount_usd).label("avg_price"),
            func.count().label("contracts"),
        )
        .select_from(models.Contract)
        .where(*contract_filter)
        .group_by(models.Contract.buyer_id, year_expr)
        .order_by(models.Contract.buyer_id, year_expr)
    )

    # Get buyer names
    buyer_ids = db.execute(
        select(func.distinct(models.Contract.buyer_id))
        .select_from(models.Contract)
        .where(*contract_filter, models.Contract.buyer_id.isnot(None))
    ).scalars().all()
    buyers = {b.id: b for b in db.execute(select(models.Buyer).where(models.Buyer.id.in_(buyer_ids))).scalars().all()}

    results = []
    for row in db.execute(provider_stmt).all():
        year = int(row.year)
        if year < start_year or year > end_year:
            continue

        buyer = buyers.get(row.buyer_id)
        if not buyer or row.contracts < 2:  # Skip low-sample providers
            continue

        baseline = baseline_by_year.get(year, 0)
        markup = ((row.avg_price - baseline) / baseline * 100) if baseline > 0 else 0.0

        results.append(
            PriceFavoritismPoint(
                provider_name=buyer.name,
                year=year,
                avg_contract_value_usd=row.avg_price,
                market_baseline_usd=baseline,
                markup_percent=markup,
            )
        )

    return results


def get_geographic_favoritism(
    db: Session,
    limit_per_country: int = 5,
) -> list[GeographicPattern]:
    """Identify geographic favoritism: which providers dominate which countries?"""
    provider_by_country = (
        select(
            models.Contract.buyer_id,
            models.Contract.country_code,
            func.count().label("contracts"),
            func.coalesce(func.sum(models.Contract.amount_usd), 0.0).label("spending"),
        )
        .select_from(models.Contract)
        .where(models.Contract.buyer_id.isnot(None), models.Contract.amount_usd.isnot(None))
        .group_by(models.Contract.buyer_id, models.Contract.country_code)
        .order_by(models.Contract.country_code, func.sum(models.Contract.amount_usd).desc())
    )

    # Get country totals for market share
    country_totals = {}
    country_stmt = (
        select(
            models.Contract.country_code,
            func.coalesce(func.sum(models.Contract.amount_usd), 0.0).label("spending"),
        )
        .select_from(models.Contract)
        .where(models.Contract.amount_usd.isnot(None))
        .group_by(models.Contract.country_code)
    )
    for row in db.execute(country_stmt).all():
        country_totals[row.country_code] = row.spending

    # Get buyer names
    all_buyer_ids = db.execute(
        select(func.distinct(models.Contract.buyer_id))
        .select_from(models.Contract)
        .where(models.Contract.buyer_id.isnot(None))
    ).scalars().all()
    buyers = {b.id: b for b in db.execute(select(models.Buyer).where(models.Buyer.id.in_(all_buyer_ids))).scalars().all()}

    results = []
    per_country_count = {}
    for row in db.execute(provider_by_country).all():
        country = row.country_code
        if per_country_count.get(country, 0) >= limit_per_country:
            continue

        buyer = buyers.get(row.buyer_id)
        if not buyer:
            continue

        country_total = country_totals.get(country, 0)
        market_share = (row.spending / country_total * 100) if country_total > 0 else 0.0

        results.append(
            GeographicPattern(
                provider_name=buyer.name,
                country_code=country,
                contracts=row.contracts,
                total_spending_usd=row.spending,
                market_share_in_country=market_share,
            )
        )

        per_country_count[country] = per_country_count.get(country, 0) + 1

    return results


def get_temporal_patterns(
    db: Session,
    country_code: str | None = None,
    limit: int = 100,
) -> list[TemporalCluster]:
    """Identify temporal clustering: same provider getting multiple awards in close succession?"""
    contract_filter = [models.Contract.award_date.isnot(None)]
    if country_code:
        contract_filter.append(models.Contract.country_code == country_code)

    # Get all contracts ordered by provider and date
    contracts = db.execute(
        select(
            models.Contract.buyer_id,
            models.Contract.award_date,
            models.Contract.buyer,
            models.Contract.amount_usd,
        )
        .select_from(models.Contract)
        .options(__import__('sqlalchemy.orm', fromlist=['joinedload']).joinedload(models.Contract.buyer))
        .where(*contract_filter)
        .order_by(models.Contract.buyer_id, models.Contract.award_date)
    ).all()

    results = []
    month_groups = {}

    for contract in contracts:
        if not contract.award_date or not contract.buyer:
            continue

        # Group by buyer and month
        month_key = (contract.buyer_id, contract.award_date.year, contract.award_date.month)
        if month_key not in month_groups:
            month_groups[month_key] = []
        month_groups[month_key].append(contract)

    # Find clusters (same provider with 3+ awards in same month)
    for month_key, contracts_in_month in month_groups.items():
        if len(contracts_in_month) >= 3:
            for contract in contracts_in_month:
                results.append(
                    TemporalCluster(
                        provider_name=contract.buyer.name,
                        award_date=contract.award_date,
                        buyer_name="Multiple",  # Would need to extract from OCDS JSON
                        contract_amount_usd=contract.amount_usd or 0.0,
                        consecutive_awards=len(contracts_in_month),
                    )
                )

    return results[:limit]
