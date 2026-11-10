"""Territorios: what a place needs, what is failing, and where money goes.

Three questions, each answered only with data that can be cited:

* What does the population need?  Official indicators per territory
  (TerritoryIndicator, loaded by scripts/ingest_territory_indicators.py):
  unmet basic needs from the census and education statistics. Each value is
  shown next to the national figure and its rank among peer territories.
* What is failing?  Contract alerts (statistical and AI) in the territory
  against the national rate, the contracts behind them, education indicators
  that got worse year on year, and how many inquiries name the place.
* Where does the money go?  Contracts linked to the territory, grouped into
  sectors by a keyword classifier on what each contract says it buys.

"Priorities" rank the needs indicators by how badly the territory compares
with its peers, and say next to each one how much of the local spending goes
to that sector. It's a ranking of measured gaps, not a recommendation: the
page says so, and every number links back to its source.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models

# Order matters: the first sector whose keywords appear wins, so the specific
# ones ("alimentación escolar") come before the general ones ("alimentación").
SECTOR_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("agua_saneamiento", ("agua potable", "acueducto", "alcantarillado", "saneamiento", "aguas residuales", "aguas servidas",
                          "planta de tratamiento", "pozo profundo", "tanque elevado", "letrina", "drenaje", "pluvial",
                          "esgoto", "abastecimento de agua", "abastecimento de água", "água potável")),
    ("educacion", ("alimentacion escolar", "alimentación escolar", "escuela", "colegio", "institucion educativa",
                   "institución educativa", "educativ", "docente", "estudiantes", "aula", "utiles escolares",
                   "útiles escolares", "escolar", "escola", "educação", "educacao", "universidad", "liceo")),
    ("salud", ("salud", "hospital", "medicament", "clinic", "clínic", "medico", "médic", "vacun", "ambulancia",
               "odontolog", "laboratorio clinico", "laboratorio clínico", "saúde", "saude", "farmac", "puesto de salud",
               "centro de salud", "insumos medicos", "insumos médicos", "quirurg", "quirúrg", "reactivo", "diagnostic",
               "rayos x", "biomedic", "biomédic", "oxigeno medicinal", "oxígeno medicinal", "comprimido", "tableta",
               "inyectable", "ampolla", "jeringa", "osteosintesis", "osteosíntesis", "oncolog", "paciente", " mg ")),
    ("vias_transporte", ("via ", "vía ", "vias ", "vías ", "carretera", "pavimenta", "asfalt", "puente", "camino vecinal",
                         "malla vial", "bacheo", "señalizacion vial", "señalización vial", "rodovia", "estrada",
                         "pavimentação", "pavimentacao", "transporte publico", "transporte público", "calles")),
    ("vivienda", ("vivienda", "mejoramiento de vivienda", "habitacional", "moradia", "habitação", "habitacao")),
    ("alimentacion", ("alimentos", "alimentacion", "alimentación", "raciones", "comedor", "viveres", "víveres",
                      "kits alimentarios", "alimentação", "alimentacao", "merienda", "catering", "almuerzo",
                      "refrigerio", "generos alimenticios", "gêneros alimentícios")),
    ("seguridad", ("seguridad ciudadana", "vigilancia", "policia", "policía", "camaras de seguridad", "cámaras de seguridad",
                   "segurança", "seguranca", "carcel", "cárcel", "penitenciari")),
    ("energia", ("energia electrica", "energía eléctrica", "alumbrado", "electrificacion", "electrificación",
                 "iluminacion publica", "iluminación pública", "energia eletrica", "energía solar", "paneles solares")),
    ("ambiente", ("residuos solidos", "residuos sólidos", "recoleccion de basura", "recolección de basura", "relleno sanitario",
                  "reforestacion", "reforestación", "ambiental", "resíduos", "residuos")),
]
# What most of the rest buys. These are not needs a census measures, so they
# are only tried after the sectors above and the UNSPSC code have said nothing.
GENERIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("tecnologia", ("software", "hardware", "informatic", "informátic", "computador", "computo", "cómputo", "servidores",
                    "licencias de", "licenciamiento", "internet", "telecomunicac", "impresora", "toner", "tóner", "conectividad", "laptop",
                    "ciberseguridad", "sistema de informacion", "sistema de información", "centro de datos",
                    "fibra optica", "fibra óptica", "fibras opticas", "fibras ópticas")),
    ("vehiculos_combustible", ("combustible", "diesel", "diésel", "gasolina", "lubricante", "llantas", "neumatic",
                               "neumátic", "repuesto", "automotriz", "vehiculo", "vehículo", "automotor", "camion", "camión",
                               "combustivel", "combustível", "veiculo", "veículo", "pneus", "peças automotivas")),
    ("obras", ("construccion", "construcción", "construção", "construcao", " obra ", " obras ", "obra civil",
               "remodelacion", "remodelación", "adecuacion", "adecuación", "infraestructura", "edificacion",
               "edificación", "ampliacion", "ampliación", "cerramiento", "engenharia", "arquitetura", "reforma predial")),
    ("comunicacion", ("publicidad", "publicitari", "difusion", "difusión", "comunicacion", "comunicación", "periodis",
                      "audiovisual", "evento", "material grafico", "material gráfico", "impresion de", "impresión de",
                      "divulgação", "divulgacao", "publicidade", "prensa", "periodico", "periódico", "publicacion",
                      "publicación", "suscripcion", "suscripción")),
    ("mantenimiento_limpieza", ("limpieza", " aseo", "fumigacion", "fumigación", "jardineria", "jardinería", "extintores",
                                "ascensor", "mantenimiento", "manutenção", "manutencao", "limpeza", "reparacion",
                                "reparación", "ferreter", "plomeria", "plomería", "pintura", "cerrajeria", "cerrajería",
                                "aire acondicionado", "zafacon", "zafacón")),
    ("administracion", ("servicios profesionales", "apoyo a la gestion", "apoyo a la gestión", "prestacion de servicios",
                        "prestación de servicios", "prestar servicios", "consultoria", "consultoría", "asesoria",
                        "asesoría", "auditoria", "auditoría", "papeleria", "papelería", "utiles de oficina",
                        "útiles de oficina", "articulos de oficina", "artículos de oficina", "material de escritorio",
                        "mobiliario", "uniformes", "indumentaria", "arrendamiento", "alquiler de", "capacitacion",
                        "capacitación", "seguros", "poliza", "póliza", "pasajes", "viaticos", "viáticos",
                        "material de consumo", "material de expediente", "pasaje", "papel", "material de oficina",
                        "calzado", "zapato")),
]
SECTORS = (
    [s for s, _ in SECTOR_KEYWORDS]
    + [s for s, _ in GENERIC_KEYWORDS if s != "administracion"]
    + ["administracion", "sin_detalle", "otros"]
)

# When the words say nothing, the UNSPSC code SECOP publishes often does.
# Longest prefix wins.
UNSPSC_SECTORS: list[tuple[str, str]] = sorted(
    [
        ("85", "salud"), ("42", "salud"), ("51", "salud"),
        ("86", "educacion"), ("6010", "educacion"), ("6011", "educacion"), ("6012", "educacion"),
        ("50", "alimentacion"), ("9010", "alimentacion"),
        ("76", "ambiente"), ("77", "ambiente"),
        ("92", "seguridad"), ("46", "seguridad"),
        ("831015", "agua_saneamiento"), ("831018", "energia"), ("39", "energia"),
        ("721410", "vias_transporte"), ("7211", "vivienda"),
        ("8011", "administracion"), ("8016", "administracion"), ("8010", "administracion"), ("44", "administracion"),
    ],
    key=lambda p: -len(p[0]),
)


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize_name(name: str | None) -> str:
    """Lowercase, no accents, no punctuation, single spaces: "BOGOTÁ, D.C." -> "bogota dc"."""
    text = strip_accents((name or "").lower())
    text = re.sub(r"[^a-z0-9ñ ]+", " ", text.replace(".", ""))
    return re.sub(r"\s+", " ", text).strip()


# Portals spell some places differently from the statistics offices.
REGION_ALIASES = {
    "distrito capital de bogota": "bogota dc",
    "bogota": "bogota dc",
    "san andres providencia y santa catalina": "archipielago de san andres providencia y santa catalina",
    "san andres": "archipielago de san andres providencia y santa catalina",
}


def region_key(name: str | None) -> str:
    key = normalize_name(name)
    return REGION_ALIASES.get(key, key)


# Keywords without accents, matched against text without accents. A keyword
# found in the text is also found once both lose their accents, so this gives
# what comparing each keyword both ways did, at a fraction of the cost:
# stripping every keyword on every call took ~30 s over the corpus, and a
# regex alternation is slower than plain substring checks.
def _folded(groups: list[tuple[str, tuple[str, ...]]]) -> list[tuple[str, tuple[str, ...]]]:
    return [(s, tuple(dict.fromkeys(strip_accents(w) for w in words))) for s, words in groups]


_SECTOR_WORDS = _folded(SECTOR_KEYWORDS)
_GENERIC_WORDS = _folded(GENERIC_KEYWORDS)

# strip_accents for the letters these portals use, without decomposing every
# character; anything else still goes through unicodedata.
_FOLD = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçñ", "aaaaaeeeeiiiiooooouuuucn")


def _fold(text: str) -> str:
    folded = text.translate(_FOLD)
    return folded if folded.isascii() else strip_accents(folded)


# Words that describe the procedure, not what is bought. A text made only of
# these (and reference numbers) says nothing about the purchase: Brazil
# publishes many contracts whose whole text is the standard supplier clause.
_PROCEDURE_WORDS = {
    "contrato", "contratos", "contratacion", "contratacao", "pedido", "orden", "compra", "compras", "directa", "direta",
    "licitacion", "licitacao", "pregao", "dispensa", "edital", "proceso", "processo", "expediente", "empenho", "empenha",
    "valor", "fornecedor", "vincula", "proposta", "instrumento", "convocatorio", "anexos", "hipoteses", "infracao",
    "artigo", "estao", "previstas", "seus", "suas", "conforme", "atender", "despesa", "despesas", "numero", "item",
    "itens", "lote", "lotes", "para", "como", "segun", "acuerdo", "marco", "convenio", "aquisicao", "adquisicion",
}


def _describes_something(plain: str) -> bool:
    for token in plain.split():
        word = token.strip(".,;:()\"'")
        if len(word) >= 4 and word.isalpha() and word not in _PROCEDURE_WORDS:
            return True
    return False


def classify_sector(*texts: str | None, unspsc: str | None = None) -> str:
    plain = _fold(" " + " ".join(t for t in texts if t).lower() + " ")
    for sector, words in _SECTOR_WORDS:
        if any(w in plain for w in words):
            return sector
    digits = re.sub(r"\D", "", (unspsc or "").split(".")[-1])
    for prefix, sector in UNSPSC_SECTORS:
        if digits.startswith(prefix):
            return sector
    for sector, words in _GENERIC_WORDS:
        if any(w in plain for w in words):
            return sector
    # Some portals publish only a reference number or boilerplate: say so
    # rather than filing it with contracts whose words we could not place.
    return "otros" if _describes_something(plain) else "sin_detalle"


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def countries_overview(db: Session) -> dict[str, dict]:
    """Per country: how many territories have indicators, and how many
    contracts are linked to a territory."""
    terr = dict(
        db.execute(
            select(models.Territory.country_code, func.count(func.distinct(models.TerritoryIndicator.territory_id)))
            .join(models.TerritoryIndicator, models.TerritoryIndicator.territory_id == models.Territory.id)
            .group_by(models.Territory.country_code)
        ).all()
    )
    linked = dict(
        db.execute(
            select(models.Territory.country_code, func.count())
            .join(models.ContractTerritory, models.ContractTerritory.territory_id == models.Territory.id)
            .group_by(models.Territory.country_code)
        ).all()
    )
    return {c: {"territories_with_indicators": terr.get(c, 0), "linked_contracts": linked.get(c, 0)} for c in set(terr) | set(linked)}


def list_territories(db: Session, country: str, level: str | None, q: str | None, limit: int, offset: int):
    stmt = select(models.Territory).where(models.Territory.country_code == country)
    if level:
        stmt = stmt.where(models.Territory.level == level)
    if q:
        stmt = stmt.where(models.Territory.normalized_name.like(f"%{normalize_name(q)}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    # Worst first: by the headline indicator's rank among peers.
    rank = (
        select(models.TerritoryIndicator.territory_id, func.max(models.TerritoryIndicator.peer_percentile).label("pct"))
        .where(models.TerritoryIndicator.key.in_(HEADLINE_KEYS))
        .group_by(models.TerritoryIndicator.territory_id)
        .subquery()
    )
    rows = db.execute(
        stmt.outerjoin(rank, rank.c.territory_id == models.Territory.id)
        .order_by(rank.c.pct.desc().nullslast(), models.Territory.normalized_name)
        .limit(limit)
        .offset(offset)
    ).scalars().all()
    ids = [t.id for t in rows]

    headline: dict[str, models.TerritoryIndicator] = {}
    if ids:
        for ind in db.execute(
            select(models.TerritoryIndicator).where(
                models.TerritoryIndicator.territory_id.in_(ids), models.TerritoryIndicator.key.in_(HEADLINE_KEYS)
            )
        ).scalars():
            current = headline.get(ind.territory_id)
            if current is None or HEADLINE_KEYS.index(ind.key) < HEADLINE_KEYS.index(current.key):
                headline[ind.territory_id] = ind

    linked = dict(
        db.execute(
            select(models.ContractTerritory.territory_id, func.count())
            .where(models.ContractTerritory.territory_id.in_(ids))
            .group_by(models.ContractTerritory.territory_id)
        ).all()
    ) if ids else {}
    dept_linked = dict(
        db.execute(
            select(models.ContractTerritory.department_id, func.count())
            .where(models.ContractTerritory.department_id.in_(ids))
            .group_by(models.ContractTerritory.department_id)
        ).all()
    ) if ids else {}
    out = []
    for t in rows:
        h = headline.get(t.id)
        out.append(
            {
                "id": t.id,
                "level": t.level,
                "name": t.name,
                "code": t.code,
                "headline": _indicator_out(h) if h else None,
                "linked_contracts": max(linked.get(t.id, 0), dept_linked.get(t.id, 0)),
            }
        )
    return total, out


# The single number shown in lists, first available wins.
HEADLINE_KEYS = ["nbi_total", "nbi_hogares_total", "pobreza_general"]

LABELS = {
    "nbi_total": "Personas con al menos una necesidad básica insatisfecha",
    "nbi_miseria": "Personas en miseria (dos o más NBI)",
    "nbi_vivienda": "NBI: vivienda inadecuada",
    "nbi_servicios": "NBI: servicios inadecuados (agua, saneamiento)",
    "nbi_hacinamiento": "NBI: hacinamiento crítico",
    "nbi_inasistencia": "NBI: niños que no asisten a la escuela",
    "nbi_dependencia": "NBI: alta dependencia económica",
    "nbi_hogares_total": "Hogares con al menos una necesidad básica insatisfecha",
    "nbi_calidad_vivienda": "NBI: calidad de la vivienda",
    "nbi_infra_sanitaria": "NBI: infraestructura sanitaria",
    "nbi_acceso_educacion": "NBI: acceso a la educación",
    "nbi_subsistencia": "NBI: capacidad de subsistencia",
    "edu_cobertura_neta": "Cobertura neta de educación (5 a 16 años)",
    "edu_desercion": "Deserción escolar",
    "pobreza_general": "Pobreza monetaria",
    "pobreza_extrema": "Pobreza monetaria extrema",
}

# Aggregates summarise the components; ranking them next to the components
# would count the same gap twice.
AGGREGATE_KEYS = {"nbi_total", "nbi_miseria", "nbi_hogares_total"}


def _indicator_out(ind: models.TerritoryIndicator) -> dict:
    return {
        "key": ind.key,
        "label": LABELS.get(ind.key, ind.key),
        "sector": ind.sector,
        "value": ind.value,
        "national_value": ind.national_value,
        "unit": ind.unit,
        "worse_when": ind.worse_when,
        "year": ind.year,
        "peer_percentile": ind.peer_percentile,
        "source": ind.source,
        "source_url": ind.source_url,
    }


def _territory_filter(territory: models.Territory):
    """Contracts of a department/region include its municipalities'."""
    if territory.level in ("department", "region"):
        return models.ContractTerritory.department_id == territory.id
    return models.ContractTerritory.territory_id == territory.id


