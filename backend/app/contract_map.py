"""Contract map: which institutions buy what, over the whole corpus.

The dashboard graph used to draw from the few hundred most recent contracts
the /contracts endpoint returns, which made "all countries" whichever country
loaded last. This groups every contract that matches the filter in the
database instead: country -> institution -> sector, with contract counts,
value in the local currency and how many carry an open alert.

Sectors come from contract_sectors (scripts/classify_contracts.py). Contracts
loaded since the last run have no row yet; those of the institutions on the
map are classified here, so the map is complete either way.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict

from sqlalchemy import case, func, literal, select
from sqlalchemy.orm import Session

from . import models
from .territories import classify_sector, normalize_name

# SECOP's UNSPSC code, which classify_sector falls back on when the words say
# nothing. Only Colombian contracts carry it.
UNSPSC = models.Contract.raw_ocds_json["codigo_de_categoria_principal"].as_string()


def _cell() -> list:
    return [0, 0.0, 0]  # contracts, value (local currency), flagged


def _add(cell: list, n: int, value: float, flagged: int) -> None:
    cell[0] += n
    cell[1] += value
    cell[2] += flagged


def _out(cell: list) -> dict:
    return {"contracts": cell[0], "value": round(cell[1], 2), "flagged": cell[2]}


def contract_map(db: Session, country: str | None, flagged_only: bool, metric: str, limit: int) -> dict:
    """The `limit` institutions with most contracts (or most value), the
    sectors they buy, and totals for everything the filter matched. With no
    country, the institutions are split evenly across countries so that every
    country appears, not only the one with the most contracts.

    Value is the amount in the country's own currency, so it exists only with
    a country: USD amounts are missing for most countries (Colombia,
    Guatemala, Brazil and the Dominican Republic publish none), and summing
    them across countries would compare whatever happened to be converted."""
    if metric == "value" and not country:
        raise ValueError("value needs a country")
    flagged_ids = (
        select(models.Anomaly.contract_id).where(models.Anomaly.status == "open").distinct().subquery()
    )
    is_flagged = case((flagged_ids.c.contract_id.isnot(None), 1), else_=0)
    filters = []
    if country:
        filters.append(models.Contract.country_code == country)
    if flagged_only:
        filters.append(flagged_ids.c.contract_id.isnot(None))

    # Amounts count in the country's usual currency only; the odd contract in
    # dollars or euros is left out of the sums rather than added as if local.
    currency = None
    if country:
        currency = db.execute(
            select(models.Contract.currency).where(models.Contract.country_code == country,
                                                   models.Contract.amount_original.isnot(None))
            .group_by(models.Contract.currency).order_by(func.count().desc()).limit(1)
        ).scalar()
    amount = (
        case((models.Contract.currency == currency, models.Contract.amount_original), else_=0.0)
        if currency else literal(0.0)
    )

    rows = db.execute(
        select(
            models.Contract.country_code,
            models.Contract.buyer_id,
            models.ContractSector.sector,
            func.count().label("n"),
            func.coalesce(func.sum(amount), 0.0).label("value"),
            func.sum(is_flagged).label("flagged"),
        )
        .outerjoin(models.ContractSector, models.ContractSector.contract_id == models.Contract.id)
        .outerjoin(flagged_ids, flagged_ids.c.contract_id == models.Contract.id)
        .where(*filters)
        .group_by(models.Contract.country_code, models.Contract.buyer_id, models.ContractSector.sector)
    ).all()

    # Portals register some institutions more than once ("CAJA COSTARRICENSE
    # DE SEGURO SOCIAL" under two ids): one node per name and country.
    buyer_q = select(models.Buyer.id, models.Buyer.name, models.Buyer.country_code)
    if country:
        buyer_q = buyer_q.where(models.Buyer.country_code == country)
    group_of: dict[str, tuple[str, str]] = {}
    name_of: dict[str, str] = {}
    for b in db.execute(buyer_q):
        group_of[b.id] = (b.country_code, normalize_name(b.name) or b.id)
        name_of[b.id] = b.name

    total = _cell()
    countries: dict[str, list] = defaultdict(_cell)
    groups: dict[tuple, list] = defaultdict(_cell)
    members: dict[tuple, Counter[str]] = defaultdict(Counter)
    for r in rows:
        args = (r.n, float(r.value or 0), int(r.flagged or 0))
        _add(total, *args)
        _add(countries[r.country_code], *args)
        if r.buyer_id and r.buyer_id in group_of:
            g = group_of[r.buyer_id]
            _add(groups[g], *args)
            members[g][r.buyer_id] += r.n

    rank = 1 if metric == "value" else 0
    # Ranking by value, an institution with no amounts would sit on the map
    # as an empty node.
    ordered = sorted((g for g in groups if groups[g][rank] > 0), key=lambda g: -groups[g][rank])
    if country:
        chosen = ordered[:limit]
    else:
        quota = max(1, math.ceil(limit / max(1, len(countries))))
        taken: Counter[str] = Counter()
        chosen = []
        for g in ordered:
            if taken[g[0]] < quota:
                chosen.append(g)
                taken[g[0]] += 1
    chosen_set = set(chosen)
    member_ids = [b for g in chosen for b in members[g]]

    links: dict[tuple[tuple, str], list] = defaultdict(_cell)
    for r in rows:
        g = group_of.get(r.buyer_id) if r.buyer_id else None
        if g in chosen_set and r.sector:
            _add(links[(g, r.sector)], r.n, float(r.value or 0), int(r.flagged or 0))
    if chosen:
        missing = db.execute(
            select(models.Contract.buyer_id, models.Contract.title, models.Contract.description,
                   models.Contract.category_code, UNSPSC, amount.label("amount"), is_flagged.label("flagged"))
            .outerjoin(models.ContractSector, models.ContractSector.contract_id == models.Contract.id)
            .outerjoin(flagged_ids, flagged_ids.c.contract_id == models.Contract.id)
            .where(*filters, models.ContractSector.contract_id.is_(None), models.Contract.buyer_id.in_(member_ids))
        ).all()
        for m in missing:
            sector = classify_sector(m.title, m.description, m.category_code, unspsc=m[4])
            _add(links[(group_of[m.buyer_id], sector)], 1, float(m.amount or 0), int(m.flagged or 0))

    sectors: dict[str, list] = defaultdict(_cell)
    main_sector: dict[tuple, tuple[float, str]] = {}
    for (g, sector), cell in links.items():
        _add(sectors[sector], *cell)
        if cell[rank] > main_sector.get(g, (-1.0, ""))[0]:
            main_sector[g] = (cell[rank], sector)

    # The member with most contracts stands for the group: its id is what the
    # institution page opens.
    lead = {g: members[g].most_common(1)[0][0] for g in chosen}
    shown = _cell()
    for g in chosen:
        _add(shown, *groups[g])
    return {
        "metric": "value" if rank else "contracts",
        "currency": currency,
        "total": _out(total),
        "shown": _out(shown),
        "countries": sorted(
            ({"code": c, **_out(cell)} for c, cell in countries.items()), key=lambda c: -c["contracts"]
        ),
        "buyers": [
            {
                "id": lead[g],
                "name": name_of.get(lead[g], ""),
                "country_code": g[0],
                "main_sector": main_sector.get(g, (0, None))[1],
                **_out(groups[g]),
            }
            for g in chosen
        ],
        "sectors": sorted(
            ({"key": s, **_out(cell)} for s, cell in sectors.items()), key=lambda s: -s["contracts"]
        ),
        "links": [
            {"buyer_id": lead[g], "sector": s, **_out(cell)}
            for (g, s), cell in sorted(links.items(), key=lambda kv: -kv[1][rank])
        ],
    }
