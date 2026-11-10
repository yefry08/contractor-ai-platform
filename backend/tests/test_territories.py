from datetime import datetime, timedelta

from app import models
from app.territories import classify_sector, normalize_name, region_key
from scripts.ingest_territories import Build, link_contracts, local_name
from tests.conftest import make_buyer, make_contract, make_country


def add_territory(session, tid, level, name, parent_id=None, country="PY"):
    t = models.Territory(id=tid, country_code=country, level=level, code=tid.split("-")[-1], name=name,
                         normalized_name=normalize_name(name), parent_id=parent_id)
    session.add(t)
    session.flush()
    return t


def add_indicator(session, tid, key, sector, value, national, pct, year=2022, worse_when="high"):
    session.add(models.TerritoryIndicator(territory_id=tid, key=key, sector=sector, value=value,
                                          national_value=national, worse_when=worse_when, year=year,
                                          peer_percentile=pct, source="INE", source_url="https://www.ine.gov.py/"))


def link(session, contract, tid, dept_id, sector):
    session.add(models.ContractTerritory(contract_id=contract.id, territory_id=tid, department_id=dept_id,
                                         sector=sector, method="buyer_name"))


# --- classification and names ----------------------------------------------


def test_classify_sector_reads_words_then_unspsc():
    assert classify_sector("Construcción de alcantarillado sanitario") == "agua_saneamiento"
    assert classify_sector("ADQUISICION DE MEDICAMENTOS") == "salud"
    assert classify_sector("Pavimentación de calles del barrio") == "vias_transporte"
    # Words say nothing; SECOP's UNSPSC code does.
    assert classify_sector("Prestación de servicios de apoyo a la gestión", unspsc="V1.80111600") == "administracion"
    assert classify_sector("Contrato 45", unspsc="V1.85101500") == "salud"
    assert classify_sector("Compra de sillas plegables") == "otros"


def test_classify_sector_fills_gaps_after_needs_and_unspsc():
    # The needs sectors and the UNSPSC code still win over the generic ones.
    assert classify_sector("Mantenimiento de la red de alcantarillado") == "agua_saneamiento"
    assert classify_sector("Mantenimiento correctivo", unspsc="V1.85101500") == "salud"
    assert classify_sector("Mantenimiento de equipos de cómputo") == "tecnologia"
    assert classify_sector("COMPRA DIRECTA DIESEL") == "vehiculos_combustible"
    assert classify_sector("Servicio de limpieza de oficinas") == "mantenimiento_limpieza"
    assert classify_sector("LOSARTAN (COMPRIMIDO)") == "salud"
    # "aseo" inside "paseo" is not cleaning.
    assert classify_sector("Paseo cultural de fin de año") == "otros"


def test_classify_sector_says_when_there_is_no_description():
    assert classify_sector("R/214931520013") == "sin_detalle"
    assert classify_sector("CP-ABR-44-2026-GRA-SEDECENTRAL-1") == "sin_detalle"
    assert classify_sector("Contrato 45") == "sin_detalle"
    assert classify_sector("AE 132266. O FORNECEDOR SE VINCULA A SUA PROPOSTA E AO INSTRUMENTO "
                           "CONVOCATÓRIO E SEUS ANEXOS.") == "sin_detalle"


def test_place_names_normalize_across_spellings():
    assert normalize_name("BOGOTÁ, D.C.") == "bogota dc"
    assert region_key("Distrito Capital de Bogotá") == region_key("BOGOTÁ, D.C.")
    assert local_name("Gobierno Departamental de Misiones (MISIONES)") == "misiones"
    assert local_name("Municipalidad de Gral. Elizardo Aquino") == "general elizardo aquino"
    assert local_name("Municipalidad de la Paz") == "la paz"
    assert local_name("Ministerio de Salud") is None


def test_peer_percentile_is_share_of_peers_doing_better():
    b = Build("PY")
    for i, v in enumerate([10.0, 20.0, 30.0]):
        tid = b.territory("department", f"0{i}", f"D{i}")
        b.indicator(tid, "nbi_infra_sanitaria", "agua_saneamiento", v, 20.0, 2022, "INE", "u")
        b.indicator(tid, "edu_cobertura_neta", "educacion", v, 20.0, 2022, "MEN", "u", worse_when="low")
    b.rank_peers()
    pct = {(i["territory_id"], i["key"]): i["peer_percentile"] for i in b.indicators}
    assert pct[("PY-dep-02", "nbi_infra_sanitaria")] == 1.0  # highest share lacking sanitation: worst
    assert pct[("PY-dep-00", "nbi_infra_sanitaria")] == 0.0
    assert pct[("PY-dep-00", "edu_cobertura_neta")] == 1.0  # lowest coverage: worst


def test_contracts_link_by_local_government_name(db_session):
    make_country(db_session, "PY", "Paraguay")
    b = Build("PY")
    dep = b.territory("department", "07", "Itapúa")
    b.territory("municipality", "0701", "Encarnación", dep)
    b.territory("municipality", "0702", "Bella Vista", dep)
    other = b.territory("department", "13", "Amambay")
    b.territory("municipality", "1301", "Bella Vista", other)
    for name in ["Municipalidad de Encarnación", "Municipalidad de Bella Vista - Itapúa",
                 "Municipalidad de Bella Vista", "Gobierno Departamental de Itapua (ITAPÚA)", "Ministerio de Salud"]:
        make_contract(db_session, buyer_id=make_buyer(db_session, name=name).id, title="Almuerzo escolar")
    db_session.commit()

    links = {link["territory_id"] for link in link_contracts(db_session, b)}
    # The ambiguous "Bella Vista" (two departments have one) and the ministry stay unlinked.
    assert links == {"PY-mun-0701", "PY-mun-0702", "PY-dep-07"}