def _contracts_for(db: Session, territory: models.Territory):
    # Only the columns the shares need: raw_ocds_json makes full rows heavy.
    rows = db.execute(
        select(models.Contract.currency, models.Contract.amount_original, models.ContractTerritory.sector)
        .join(models.ContractTerritory, models.ContractTerritory.contract_id == models.Contract.id)
        .where(_territory_filter(territory))
    ).all()
    return [(r, r.sector) for r in rows]


def _flagged(db: Session, where) -> tuple[int, list[dict]]:
    """Contracts with an open alert matching `where`: how many, and the eight
    with the highest score."""
    n = db.execute(
        select(func.count(func.distinct(models.Anomaly.contract_id)))
        .join(models.Contract, models.Contract.id == models.Anomaly.contract_id)
        .outerjoin(models.ContractTerritory, models.ContractTerritory.contract_id == models.Contract.id)
        .where(where, models.Anomaly.status == "open")
    ).scalar_one()
    top, seen = [], set()
    for a, cid, title, amount, currency, buyer in db.execute(
        select(models.Anomaly.anomaly_type, models.Contract.id, models.Contract.title, models.Contract.amount_original,
               models.Contract.currency, models.Buyer.name)
        .join(models.Contract, models.Contract.id == models.Anomaly.contract_id)
        .outerjoin(models.Buyer, models.Buyer.id == models.Contract.buyer_id)
        .outerjoin(models.ContractTerritory, models.ContractTerritory.contract_id == models.Contract.id)
        .where(where, models.Anomaly.status == "open")
        .order_by(models.Anomaly.composite_score.desc().nullslast())
        .limit(40)
    ).all():
        if cid in seen:
            continue
        seen.add(cid)
        top.append({"contract_id": cid, "title": title, "buyer": buyer, "amount": amount, "currency": currency,
                    "anomaly_type": a})
        if len(top) >= 8:
            break
    return n, top


