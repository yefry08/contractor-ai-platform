"""Formulas shared by the Fase 5 batch job (compute_statistical_anomalies.py)
and the live /analyze endpoint, so both use the exact same math instead of
two implementations that can silently drift apart.

See scripts/compute_statistical_anomalies.py for the full methodology
writeup (modified z-score on log(amount), Tukey IQR fences, why log-space
matters for right-skewed procurement spend).
"""

import statistics

MIN_GROUP_SIZE = 8
ZSCORE_THRESHOLD = 3.5
IQR_MULTIPLIER = 1.5
ZSCORE_CAP = 50.0


def modified_zscore(value: float, median: float, mad: float) -> float:
    if mad == 0:
        return 0.0
    z = 0.6745 * (value - median) / mad
    return max(-ZSCORE_CAP, min(ZSCORE_CAP, z))


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
