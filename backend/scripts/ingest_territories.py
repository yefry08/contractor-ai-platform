"""Territorios: official needs indicators per territory, and which contracts
belong to which place. Sources (verified 2026-11-02):

  CO  DANE, Necesidades Básicas Insatisfechas, Censo 2018 (department and
      municipality sheets, "Total" columns).
      MEN, Estadísticas en educación básica por municipio (datos.gov.co
      nudc-7mev): net coverage and dropout, last two years. Department and
      national values are weighted by the 5-16 population the file gives.
  PY  INE, Hogares por Necesidades Básicas Insatisfechas 2022, by department
      and district.
  DO  ONE, Tasa de pobreza monetaria general y extrema por regiones de
      desarrollo (Decreto 710-04 regions), last two years.
  SV  none: no official needs indicator by municipality is published as data
      since the 2024 municipal reorganization. El Salvador gets the
      institution profile only.

Contracts are linked to a territory only when the data says where they are:
the department/city fields SECOP publishes (CO), or a local government's own
name ("Municipalidad de Encarnación", "Ayuntamiento Municipal de Baní")
matched to exactly one territory. Every linked contract gets a sector from
app.territories.classify_sector.

Everything is downloaded first and written in one short transaction (Neon
drops connections left idle inside a long one). Territory ids are stable, so
links to /territorios/<id> keep working across runs.

    cd backend
    python scripts/ingest_territories.py            # CO, PY, DO
    python scripts/ingest_territories.py PY
"""

import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl  # noqa: E402
from sqlalchemy import delete, insert, select  # noqa: E402

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.territories import classify_sector, normalize_name, region_key  # noqa: E402

HEADERS = {"User-Agent": "ContractorAI-ingest/1.0 (+https://github.com/yefry08/contractor-ai-platform)"}

CO_NBI_URL = "https://www.dane.gov.co/files/censo2018/informacion-tecnica/CNPV-2018-NBI.xlsx"
CO_NBI_SOURCE = "DANE, Censo Nacional de Población y Vivienda 2018 (NBI)"
CO_EDU_URL = "https://www.datos.gov.co/resource/nudc-7mev.json"
CO_EDU_PAGE = "https://www.datos.gov.co/d/nudc-7mev"
CO_EDU_SOURCE = "Ministerio de Educación Nacional, estadísticas por municipio"
PY_NBI_URL = (
    "https://www.ine.gov.py/Publicaciones/Biblioteca/documento/262/"
    "Paraguay.Hogares_por_Necesidades_Basicas_Insatisfechas(NBI).xlsx"
)
PY_NBI_SOURCE = "INE Paraguay, Hogares por NBI 2022"
DO_POV_URL = (
    "https://descargas.one.gob.do/download/OGTIC/"
    "Tasa_de_Pobreza_Monetaria_General_y_Extrema_por_Regiones_de_Desarrollo,_2000-2024.csv"
)
DO_POV_SOURCE = "ONE, pobreza monetaria por región de desarrollo"

# DANE "Total" columns, in sheet order after the codes and names.
CO_NBI_COLUMNS = [
    ("nbi_total", "pobreza"),
    ("nbi_miseria", "pobreza"),
    ("nbi_vivienda", "vivienda"),
    ("nbi_servicios", "agua_saneamiento"),
    ("nbi_hacinamiento", "vivienda"),
    ("nbi_inasistencia", "educacion"),
    ("nbi_dependencia", "empleo"),
]
PY_NBI_COLUMNS = [
    ("nbi_hogares_total", "pobreza"),
    ("nbi_calidad_vivienda", "vivienda"),
    ("nbi_infra_sanitaria", "agua_saneamiento"),
    ("nbi_acceso_educacion", "educacion"),
    ("nbi_subsistencia", "empleo"),
]

