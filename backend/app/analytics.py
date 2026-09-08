"""Advanced predictive analytics & trend analysis.

Phase 3 features:
- Anomaly rate forecasting (time-series prediction)
- Category price trends with seasonal adjustment
- Buyer favoritism patterns & risk profiles
- Network analysis (supplier-buyer relationships)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models


@dataclass
class AnomalyRateTrend:
    """Anomaly rate over time."""
    year: int
    month: int | None
    anomaly_rate: float  # 0-1: % of contracts flagged
    total_contracts: int
    anomalous_contracts: int
    trend_direction: str  # "increasing", "stable", "decreasing"


@dataclass
class CategoryPriceTrend:
    """Price trend for a category over time."""
    category_code: str
    year: int
    median_price: float
    price_change_pct: float  # % change from previous year
    volatility: float  # std dev
    sample_size: int
    trend: str  # "up", "stable", "down"


@dataclass
class BuyerRiskProfile:
    """Detailed risk assessment for a buyer."""
    buyer_name: str
    total_contracts: int
    total_spending_usd: float
    anomaly_rate: float
    concentration_hhi: float  # Supplier concentration
    favorite_supplier_share: float  # Top supplier's % of contracts
    price_premium: float  # Average premium vs baseline (%)
    risk_score: float  # 0-1 composite
    risk_factors: list[str]
    recommendation: str


def get_anomaly_rate_trend(db: Session, country_code: str, granularity: str = "month") -> list[AnomalyRateTrend]:
    """Get anomaly rate over time (by month or year).

    Args:
        country_code: Country to analyze
        granularity: "month" or "year"

    Returns:
        List of AnomalyRateTrend with rates and directions
    """
    # Get all contracts with anomaly status
    stmt = select(
        models.Contract.award_date,
        func.count().label("total"),
        func.sum(
            func.cast(models.Contract.anomalies.any(), models.sqlalchemy.Integer)
        ).label("anomalous")
    ).where(
        models.Contract.country_code == country_code,
        models.Contract.award_date.isnot(None)
    ).group_by(models.Contract.award_date)

    results = db.execute(stmt).all()

    # Group by month or year
    trends_dict = defaultdict(lambda: {"total": 0, "anomalous": 0})

    for award_date, total, anomalous in results:
        if not award_date:
            continue

        if granularity == "month":
            key = (award_date.year, award_date.month)
        else:
            key = (award_date.year, None)

        trends_dict[key]["total"] += total
        trends_dict[key]["anomalous"] += (anomalous or 0)

    # Convert to trends with direction
    trends = []
    sorted_keys = sorted(trends_dict.keys())

    for i, key in enumerate(sorted_keys):
        year, month = key
        data = trends_dict[key]
        total = data["total"]
        anomalous = data["anomalous"]
        rate = anomalous / total if total > 0 else 0.0

        # Determine trend direction
        if i == 0:
            trend_direction = "stable"
        else:
            prev_key = sorted_keys[i - 1]
            prev_rate = trends_dict[prev_key]["anomalous"] / trends_dict[prev_key]["total"]
            if rate > prev_rate * 1.1:
                trend_direction = "increasing"
            elif rate < prev_rate * 0.9:
                trend_direction = "decreasing"
            else:
                trend_direction = "stable"

        trends.append(
            AnomalyRateTrend(
                year=year,
                month=month,
                anomaly_rate=rate,
                total_contracts=total,
                anomalous_contracts=anomalous,
                trend_direction=trend_direction
            )
        )

    return trends


def get_category_price_trends(db: Session, country_code: str, category_code: str) -> list[CategoryPriceTrend]:
    """Get price trends for a category over time.

    Returns yearly median prices and volatility.
    """
    import statistics

    stmt = select(models.Contract).where(
        models.Contract.country_code == country_code,
        models.Contract.category_code == category_code,
        models.Contract.award_date.isnot(None),
        models.Contract.amount_original.isnot(None),
        models.Contract.amount_original > 0
    ).order_by(models.Contract.award_date)

    contracts = db.execute(stmt).scalars().all()

    # Group by year
    yearly_data = defaultdict(list)
    for contract in contracts:
        year = contract.award_date.year
        yearly_data[year].append(contract.amount_original)

    # Calculate trends
    trends = []
    sorted_years = sorted(yearly_data.keys())

    for i, year in enumerate(sorted_years):
        amounts = yearly_data[year]
        if not amounts:
            continue

        median_price = statistics.median(amounts)
        volatility = statistics.stdev(amounts) if len(amounts) > 1 else 0.0

        # Calculate year-over-year change
        if i == 0:
            price_change_pct = 0.0
        else:
            prev_year = sorted_years[i - 1]
            prev_median = statistics.median(yearly_data[prev_year])
            price_change_pct = ((median_price - prev_median) / prev_median * 100) if prev_median > 0 else 0.0

        # Determine trend
        if price_change_pct > 5:
            trend = "up"
        elif price_change_pct < -5:
            trend = "down"
        else:
            trend = "stable"

        trends.append(
            CategoryPriceTrend(
                category_code=category_code,
                year=year,
                median_price=median_price,
                price_change_pct=price_change_pct,
                volatility=volatility,
                sample_size=len(amounts),
                trend=trend
            )
        )

    return trends


def get_buyer_risk_profile(db: Session, buyer_id: str) -> BuyerRiskProfile | None:
    """Generate comprehensive risk profile for a buyer.

    Analyzes: contract volume, spending patterns, anomaly rate, supplier concentration.
    """
    buyer = db.get(models.Buyer, buyer_id)
    if not buyer:
        return None

    contracts = db.execute(
        select(models.Contract).where(models.Contract.buyer_id == buyer_id)
    ).scalars().all()

    if not contracts:
        return None

    # Basic metrics
    total_contracts = len(contracts)
    total_spending = sum(c.amount_usd or 0.0 for c in contracts if c.amount_usd)

    # Anomaly rate
    anomalous_count = sum(1 for c in contracts if c.anomalies)
    anomaly_rate = anomalous_count / total_contracts if total_contracts > 0 else 0.0

    # Supplier concentration (top supplier)
    supplier_contracts = defaultdict(int)
    for contract in contracts:
        supplier_id = contract.external_id or "unknown"
        supplier_contracts[supplier_id] += 1

    top_supplier_count = max(supplier_contracts.values()) if supplier_contracts else 0
    favorite_supplier_share = top_supplier_count / total_contracts if total_contracts > 0 else 0.0

    # HHI (supplier concentration)
    hhi = sum((count / total_contracts) ** 2 for count in supplier_contracts.values()) * 10000

    # Price premium analysis
    category_contracts = db.execute(
        select(models.Contract).where(
            models.Contract.category_code == contracts[0].category_code,
            models.Contract.country_code == contracts[0].country_code,
            models.Contract.amount_usd.isnot(None),
            models.Contract.amount_usd > 0
        )
    ).scalars().all()

    buyer_amounts = [c.amount_usd for c in contracts if c.amount_usd and c.amount_usd > 0]
    category_amounts = [c.amount_usd for c in category_contracts if c.amount_usd and c.amount_usd > 0]

    if buyer_amounts and category_amounts:
        buyer_avg = sum(buyer_amounts) / len(buyer_amounts)
        category_avg = sum(category_amounts) / len(category_amounts)
        price_premium = ((buyer_avg - category_avg) / category_avg * 100) if category_avg > 0 else 0.0
    else:
        price_premium = 0.0

    # Composite risk score (0-1)
    risk_factors = []
    risk_score = 0.0

    if anomaly_rate > 0.3:
        risk_factors.append(f"Alta tasa de anomalías ({anomaly_rate:.1%})")
        risk_score += 0.3

    if hhi > 5000:
        risk_factors.append(f"Alta concentración de proveedores (HHI: {hhi:.0f})")
        risk_score += 0.3

    if price_premium > 20:
        risk_factors.append(f"Precios {price_premium:.0f}% sobre el promedio de categoría")
        risk_score += 0.25

    if favorite_supplier_share > 0.5:
        risk_factors.append(f"Un proveedor domina {favorite_supplier_share:.0%} de contratos")
        risk_score += 0.15

    # Risk recommendation
    if risk_score >= 0.7:
        recommendation = "Requerida revisión detallada - Riesgo crítico identificado"
    elif risk_score >= 0.5:
        recommendation = "Se recomienda auditoría selectiva de patrones sospechosos"
    elif risk_score >= 0.3:
        recommendation = "Monitoreo continuo recomendado"
    else:
        recommendation = "Perfil bajo riesgo - Monitoreo estándar"

    return BuyerRiskProfile(
        buyer_name=buyer.name,
        total_contracts=total_contracts,
        total_spending_usd=total_spending,
        anomaly_rate=anomaly_rate,
        concentration_hhi=hhi,
        favorite_supplier_share=favorite_supplier_share,
        price_premium=price_premium,
        risk_score=risk_score,
        risk_factors=risk_factors,
        recommendation=recommendation
    )


@dataclass
class SupplierNetworkNode:
    """Node in supplier-buyer network."""
    entity_id: str
    entity_name: str
    entity_type: str  # "supplier" or "buyer"
    connection_count: int
    total_value_usd: float


@dataclass
class SupplierNetworkEdge:
    """Edge in supplier-buyer network."""
    supplier_id: str
    supplier_name: str
    buyer_id: str
    buyer_name: str
    contract_count: int
    total_value_usd: float
    average_amount: float


def get_supplier_buyer_network(db: Session, country_code: str, min_connection_value: float = 0) -> tuple[list[SupplierNetworkNode], list[SupplierNetworkEdge]]:
    """Extract supplier-buyer relationship network.

    Returns nodes (suppliers + buyers) and edges (relationships) for network visualization.
    """
    contracts = db.execute(
        select(models.Contract).where(
            models.Contract.country_code == country_code,
            models.Contract.amount_usd.isnot(None),
            models.Contract.amount_usd > 0
        ).options(
            select(models.Contract.buyer)
        )
    ).scalars().all()

    # Build network
    nodes_dict = {}
    edges_dict = {}

    for contract in contracts:
        if not contract.buyer:
            continue

        supplier_id = contract.external_id or f"supplier_{id(contract)}"
        supplier_name = "Unknown Supplier"
        buyer_id = contract.buyer_id
        buyer_name = contract.buyer.name

        # Add nodes
        if supplier_id not in nodes_dict:
            nodes_dict[supplier_id] = {
                "id": supplier_id,
                "name": supplier_name,
                "type": "supplier",
                "connections": 0,
                "value": 0.0
            }

        if buyer_id not in nodes_dict:
            nodes_dict[buyer_id] = {
                "id": buyer_id,
                "name": buyer_name,
                "type": "buyer",
                "connections": 0,
                "value": 0.0
            }

        # Add edge
        edge_key = (supplier_id, buyer_id)
        if edge_key not in edges_dict:
            edges_dict[edge_key] = {
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "buyer_id": buyer_id,
                "buyer_name": buyer_name,
                "count": 0,
                "value": 0.0
            }

        # Update edge
        edges_dict[edge_key]["count"] += 1
        edges_dict[edge_key]["value"] += contract.amount_usd

        # Update nodes
        nodes_dict[supplier_id]["connections"] += 1
        nodes_dict[supplier_id]["value"] += contract.amount_usd
        nodes_dict[buyer_id]["connections"] += 1
        nodes_dict[buyer_id]["value"] += contract.amount_usd

    # Filter by minimum value and convert to result objects
    nodes = [
        SupplierNetworkNode(
            entity_id=n["id"],
            entity_name=n["name"],
            entity_type=n["type"],
            connection_count=n["connections"],
            total_value_usd=n["value"]
        )
        for n in nodes_dict.values()
        if n["value"] >= min_connection_value
    ]

    edges = [
        SupplierNetworkEdge(
            supplier_id=e["supplier_id"],
            supplier_name=e["supplier_name"],
            buyer_id=e["buyer_id"],
            buyer_name=e["buyer_name"],
            contract_count=e["count"],
            total_value_usd=e["value"],
            average_amount=e["value"] / e["count"] if e["count"] > 0 else 0.0
        )
        for e in edges_dict.values()
        if e["value"] >= min_connection_value
    ]

    return nodes, edges
