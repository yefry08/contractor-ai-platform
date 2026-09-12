"""Turns a flagged contract into "X% over comparable contracts".

The stored signal is a modified z-score, which answers "how unusual is this
against the group's spread" -- useful for ranking, unreadable on screen, and
capped at ZSCORE_CAP so very different overprices all read the same. The
percentage over the group's median answers "how much money", which is what a
reader is actually after.

That percentage needs the group's median, which is not stored anywhere, so it
is recomputed here from the same grouping rule the batch job uses (see
app/stats.py). Recomputing per request would mean a full pass over the corpus
each time, so the group stats are cached in-process for CACHE_TTL_SECONDS.
The cache is per worker and rebuilt on expiry: newly ingested contracts move
a group's median only after it turns over, which is fine for a median over
thousands of contracts.
"""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .stats import build_reference_stats, pick_reference, relative_deviation

CACHE_TTL_SECONDS = 600

_cache: dict = {"built_at": 0.0, "stats": None}


def reset_cache() -> None:
    """Drops the cached stats. Tests call this between cases, where each one
    builds its own tiny corpus and would otherwise read the previous one's."""
    _cache["built_at"] = 0.0
    _cache["stats"] = None


def get_reference_stats(db: Session) -> dict[str, dict]:
    now = time.monotonic()
    if _cache["stats"] is None or (now - _cache["built_at"]) > CACHE_TTL_SECONDS:
        rows = db.execute(
            select(
                models.Contract.country_code,
                models.Contract.buyer_id,
                models.Contract.category_code,
                models.Contract.amount_original,
            ).where(
                models.Contract.amount_original.isnot(None),
                models.Contract.amount_original > 0,
            )
        ).all()
        _cache["stats"] = build_reference_stats(rows)
        _cache["built_at"] = now
    return _cache["stats"]


def deviation_for(db: Session, contract: models.Contract | None) -> float | None:
    """Fraction over (positive) or under (negative) the median of comparable
    contracts. None when the contract has no usable amount or no group."""
    if contract is None or not contract.amount_original or contract.amount_original <= 0:
        return None

    stats = get_reference_stats(db)
    group, _ = pick_reference(stats, contract.country_code, contract.buyer_id, contract.category_code)
    if group is None:
        return None
    return relative_deviation(contract.amount_original, group["median"])