# Decreto 710-04: development regions -> provinces, and each province's
# capital (the name its ayuntamiento goes by).
DO_REGIONS = {
    "Cibao Norte": {"Santiago": "Santiago", "Puerto Plata": "Puerto Plata", "Espaillat": "Moca"},
    "Cibao Sur": {"La Vega": "La Vega", "Monseñor Nouel": "Bonao", "Sánchez Ramírez": "Cotuí"},
    "Cibao Nordeste": {"Duarte": "San Francisco de Macorís", "María Trinidad Sánchez": "Nagua",
                       "Hermanas Mirabal": "Salcedo", "Samaná": "Samaná"},
    "Cibao Noroeste": {"Valverde": "Mao", "Monte Cristi": "Monte Cristi", "Dajabón": "Dajabón",
                       "Santiago Rodríguez": "San Ignacio de Sabaneta"},
    "Valdesia": {"San Cristóbal": "San Cristóbal", "Peravia": "Baní", "San José de Ocoa": "San José de Ocoa",
                 "Azua": "Azua"},
    "Enriquillo": {"Barahona": "Barahona", "Bahoruco": "Neiba", "Independencia": "Jimaní", "Pedernales": "Pedernales"},
    "El Valle": {"San Juan": "San Juan de la Maguana", "Elías Piña": "Comendador"},
    "Yuma": {"La Romana": "La Romana", "La Altagracia": "Higüey", "El Seibo": "El Seibo"},
    "Higuamo": {"San Pedro de Macorís": "San Pedro de Macorís", "Hato Mayor": "Hato Mayor", "Monte Plata": "Monte Plata"},
    "Ozama o Metropolitana": {"Distrito Nacional": "Distrito Nacional", "Santo Domingo": "Santo Domingo Este"},
}

# SECOP's city names against DANE's (department spellings: REGION_ALIASES).
CO_CITY_ALIASES = {"bogota": "bogota dc", "cucuta": "san jose de cucuta", "cartagena": "cartagena de indias",
                   "santa fe de antioquia": "santa fe de antioquia", "tumaco": "san andres de tumaco",
                   "mompos": "santa cruz de mompox", "san vicente": "san vicente ferrer"}

# Municipalities that aren't a province capital but buy under their own
# ayuntamiento, with their region.
DO_OTHER_MUNICIPALITIES = {
    "Santo Domingo Norte": "Ozama o Metropolitana", "Santo Domingo Oeste": "Ozama o Metropolitana",
    "Boca Chica": "Ozama o Metropolitana", "Los Alcarrizos": "Ozama o Metropolitana",
    "Pedro Brand": "Ozama o Metropolitana", "San Antonio de Guerra": "Ozama o Metropolitana",
    "Santiago de los Caballeros": "Cibao Norte", "Tamboril": "Cibao Norte", "Villa González": "Cibao Norte",
    "Puñal": "Cibao Norte", "Licey al Medio": "Cibao Norte", "Imbert": "Cibao Norte", "Sosúa": "Cibao Norte",
    "Tenares": "Cibao Nordeste", "Sabana Grande de Palenque": "Valdesia", "Bajos de Haina": "Valdesia",
}

LOCAL_NAME = re.compile(
    r"^(?:municipalidad|alcald[ií]a(?: municipal)?|ayuntamiento(?: del municipio| municipal)?|"
    r"gobernaci[oó]n(?: del departamento)?|gobierno departamental)\s+(?:de\s+|del\s+)?(.+)$",
    re.IGNORECASE,
)
ABBREVIATIONS = {"gral": "general", "mcal": "mariscal", "tte": "teniente", "dr": "doctor", "pte": "presidente",
                 "cnel": "coronel", "sta": "santa", "sto": "santo", "cap": "capitan"}


def place_key(name: str | None) -> str:
    """normalize_name plus the abbreviations local governments use in their
    own names ("Gral. Elizardo Aquino" -> "general elizardo aquino")."""
    return " ".join(ABBREVIATIONS.get(w, w) for w in normalize_name(name).split())