def _national_anomaly_rate(db: Session, country: str) -> float | None:
    contracts = db.execute(
        select(func.count()).select_from(models.Contract).where(models.Contract.country_code == country)
    ).scalar_one()
    flagged = db.execute(
        select(func.count(func.distinct(models.Anomaly.contract_id)))
        .join(models.Contract, models.Contract.id == models.Anomaly.contract_id)
        .where(models.Contract.country_code == country, models.Anomaly.status == "open")
    ).scalar_one()
    return flagged / contracts if contracts else None


def _sector_shares(rows) -> dict[str, dict]:
    """Share of contracts and of amount per sector. Amounts are summed in the
    most common currency only: different currencies can't be added."""
    if not rows:
        return {}
    currency = Counter(c.currency for c, _ in rows).most_common(1)[0][0]
    counts, amounts = Counter(), defaultdict(float)
    for c, sector in rows:
        counts[sector] += 1
        if c.currency == currency and c.amount_original:
            amounts[sector] += c.amount_original
    total_n = sum(counts.values())
    total_amount = sum(amounts.values()) or 1.0
    return {
        s: {
            "contracts": counts[s],
            "contract_share": counts[s] / total_n,
            "amount": amounts[s],
            "amount_share": amounts[s] / total_amount,
            "currency": currency,
        }
        for s in counts
    }