# --- API -------------------------------------------------------------------


def seed_itapua(session):
    make_country(session, "PY", "Paraguay")
    add_territory(session, "PY-dep-07", "department", "Itapúa")
    add_territory(session, "PY-mun-0701", "municipality", "Encarnación", "PY-dep-07")
    add_indicator(session, "PY-dep-07", "nbi_hogares_total", "pobreza", 30.0, 28.3, 0.5)
    add_indicator(session, "PY-dep-07", "nbi_infra_sanitaria", "agua_saneamiento", 18.0, 10.4, 0.9)
    add_indicator(session, "PY-dep-07", "nbi_acceso_educacion", "educacion", 9.0, 10.5, 0.2)
    buyer = make_buyer(session, name="Municipalidad de Encarnación")
    contracts = []
    for i in range(4):
        c = make_contract(session, buyer_id=buyer.id, title=f"Almuerzo escolar {i}", amount_original=1000.0 * (i + 1))
        link(session, c, "PY-mun-0701", "PY-dep-07", "educacion")
        contracts.append(c)
    # Two alerts on one contract count once.
    for score in (0.9, 0.8):
        session.add(models.Anomaly(contract_id=contracts[0].id, anomaly_type="overcost", composite_score=score))
    make_contract(session, title="Fuera de cualquier territorio")
    session.commit()
    return buyer


def test_territory_profile_ranks_gaps_and_shows_spending(client, db_session):
    seed_itapua(db_session)
    p = client.get("/territories/PY-dep-07").json()

    # The aggregate is shown but not ranked next to its own components.
    assert [x["key"] for x in p["priorities"]] == ["nbi_infra_sanitaria", "nbi_acceso_educacion"]
    top = p["priorities"][0]
    assert top["local_contract_share"] == 0.0  # no contract here goes to water and sanitation
    assert p["priorities"][1]["local_contract_share"] == 1.0
    assert p["spending"]["linked_contracts"] == 4
    assert p["failures"]["anomalies"] == 1
    assert p["failures"]["anomaly_rate"] == 0.25
    assert p["failures"]["national_anomaly_rate"] == 0.2  # 1 flagged of 5 PY contracts
    assert p["failures"]["flagged_contracts"][0]["buyer"] == "Municipalidad de Encarnación"
    assert len(p["failures"]["flagged_contracts"]) == 1

    muni = client.get("/territories/PY-mun-0701").json()
    assert muni["parent"]["id"] == "PY-dep-07"
    assert muni["spending"]["linked_contracts"] == 4
    assert client.get("/territories/PY-nope").status_code == 404


def test_territory_profile_reports_worsening_indicators(client, db_session):
    make_country(db_session, "CO", "Colombia")
    add_territory(db_session, "CO-mun-76001", "municipality", "CALI", country="CO")
    add_indicator(db_session, "CO-mun-76001", "edu_cobertura_neta", "educacion", 80.6, 88.0, None, 2023, "low")
    add_indicator(db_session, "CO-mun-76001", "edu_cobertura_neta", "educacion", 78.8, 88.2, 0.56, 2024, "low")
    db_session.commit()
    p = client.get("/territories/CO-mun-76001").json()
    assert [(w["previous_value"], w["value"]) for w in p["worsening"]] == [(80.6, 78.8)]
    assert p["indicators"][0]["year"] == 2024


def test_territory_profile_lists_open_calls_in_its_department(client, db_session):
    make_country(db_session, "CO", "Colombia")
    add_territory(db_session, "CO-dep-11", "department", "BOGOTÁ, D.C.", country="CO")
    for i, region in enumerate(["Distrito Capital de Bogotá", "Antioquia"]):
        db_session.add(models.Opportunity(country_code="CO", source="secop2", external_id=str(i), title=f"Llamado {i}",
                                          region=region, deadline=datetime.utcnow() + timedelta(days=3),
                                          url="https://community.secop.gov.co/Public/x"))
    db_session.commit()
    calls = client.get("/territories/CO-dep-11").json()["open_calls"]
    assert [c["title"] for c in calls] == ["Llamado 0"]


def test_territory_list_has_headline_and_links(client, db_session):
    seed_itapua(db_session)
    res = client.get("/territories", params={"country": "py", "level": "department"}).json()
    assert res["total"] == 1
    item = res["items"][0]
    assert item["headline"]["key"] == "nbi_hogares_total"
    assert item["linked_contracts"] == 4
    assert client.get("/territories", params={"country": "PY", "level": "planet"}).status_code == 422


def test_institutions_put_local_governments_first(client, db_session):
    buyer = seed_itapua(db_session)
    ministry = make_buyer(db_session, name="Ministerio de Obras Públicas")
    for i in range(6):
        make_contract(db_session, buyer_id=ministry.id, title=f"Construcción de puente {i}")
    make_buyer(db_session, name="Municipalidad Pequeña")  # no contracts: left out
    db_session.commit()

    items = client.get("/institutions", params={"country": "PY"}).json()["items"]
    assert [i["name"] for i in items] == ["Municipalidad de Encarnación", "Ministerio de Obras Públicas"]
    assert items[0]["anomaly_rate"] == 0.25

    p = client.get(f"/institutions/{buyer.id}").json()
    assert p["territory"]["id"] == "PY-mun-0701"
    assert p["spending"][0]["sector"] == "educacion"
    assert p["failures"]["anomalies"] == 1
    m = client.get(f"/institutions/{ministry.id}").json()
    assert m["spending"][0]["sector"] == "vias_transporte"
    assert client.get("/institutions/nope").status_code == 404
