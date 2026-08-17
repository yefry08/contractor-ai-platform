from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models

# Institutions with fewer contracts than this are excluded from the ranking --
# a buyer with 1-2 contracts and zero anomalies isn't "the best," it's just an
# unreliable sample size.
MIN_BUYER_CONTRACTS = 5


@dataclass
class YearPoint:
    year: int
    contracts: int
    total_amount_usd: float
    anomalies: int


@dataclass
class CategoryBreakdown:
    category_code: str
    contracts: int
    total_amount_usd: float
    anomalies: int


@dataclass
class CountryBreakdown:
    country_code: str
    contracts: int
    total_amount_usd: float
    anomalies: int
    anomaly_rate: float


@dataclass
class DashboardSummary:
    country_code: str | None
    total_contracts: int
    total_amount_usd: float
    total_anomalies: int
    anomaly_rate: float
    by_year: list[YearPoint]
    by_category: list[CategoryBreakdown]
    by_country: list[CountryBreakdown]


@dataclass
class BuyerRanking:
    buyer_id: str
    name: str
    country_code: str
    total_contracts: int
    total_amount_usd: float
    anomalies: int
    anomaly_rate: float


def _open_anomaly_contract_ids(db: Session, country_code: str | None):
    stmt = select(models.Anomaly.contract_id).join(models.Contract).where(models.Anomaly.status == "open")
    if country_code:
        stmt = stmt.where(models.Contract.country_code == country_code)
    return stmt


def get_summary(db: Session, country_code: str | None) -> DashboardSummary:
    contract_filter = []
    if country_code:
        contract_filter.append(models.Contract.country_code == country_code)

    total_contracts = db.execute(
        select(func.count()).select_from(models.Contract).where(*contract_filter)
    ).scalar_one()

    total_amount_usd = db.execute(
        select(func.coalesce(func.sum(models.Contract.amount_usd), 0.0))
        .select_from(models.Contract)
        .where(*contract_filter)
    ).scalar_one()

    total_anomalies = db.execute(
        select(func.count(func.distinct(models.Anomaly.contract_id))).select_from(
            _open_anomaly_contract_ids(db, country_code).subquery()
        )
    ).scalar_one()

    year_expr = func.extract("year", models.Contract.award_date)
    year_stmt = (
        select(
            year_expr.label("year"),
            func.count().label("contracts"),
            func.coalesce(func.sum(models.Contract.amount_usd), 0.0).label("total_amount_usd"),
        )
        .select_from(models.Contract)
        .where(*contract_filter, models.Contract.award_date.isnot(None))
        .group_by(year_expr)
        .order_by(year_expr)
    )
    year_rows = db.execute(year_stmt).all()

    anomaly_by_year_stmt = (
        select(year_expr.label("year"), func.count(func.distinct(models.Anomaly.contract_id)))
        .select_from(models.Anomaly)
        .join(models.Contract)
        .where(models.Anomaly.status == "open", models.Contract.award_date.isnot(None), *contract_filter)
        .group_by(year_expr)
    )
    anomalies_by_year = dict(db.execute(anomaly_by_year_stmt).all())

    by_year = [
        YearPoint(
            year=int(row.year),
            contracts=row.contracts,
            total_amount_usd=row.total_amount_usd,
            anomalies=int(anomalies_by_year.get(row.year, 0)),
        )
        for row in year_rows
    ]

    category_stmt = (
        select(
            models.Contract.category_code,
            func.count().label("contracts"),
            func.coalesce(func.sum(models.Contract.amount_usd), 0.0).label("total_amount_usd"),
        )
        .select_from(models.Contract)
        .where(*contract_filter, models.Contract.category_code.isnot(None))
        .group_by(models.Contract.category_code)
        .order_by(func.count().desc())
        .limit(8)
    )
    category_rows = db.execute(category_stmt).all()

    anomalies_by_category_stmt = (
        select(models.Contract.category_code, func.count(func.distinct(models.Anomaly.contract_id)))
        .select_from(models.Anomaly)
        .join(models.Contract)
        .where(models.Anomaly.status == "open", models.Contract.category_code.isnot(None), *contract_filter)
        .group_by(models.Contract.category_code)
    )
    anomalies_by_category = dict(db.execute(anomalies_by_category_stmt).all())

    by_category = [
        CategoryBreakdown(
            category_code=row.category_code,
            contracts=row.contracts,
            total_amount_usd=row.total_amount_usd,
            anomalies=int(anomalies_by_category.get(row.category_code, 0)),
        )
        for row in category_rows
    ]

    by_country: list[CountryBreakdown] = []
    if not country_code:
        country_stmt = (
            select(
                models.Contract.country_code,
                func.count().label("contracts"),
                func.coalesce(func.sum(models.Contract.amount_usd), 0.0).label("total_amount_usd"),
            )
            .select_from(models.Contract)
            .group_by(models.Contract.country_code)
        )
        country_rows = db.execute(country_stmt).all()

        anomalies_by_country_stmt = (
            select(models.Contract.country_code, func.count(func.distinct(models.Anomaly.contract_id)))
            .select_from(models.Anomaly)
            .join(models.Contract)
            .where(models.Anomaly.status == "open")
            .group_by(models.Contract.country_code)
        )
        anomalies_by_country = dict(db.execute(anomalies_by_country_stmt).all())

        by_country = [
            CountryBreakdown(
                country_code=row.country_code,
                contracts=row.contracts,
                total_amount_usd=row.total_amount_usd,
                anomalies=int(anomalies_by_country.get(row.country_code, 0)),
                anomaly_rate=(anomalies_by_country.get(row.country_code, 0) / row.contracts) if row.contracts else 0.0,
            )
            for row in country_rows
        ]

    return DashboardSummary(
        country_code=country_code,
        total_contracts=total_contracts,
        total_amount_usd=total_amount_usd,
        total_anomalies=total_anomalies,
        anomaly_rate=(total_anomalies / total_contracts) if total_contracts else 0.0,
        by_year=by_year,
        by_category=by_category,
        by_country=by_country,
    )