def _national_sector_shares(db: Session, country: str) -> dict[str, float]:
    rows = db.execute(
        select(models.ContractTerritory.sector, func.count())
        .join(models.Territory, models.Territory.id == models.ContractTerritory.territory_id)
        .where(models.Territory.country_code == country)
        .group_by(models.ContractTerritory.sector)
    ).all()
    total = sum(n for _, n in rows) or 1
    return {s: n / total for s, n in rows}


def territory_profile(db: Session, territory_id: str) -> dict | None:
    t = db.get(models.Territory, territory_id)
    if t is None:
        return None
    parent = db.get(models.Territory, t.parent_id) if t.parent_id else None

    indicators = db.execute(
        select(models.TerritoryIndicator).where(models.TerritoryIndicator.territory_id == t.id)
    ).scalars().all()
    latest: dict[str, models.TerritoryIndicator] = {}
    previous: dict[str, models.TerritoryIndicator] = {}
    for ind in sorted(indicators, key=lambda i: i.year):
        if ind.key in latest:
            previous[ind.key] = latest[ind.key]
        latest[ind.key] = ind

    rows = _contracts_for(db, t)
    shares = _sector_shares(rows)
    national_shares = _national_sector_shares(db, t.country_code)

    # Priorities: components ranked by how badly the place compares with its peers.
    priorities = []
    for ind in latest.values():
        if ind.key in AGGREGATE_KEYS or ind.peer_percentile is None:
            continue
        local = shares.get(ind.sector)
        # Poverty and income have no contract sector to compare with.
        comparable = bool(rows) and ind.sector in SECTORS
        priorities.append(
            {
                **_indicator_out(ind),
                "local_contract_share": (local["contract_share"] if local else 0.0) if comparable else None,
                "national_contract_share": national_shares.get(ind.sector, 0.0) if comparable else None,
            }
        )
    priorities.sort(key=lambda p: p["peer_percentile"], reverse=True)

    # Year-on-year changes for the indicators published more than once.
    worsening = []
    for key, ind in latest.items():
        prev = previous.get(key)
        if not prev:
            continue
        delta = ind.value - prev.value
        worse = delta > 0 if ind.worse_when == "high" else delta < 0
        if worse and abs(delta) >= 0.1:
            worsening.append({**_indicator_out(ind), "previous_value": prev.value, "previous_year": prev.year})

    anomaly_n, flagged = _flagged(db, _territory_filter(t)) if rows else (0, [])

    inquiries = db.execute(
        select(func.count())
        .select_from(models.Inquiry)
        .where(models.Inquiry.country_code == t.country_code, func.lower(models.Inquiry.institution).like(f"%{t.name.lower()}%"))
    ).scalar_one()

    open_calls = []
    if t.level in ("department", "municipality"):
        dept_name = region_key(parent.name if parent else t.name)
        for o in db.execute(
            select(models.Opportunity.id, models.Opportunity.title, models.Opportunity.buyer_name,
                   models.Opportunity.region, models.Opportunity.deadline, models.Opportunity.url,
                   models.Opportunity.estimated_amount, models.Opportunity.currency)
            .where(models.Opportunity.country_code == t.country_code, models.Opportunity.deadline > datetime.utcnow())
            .order_by(models.Opportunity.deadline.asc())
            .limit(3000)
        ).all():
            # CO calls carry the buyer's department; a municipality also
            # needs the buyer to be named after it.
            if region_key(o.region) != dept_name:
                continue
            if t.level == "municipality" and f" {region_key(t.name)} " not in f" {region_key(o.buyer_name)} ":
                continue
            open_calls.append({"id": o.id, "title": o.title, "buyer": o.buyer_name, "deadline": o.deadline, "url": o.url,
                               "estimated_amount": o.estimated_amount, "currency": o.currency})
            if len(open_calls) >= 6:
                break

    return {
        "id": t.id,
        "country_code": t.country_code,
        "level": t.level,
        "code": t.code,
        "name": t.name,
        "parent": {"id": parent.id, "name": parent.name, "level": parent.level} if parent else None,
        "indicators": sorted((_indicator_out(i) for i in latest.values()), key=lambda i: i["key"]),
        "priorities": priorities,
        "worsening": worsening,
        "spending": {
            "linked_contracts": len(rows),
            "sectors": [{"sector": s, **v, "national_contract_share": national_shares.get(s)} for s, v in
                        sorted(shares.items(), key=lambda kv: -kv[1]["contracts"])],
        },
        "failures": {
            "anomalies": anomaly_n,
            "anomaly_rate": anomaly_n / len(rows) if rows else None,
            "national_anomaly_rate": _national_anomaly_rate(db, t.country_code),
            "flagged_contracts": flagged,
            "inquiries": inquiries,
        },
        "open_calls": open_calls,
    }