def get(url: str, retries: int = 4) -> bytes:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            print(f"  retry {attempt + 1} after {type(exc).__name__}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def num(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


CONNECTORS = {"de", "del", "la", "las", "los", "el", "y", "e"}


def place_case(name: str) -> str:
    """DANE writes names in capitals: "SAN JOSÉ DE CÚCUTA" -> "San José de
    Cúcuta". Abbreviations and parenthesised tags stay as they are."""
    words = []
    for i, w in enumerate(name.split()):
        if w.startswith("(") or "." in w:
            words.append(w)
        elif i > 0 and w.lower() in CONNECTORS:
            words.append(w.lower())
        else:
            words.append(w[:1] + w[1:].lower())
    return " ".join(words)


def sheet_rows(content: bytes, sheet: str | None = None):
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    return list(ws.iter_rows(values_only=True))


class Build:
    """Territories and indicators for one country, before anything is written."""

    def __init__(self, country: str):
        self.country = country
        self.territories: dict[str, dict] = {}
        self.indicators: list[dict] = []

    def territory(self, level: str, code: str, name: str, parent_id: str | None = None) -> str:
        prefix = {"department": "dep", "municipality": "mun", "region": "reg"}[level]
        tid = f"{self.country}-{prefix}-{code}"
        self.territories[tid] = {
            "id": tid, "country_code": self.country, "level": level, "code": code,
            "name": name, "normalized_name": normalize_name(name), "parent_id": parent_id,
        }
        return tid

    def indicator(self, tid, key, sector, value, national, year, source, url, worse_when="high"):
        if value is None:
            return
        self.indicators.append({
            "territory_id": tid, "key": key, "sector": sector, "value": round(value, 2),
            "national_value": round(national, 2) if national is not None else None, "unit": "%",
            "worse_when": worse_when, "year": year, "source": source, "source_url": url,
        })

    def rank_peers(self):
        """peer_percentile on each territory's latest value: the share of
        same-level territories doing better (1 = worst in the country)."""
        latest_year = defaultdict(int)
        for ind in self.indicators:
            latest_year[ind["key"]] = max(latest_year[ind["key"]], ind["year"])
        groups = defaultdict(list)
        for ind in self.indicators:
            if ind["year"] == latest_year[ind["key"]]:
                level = self.territories[ind["territory_id"]]["level"]
                groups[(level, ind["key"])].append(ind)
        for group in groups.values():
            if len(group) < 2:
                continue
            for ind in group:
                if ind["worse_when"] == "high":
                    better = sum(1 for o in group if o["value"] < ind["value"])
                else:
                    better = sum(1 for o in group if o["value"] > ind["value"])
                ind["peer_percentile"] = round(better / (len(group) - 1), 4)


def build_co() -> Build:
    b = Build("CO")
    nbi = get(CO_NBI_URL)
    national: dict[str, float] = {}
    dept_values: dict[str, list] = {}
    for row in sheet_rows(nbi, "Departamento"):
        code, name = row[0], row[1]
        if not isinstance(code, str) or not code.strip().isdigit():
            continue
        values = [num(v) for v in row[2:2 + len(CO_NBI_COLUMNS)]]
        if code == "00":
            national = {k: v for (k, _), v in zip(CO_NBI_COLUMNS, values)}
            continue
        b.territory("department", code, place_case(name.strip()))
        dept_values[code] = values
    for code, values in dept_values.items():
        for (key, sector), v in zip(CO_NBI_COLUMNS, values):
            b.indicator(f"CO-dep-{code}", key, sector, v, national.get(key), 2018, CO_NBI_SOURCE, CO_NBI_URL)
    for row in sheet_rows(nbi, "Municipios"):
        dep, _dep_name, mun, name = row[:4]
        # The sheet ends with a "TOTAL NACIONAL" row under department 00.
        if not isinstance(dep, str) or f"CO-dep-{dep}" not in b.territories or not mun:
            continue
        code = f"{dep}{mun}"
        tid = b.territory("municipality", code, place_case(str(name).strip()), f"CO-dep-{dep}")
        for (key, sector), v in zip(CO_NBI_COLUMNS, row[4:4 + len(CO_NBI_COLUMNS)]):
            b.indicator(tid, key, sector, num(v), national.get(key), 2018, CO_NBI_SOURCE, CO_NBI_URL)

    years = [r["a_o"] for r in json.loads(get(f"{CO_EDU_URL}?$select=a_o&$group=a_o&$order=a_o DESC&$limit=2"
                                              .replace(" ", "%20")))]
    for year in years:
        query = urllib.parse.urlencode({
            "$select": "c_digo_municipio,c_digo_departamento,poblaci_n_5_16,tasa_matriculaci_n_5_16,cobertura_neta,deserci_n",
            "$where": f"a_o='{year}'", "$limit": 5000,
        })
        rows = json.loads(get(f"{CO_EDU_URL}?{query}"))
        weights = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])  # pop, pop*cov, enrol, enrol*dropout
        for r in rows:
            tid = f"CO-mun-{r.get('c_digo_municipio')}"
            pop, cov, rate, drop = (num(r.get(k)) for k in
                                    ("poblaci_n_5_16", "cobertura_neta", "tasa_matriculaci_n_5_16", "deserci_n"))
            r["_tid"], r["_cov"], r["_drop"] = tid, cov, drop
            if not pop or cov is None:
                continue
            enrol = pop * (rate or 0) / 100
            for scope in (r.get("c_digo_departamento"), "00"):
                w = weights[scope]
                w[0] += pop
                w[1] += pop * cov
                if drop is not None:
                    w[2] += enrol
                    w[3] += enrol * drop

        def avg(scope):
            w = weights.get(scope)
            if not w or not w[0]:
                return None, None
            return w[1] / w[0], (w[3] / w[2] if w[2] else None)

        nat_cov, nat_drop = avg("00")
        y = int(year)
        for r in rows:
            if r["_tid"] in b.territories:
                b.indicator(r["_tid"], "edu_cobertura_neta", "educacion", r["_cov"], nat_cov, y, CO_EDU_SOURCE,
                            CO_EDU_PAGE, worse_when="low")
                b.indicator(r["_tid"], "edu_desercion", "educacion", r["_drop"], nat_drop, y, CO_EDU_SOURCE, CO_EDU_PAGE)
        for code in dept_values:
            cov, drop = avg(code)
            b.indicator(f"CO-dep-{code}", "edu_cobertura_neta", "educacion", cov, nat_cov, y, CO_EDU_SOURCE,
                        CO_EDU_PAGE, worse_when="low")
            b.indicator(f"CO-dep-{code}", "edu_desercion", "educacion", drop, nat_drop, y, CO_EDU_SOURCE, CO_EDU_PAGE)
    b.rank_peers()
    return b