def get_best_buyers(db: Session, country_code: str | None, limit: int) -> list[BuyerRanking]:
    """Institutions with the strongest procurement track record: the lowest
    open-anomaly rate among buyers with enough contracts to be a meaningful
    sample, ranked best first."""

    contract_filter = [models.Contract.buyer_id.isnot(None)]
    if country_code:
        contract_filter.append(models.Contract.country_code == country_code)

    totals_stmt = (
        select(
            models.Contract.buyer_id,
            func.count().label("total_contracts"),
            func.coalesce(func.sum(models.Contract.amount_usd), 0.0).label("total_amount_usd"),
        )
        .select_from(models.Contract)
        .where(*contract_filter)
        .group_by(models.Contract.buyer_id)
        .having(func.count() >= MIN_BUYER_CONTRACTS)
    )
    totals = {row.buyer_id: row for row in db.execute(totals_stmt).all()}
    if not totals:
        return []

    anomaly_stmt = (
        select(models.Contract.buyer_id, func.count(func.distinct(models.Anomaly.contract_id)))
        .select_from(models.Anomaly)
        .join(models.Contract)
        .where(models.Anomaly.status == "open", models.Contract.buyer_id.in_(totals.keys()))
        .group_by(models.Contract.buyer_id)
    )
    anomalies_by_buyer = dict(db.execute(anomaly_stmt).all())

    buyer_rows = db.execute(
        select(models.Buyer).where(models.Buyer.id.in_(totals.keys()))
    ).scalars().all()
    buyers_by_id = {b.id: b for b in buyer_rows}

    rankings = []
    for buyer_id, row in totals.items():
        buyer = buyers_by_id.get(buyer_id)
        if buyer is None:
            continue
        anomalies = int(anomalies_by_buyer.get(buyer_id, 0))
        rankings.append(
            BuyerRanking(
                buyer_id=buyer_id,
                name=buyer.name,
                country_code=buyer.country_code,
                total_contracts=row.total_contracts,
                total_amount_usd=row.total_amount_usd,
                anomalies=anomalies,
                anomaly_rate=anomalies / row.total_contracts,
            )
        )

    rankings.sort(key=lambda r: (r.anomaly_rate, -r.total_contracts))
    return rankings[:limit]