def list_institutions(db: Session, country: str, q: str | None, limit: int, offset: int):
    """Buyers of a country with enough contracts to describe, local
    governments first. Works for all ten countries: it needs no territory."""
    stmt = (
        select(models.Buyer.id, models.Buyer.name, func.count(models.Contract.id).label("n"))
        .join(models.Contract, models.Contract.buyer_id == models.Buyer.id)
        .where(models.Buyer.country_code == country)
        .group_by(models.Buyer.id, models.Buyer.name)
        .having(func.count(models.Contract.id) >= 3)
    )
    if q:
        stmt = stmt.where(models.Buyer.normalized_name.like(f"%{q.strip().lower()}%"))
    rows = db.execute(stmt).all()
    rows.sort(key=lambda r: (not _is_local_government(r.name), -r.n))
    total = len(rows)
    page = rows[offset : offset + limit]
    ids = [r.id for r in page]
    flagged = dict(
        db.execute(
            select(models.Contract.buyer_id, func.count(func.distinct(models.Contract.id)))
            .join(models.Anomaly, models.Anomaly.contract_id == models.Contract.id)
            .where(models.Contract.buyer_id.in_(ids), models.Anomaly.status == "open")
            .group_by(models.Contract.buyer_id)
        ).all()
    ) if ids else {}
    return total, [
        {
            "id": r.id,
            "name": r.name,
            "contracts": r.n,
            "anomaly_rate": flagged.get(r.id, 0) / r.n,
            "local_government": _is_local_government(r.name),
        }
        for r in page
    ]


