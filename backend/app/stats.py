"""Formulas shared by the Fase 5 batch job (compute_statistical_anomalies.py)
and the live /analyze endpoint, so both use the exact same math instead of
two implementations that can silently drift apart.

See scripts/compute_statistical_anomalies.py for the full methodology
writeup (modified z-score on log(amount), Tukey IQR fences, why log-space
matters for right-skewed procurement spend).
"""

import math
import statistics
from dataclasses import dataclass

MIN_GROUP_SIZE = 8
ZSCORE_THRESHOLD = 3.5
IQR_MULTIPLIER = 1.5
ZSCORE_CAP = 50.0


def modified_zscore(value: float, median: float, mad: float) -> float:
    if mad == 0:
        return 0.0
    z = 0.6745 * (value - median) / mad
    return max(-ZSCORE_CAP, min(ZSCORE_CAP, z))


def relative_deviation(amount: float, median_log: float) -> float:
    """How far `amount` sits from a group's median, as a fraction: 0.5 means
    50% above it. The median arrives in log space (see compute_group_stats
    callers), which is why this exponentiates instead of dividing.

    This is the number a reader can act on. The modified z-score says how
    unusual the gap is against the group's own spread, not how much money it
    is, and it saturates at ZSCORE_CAP -- two contracts can both read z=50
    while one costs twice the median and the other a thousand times."""
    if amount <= 0:
        return 0.0
    return math.exp(math.log(amount) - median_log) - 1


def build_reference_stats(rows) -> dict[str, dict]:
    """Group stats for every buyer / category / country, over log(amount).

    `rows` is anything with country_code, buyer_id, category_code and
    amount_original. Shared by the batch job and the API so the reference
    group a contract is judged against is picked the same way in both.
    """
    by_buyer: dict[tuple, list[float]] = {}
    by_category: dict[tuple, list[float]] = {}
    by_country: dict[str, list[float]] = {}

    for row in rows:
        if not row.amount_original or row.amount_original <= 0:
            continue
        log_amount = math.log(row.amount_original)
        if row.buyer_id:
            by_buyer.setdefault((row.country_code, row.buyer_id), []).append(log_amount)
        if row.category_code:
            by_category.setdefault((row.country_code, row.category_code), []).append(log_amount)
        by_country.setdefault(row.country_code, []).append(log_amount)

    return {
        "buyer": {k: compute_group_stats(v) for k, v in by_buyer.items() if len(v) >= MIN_GROUP_SIZE},
        "category": {k: compute_group_stats(v) for k, v in by_category.items() if len(v) >= MIN_GROUP_SIZE},
        "country": {k: compute_group_stats(v) for k, v in by_country.items()},
    }


def pick_reference(
    stats: dict[str, dict],
    country_code: str,
    buyer_id: str | None,
    category_code: str | None,
) -> tuple[dict | None, str | None]:
    """The narrowest group with enough contracts to compare against:
    same buyer, else same category, else the country as a whole."""
    key_buyer = (country_code, buyer_id) if buyer_id else None
    key_category = (country_code, category_code) if category_code else None

    if key_buyer in stats["buyer"]:
        return stats["buyer"][key_buyer], f"{country_code}:buyer:{buyer_id}"
    if key_category in stats["category"]:
        return stats["category"][key_category], f"{country_code}:category:{category_code}"
    if country_code in stats["country"]:
        return stats["country"][country_code], f"{country_code}:country"
    return None, None


def compute_group_stats(values: list[float]) -> dict:
    sorted_vals = sorted(values)
    median = statistics.median(sorted_vals)
    mad = statistics.median([abs(v - median) for v in sorted_vals])
    quantiles = (
        statistics.quantiles(sorted_vals, n=4, method="inclusive")
        if len(sorted_vals) >= 2
        else [median, median, median]
    )
    q1, q3 = quantiles[0], quantiles[2]
    iqr = q3 - q1
    return {"median": median, "mad": mad, "q1": q1, "q3": q3, "iqr": iqr, "n": len(sorted_vals)}


def bootstrap_confidence_interval(values: list[float], ci: float = 0.95, n_bootstrap: int = 1000) -> tuple[float, float]:
    """Calculate 95% confidence interval using bootstrap resampling.
    Returns (lower_bound, upper_bound) for the median."""
    if len(values) < 2:
        return (values[0], values[0]) if values else (0.0, 0.0)

    import random
    bootstrap_medians = []
    for _ in range(n_bootstrap):
        sample = [random.choice(values) for _ in range(len(values))]
        bootstrap_medians.append(statistics.median(sample))

    bootstrap_medians.sort()
    alpha = 1 - ci
    lower_idx = int(n_bootstrap * (alpha / 2))
    upper_idx = int(n_bootstrap * (1 - alpha / 2))
    return (bootstrap_medians[lower_idx], bootstrap_medians[upper_idx])


@dataclass
class AnomalyExplanation:
    """Explains why a value is flagged as anomalous."""
    is_anomaly: bool
    zscore: float
    deviation_pct: float
    reason: str
    severity: str  # "low", "medium", "high", "extreme"
    confidence: float  # 0-1


def explain_anomaly(value: float, median: float, mad: float, iqr: float, q1: float, q3: float) -> AnomalyExplanation:
    """Generate a human-readable explanation of whether/why a value is anomalous."""
    if median == 0:
        return AnomalyExplanation(
            is_anomaly=False,
            zscore=0.0,
            deviation_pct=0.0,
            reason="Grupo vacío o mediana cero",
            severity="low",
            confidence=0.0
        )

    zscore = modified_zscore(value, median, mad)
    deviation_pct = ((value - median) / median * 100) if median != 0 else 0

    # Determine if anomalous by multiple criteria
    is_zscore_anomaly = abs(zscore) > ZSCORE_THRESHOLD
    is_iqr_anomaly = (iqr > 0) and (value < q1 - IQR_MULTIPLIER * iqr or value > q3 + IQR_MULTIPLIER * iqr)
    is_anomaly = is_zscore_anomaly or is_iqr_anomaly

    # Determine severity
    if not is_anomaly:
        severity = "low"
        reason = f"Dentro del rango esperado (mediana: {median:.0f}, desv: {deviation_pct:+.1f}%)"
        confidence = 0.8
    elif abs(zscore) > 7:
        severity = "extreme"
        reason = f"Extremadamente desviado (z-score: {zscore:.2f}, desv: {deviation_pct:+.1f}%)"
        confidence = 0.98
    elif abs(zscore) > 5:
        severity = "high"
        reason = f"Muy desviado estadísticamente (z-score: {zscore:.2f}, desv: {deviation_pct:+.1f}%)"
        confidence = 0.95
    elif abs(zscore) > 3.5:
        severity = "medium"
        reason = f"Desviado significativamente (z-score: {zscore:.2f}, desv: {deviation_pct:+.1f}%)"
        confidence = 0.85
    else:
        severity = "low"
        reason = f"Ligeramente desviado pero dentro de límites (desv: {deviation_pct:+.1f}%)"
        confidence = 0.7

    return AnomalyExplanation(
        is_anomaly=is_anomaly,
        zscore=zscore,
        deviation_pct=deviation_pct,
        reason=reason,
        severity=severity,
        confidence=confidence
    )