# Typos in the INE table, fixed so names match how the department writes itself.
PY_SPELLING = {"Itapuá": "Itapúa"}


def build_py() -> Build:
    b = Build("PY")
    rows = sheet_rows(get(PY_NBI_URL))
    national: dict[str, float] = {}
    dept_id, dept_n, dist_n = None, -1, 0
    for row in rows:
        name, values = row[1], row[3:3 + len(PY_NBI_COLUMNS)]
        if not isinstance(name, str) or num(values[0]) is None:
            continue
        name = name.strip()
        values = [num(v) for v in values]
        if name.lower().startswith("total pa"):
            national = {k: v for (k, _), v in zip(PY_NBI_COLUMNS, values)}
            continue
        if name == "Asunción" and dept_id is None:
            # The capital district stands alone, at department level.
            dept_n += 1
            tid = b.territory("department", f"{dept_n:02d}", "Asunción")
        elif name.startswith("Departamento "):
            dept_n += 1
            dist_n = 0
            dept = name.removeprefix("Departamento ").strip()
            dept = PY_SPELLING.get(dept, dept)
            dept_id = tid = b.territory("department", f"{dept_n:02d}", dept)
        elif dept_id:
            dist_n += 1
            tid = b.territory("municipality", f"{dept_n:02d}{dist_n:02d}", name, dept_id)
        else:
            continue
        for (key, sector), v in zip(PY_NBI_COLUMNS, values):
            b.indicator(tid, key, sector, v, national.get(key), 2022, PY_NBI_SOURCE, PY_NBI_URL)
    b.rank_peers()
    return b


def build_do() -> Build:
    b = Build("DO")
    text = get(DO_POV_URL).decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))[1:]
    years = sorted({int(r[3]) for r in rows if len(r) >= 4 and r[3].strip().isdigit()})[-2:]
    ids = {}
    for i, region in enumerate(DO_REGIONS, start=1):
        ids[normalize_name(region)] = b.territory("region", f"{i:02d}", region)
    for kind, region, value, year in (r[:4] for r in rows if len(r) >= 4):
        if not year.strip().isdigit() or int(year) not in years:
            continue
        tid = ids.get(normalize_name(region))
        key = "pobreza_extrema" if "extrema" in kind.lower() else "pobreza_general"
        if tid:
            # ONE publishes no national figure in this file; the page shows
            # the region against the other nine instead.
            b.indicator(tid, key, "pobreza", num(value), None, int(year), DO_POV_SOURCE, DO_POV_URL)
    b.rank_peers()
    return b


BUILDERS = {"CO": build_co, "PY": build_py, "DO": build_do}


# ---------------------------------------------------------------------------
# Contract -> territory
# ---------------------------------------------------------------------------


def local_name(buyer: str | None) -> str | None:
    # "Gobierno Departamental de Misiones (MISIONES)": the tag repeats the name.
    m = LOCAL_NAME.match(re.sub(r"\s*\([^)]*\)\s*$", "", (buyer or "").strip()))
    return place_key(m.group(1)) if m else None