LOCAL_GOV = re.compile(
    r"\b(municipalidad|municipio|alcald[ií]a|ayuntamiento|gobernaci[oó]n|prefeitura|intendencia|"
    r"junta distrital|distrito municipal|concejo municipal|c[aá]mara municipal|gobierno departamental)\b",
    re.IGNORECASE,
)


def _is_local_government(name: str | None) -> bool:
    return bool(name and LOCAL_GOV.search(name))


def institution_profile(db: Session, buyer_id: str) -> dict | None:
    buyer = db.get(models.Buyer, buyer_id)
    if buyer is None:
        return None
    contracts = db.execute(
        select(models.Contract.title, models.Contract.description, models.Contract.category_code,
               models.Contract.currency, models.Contract.amount_original, models.ContractTerritory.sector)
        .outerjoin(models.ContractTerritory, models.ContractTerritory.contract_id == models.Contract.id)
        .where(models.Contract.buyer_id == buyer.id)
    ).all()
    # Linked contracts already have a sector (with the UNSPSC fallback).
    rows = [(c, c.sector or classify_sector(c.title, c.description, c.category_code)) for c in contracts]
    shares = _sector_shares(rows)
    amounts = sorted(c.amount_original for c in contracts if c.amount_original)
    anomaly_n, flagged = _flagged(db, models.Contract.buyer_id == buyer.id)
    for f in flagged:
        f["buyer"] = None  # it's this institution on every row

    open_calls = [
        {"id": o.id, "title": o.title, "deadline": o.deadline, "url": o.url, "estimated_amount": o.estimated_amount,
         "currency": o.currency}
        for o in db.execute(
            select(models.Opportunity)
            .where(models.Opportunity.country_code == buyer.country_code, models.Opportunity.deadline > datetime.utcnow(),
                   func.lower(models.Opportunity.buyer_name) == buyer.name.lower())
            .order_by(models.Opportunity.deadline.asc())
            .limit(6)
        ).scalars()
    ]
    inquiries = db.execute(
        select(func.count()).select_from(models.Inquiry)
        .where(models.Inquiry.country_code == buyer.country_code,
               func.lower(models.Inquiry.institution).like(f"%{buyer.name.lower()[:120]}%"))
    ).scalar_one()
    # The place most of its contracts were linked to, for a link to its needs.
    place = db.execute(
        select(models.Territory.id, models.Territory.name, models.Territory.level, func.count().label("n"))
        .join(models.ContractTerritory, models.ContractTerritory.territory_id == models.Territory.id)
        .join(models.Contract, models.Contract.id == models.ContractTerritory.contract_id)
        .where(models.Contract.buyer_id == buyer.id)
        .group_by(models.Territory.id, models.Territory.name, models.Territory.level)
        .order_by(func.count().desc())
        .limit(1)
    ).first()

    return {
        "id": buyer.id,
        "name": buyer.name,
        "country_code": buyer.country_code,
        "local_government": _is_local_government(buyer.name),
        "territory": {"id": place.id, "name": place.name, "level": place.level} if place else None,
        "contracts": len(contracts),
        "median_amount": statistics.median(amounts) if len(amounts) >= 3 else None,
        "currency": Counter(c.currency for c in contracts).most_common(1)[0][0] if contracts else None,
        "spending": [{"sector": s, **v} for s, v in sorted(shares.items(), key=lambda kv: -kv[1]["contracts"])],
        "failures": {
            "anomalies": anomaly_n,
            "anomaly_rate": anomaly_n / len(contracts) if contracts else None,
            "national_anomaly_rate": _national_anomaly_rate(db, buyer.country_code),
            "flagged_contracts": flagged,
            "inquiries": inquiries,
        },
        "open_calls": open_calls,
    }