def link_contracts(db, b: Build) -> list[dict]:
    depts = {place_key(t["name"]): t["id"] for t in b.territories.values() if t["level"] in ("department", "region")}
    munis_by_dept = defaultdict(dict)
    for t in b.territories.values():
        if t["level"] == "municipality":
            munis_by_dept[t["parent_id"]][place_key(t["name"])] = t

    def find_muni(local: str, within: list[str]) -> list[dict]:
        """Exact name first; else names that end with it ("Juan Eulogio
        Estigarribia" for "Dr. Juan Eulogio Estigarribia")."""
        pools = [munis_by_dept[d] for d in within]
        exact = [m[local] for m in pools if local in m]
        if exact:
            return exact
        return [t for m in pools for k, t in m.items() if k.endswith(" " + local)]

    do_places = {}
    if b.country == "DO":
        for region, provinces in DO_REGIONS.items():
            rid = depts[place_key(region)]
            for province, capital in provinces.items():
                do_places[place_key(capital)] = rid
                do_places.setdefault(place_key(province), rid)
        for muni, region in DO_OTHER_MUNICIPALITIES.items():
            do_places[place_key(muni)] = depts[place_key(region)]

    def place_from_buyer(name):
        local = local_name(name)
        if not local:
            return None
        if b.country == "DO":
            local = re.sub(r"^(santo domingo de guzman|distrito nacional).*", "distrito nacional", local)
            rid = do_places.get(local)
            return (rid, rid) if rid else None
        if local in depts and (name or "").lower().startswith(("gobern", "gobierno")):
            return depts[local], depts[local]
        within = list(munis_by_dept)
        # "Bella Vista - Itapúa", "Santa Rosa Misiones": the department settles
        # which of two same-named districts it is.
        for dept_name, dept_id in depts.items():
            if local.endswith(" " + dept_name):
                local, within = local[: -len(dept_name) - 1].strip(), [dept_id]
                break
        hits = find_muni(local, within)
        if len(hits) == 1:
            return hits[0]["id"], hits[0]["parent_id"]
        if local in depts:  # Asunción, Bogotá: capital districts kept at department level
            return depts[local], depts[local]
        return None

    links = []
    stmt = (
        select(models.Contract.id, models.Contract.title, models.Contract.description, models.Contract.category_code,
               models.Contract.raw_ocds_json, models.Buyer.name)
        .outerjoin(models.Buyer, models.Buyer.id == models.Contract.buyer_id)
        .where(models.Contract.country_code == b.country)
    )
    for cid, title, desc, cat, raw, buyer in db.execute(stmt):
        place, method = None, None
        raw = raw if isinstance(raw, dict) else {}
        if b.country == "CO" and raw.get("departamento"):
            dep_id = depts.get(region_key(raw["departamento"]))
            if dep_id:
                city = place_key(raw.get("ciudad"))
                city = CO_CITY_ALIASES.get(city, city)
                hits = find_muni(city, [dep_id]) if city else []
                # "No Definido" or an unknown city: the department is still known.
                place = (hits[0]["id"] if len(hits) == 1 else dep_id, dep_id)
                method = "portal_fields"
        if place is None:
            place = place_from_buyer(buyer)
            method = "buyer_name" if place else None
        if place:
            links.append({
                "contract_id": cid, "territory_id": place[0], "department_id": place[1],
                "sector": classify_sector(title, desc, cat, unspsc=raw.get("codigo_de_categoria_principal")),
                "method": method,
            })
    return links


def main():
    parser = argparse.ArgumentParser(description="Indicadores territoriales y vínculo contrato-territorio.")
    parser.add_argument("countries", nargs="*", default=list(BUILDERS))
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    for code in args.countries:
        try:
            b = BUILDERS[code]()
        except Exception as exc:  # noqa: BLE001
            # One office's file failing must not stop the others.
            print(f"[{code}] descarga fallida: {type(exc).__name__}: {exc}"[:500], file=sys.stderr)
            continue
        with SessionLocal() as db:
            links = link_contracts(db, b)
        with SessionLocal() as db:
            ids = select(models.Territory.id).where(models.Territory.country_code == code)
            db.execute(delete(models.ContractTerritory).where(models.ContractTerritory.territory_id.in_(ids)))
            db.execute(delete(models.TerritoryIndicator).where(models.TerritoryIndicator.territory_id.in_(ids)))
            db.execute(delete(models.Territory).where(models.Territory.country_code == code,
                                                      models.Territory.parent_id.isnot(None)))
            db.execute(delete(models.Territory).where(models.Territory.country_code == code))
            parents = [t for t in b.territories.values() if not t["parent_id"]]
            children = [t for t in b.territories.values() if t["parent_id"]]
            for batch in (parents, children):
                if batch:
                    db.execute(insert(models.Territory), batch)
            if b.indicators:
                rows = [{"id": str(uuid.uuid4()), "peer_percentile": None, **i} for i in b.indicators]
                db.execute(insert(models.TerritoryIndicator), rows)
            if links:
                db.execute(insert(models.ContractTerritory), links)
            db.commit()
        by_method = defaultdict(int)
        for link in links:
            by_method[link["method"]] += 1
        print(f"[{code}] territorios={len(b.territories)} indicadores={len(b.indicators)} "
              f"contratos_vinculados={len(links)} {dict(by_method)}")


if __name__ == "__main__":
    main()
