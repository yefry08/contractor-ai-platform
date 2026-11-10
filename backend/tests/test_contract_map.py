import pytest

from app import models
from app.contract_map import contract_map
from tests.conftest import make_buyer, make_contract, make_country


def build(session):
    make_country(session, "PY", "Paraguay")
    make_country(session, "CO", "Colombia")
    hospital = make_buyer(session, "PY", "Hospital Regional de Encarnación")
    school = make_buyer(session, "PY", "Escuela Básica 123")
    city = make_buyer(session, "CO", "Alcaldía de Ibagué")
    contracts = []
    for i in range(3):
        c = make_contract(session, buyer_id=hospital.id, title=f"Medicamentos lote {i}")  # 1,000,000 PYG each
        session.add(models.ContractSector(contract_id=c.id, sector="salud"))
        contracts.append(c)
    session.add(models.Anomaly(contract_id=contracts[0].id, anomaly_type="overcost", status="open"))
    # A second, dismissed alert on another contract must not count.
    session.add(models.Anomaly(contract_id=contracts[1].id, anomaly_type="overcost", status="dismissed"))
    # Loaded after the last classification run: no contract_sectors row.
    make_contract(session, buyer_id=school.id, amount_original=50_000_000.0, title="Útiles escolares para el aula")
    # A contract in dollars is not added to guaraníes.
    make_contract(session, buyer_id=school.id, currency="USD", amount_original=900.0, title="Útiles escolares")
    for _ in range(2):
        c = make_contract(session, country_code="CO", currency="COP", buyer_id=city.id, title="Pavimentación de calles")
        session.add(models.ContractSector(contract_id=c.id, sector="vias_transporte"))
    make_contract(session, title="Sin comprador")  # counts in the totals, not on the map
    session.flush()
    return hospital, school, city


def test_all_countries_share_the_institutions(db_session):
    hospital, school, city = build(db_session)
    m = contract_map(db_session, None, False, "contracts", 2)
    # No country, no currency: amounts are not summed across currencies.
    assert m["currency"] is None
    assert m["total"] == {"contracts": 8, "value": 0.0, "flagged": 1}
    # One institution per country, so Colombia shows up next to Paraguay.
    assert [b["id"] for b in m["buyers"]] == [hospital.id, city.id]
    assert m["shown"]["contracts"] == 5
    assert {c["code"]: c["contracts"] for c in m["countries"]} == {"PY": 6, "CO": 2}
    assert m["buyers"][0]["name"] == "Hospital Regional de Encarnación"
    assert m["buyers"][0]["main_sector"] == "salud"
    assert m["buyers"][0]["flagged"] == 1


def test_value_metric_and_unclassified_contracts(db_session):
    hospital, school, city = build(db_session)
    m = contract_map(db_session, "PY", False, "value", 5)
    assert m["metric"] == "value"
    assert m["currency"] == "PYG"
    assert [b["id"] for b in m["buyers"]] == [school.id, hospital.id]
    links = {(lk["buyer_id"], lk["sector"]): lk for lk in m["links"]}
    # Classified on the fly from their titles; the dollar contract adds nothing.
    assert links[(school.id, "educacion")]["value"] == 50_000_000.0
    assert links[(school.id, "educacion")]["contracts"] == 2
    assert links[(hospital.id, "salud")] == {"buyer_id": hospital.id, "sector": "salud", "contracts": 3,
                                              "value": 3_000_000.0, "flagged": 1}
    assert {s["key"] for s in m["sectors"]} == {"salud", "educacion"}


def test_value_needs_a_country(db_session):
    with pytest.raises(ValueError):
        contract_map(db_session, None, False, "value", 5)


def test_only_flagged_contracts(db_session):
    hospital, _, _ = build(db_session)
    m = contract_map(db_session, None, True, "contracts", 10)
    assert m["total"]["contracts"] == 1
    assert [b["id"] for b in m["buyers"]] == [hospital.id]


def test_same_institution_twice_is_one_node(db_session):
    make_country(db_session, "CR", "Costa Rica")
    first = make_buyer(db_session, "CR", "CAJA COSTARRICENSE DE SEGURO SOCIAL")
    second = make_buyer(db_session, "CR", "Caja Costarricense de Seguro Social")
    for buyer, n in ((first, 1), (second, 2)):
        for _ in range(n):
            make_contract(db_session, country_code="CR", currency="CRC", buyer_id=buyer.id, title="Medicamentos")
    m = contract_map(db_session, "CR", False, "contracts", 5)
    assert len(m["buyers"]) == 1
    # The registration with most contracts is the one the institution page opens.
    assert m["buyers"][0]["id"] == second.id
    assert m["buyers"][0]["contracts"] == 3
    assert m["links"] == [{"buyer_id": second.id, "sector": "salud", "contracts": 3, "value": 3_000_000.0,
                           "flagged": 0}]


def test_value_metric_leaves_out_institutions_without_amounts(db_session):
    _, _, city = build(db_session)
    no_amounts = make_buyer(db_session, "CO", "Gobernación del Tolima")
    make_contract(db_session, country_code="CO", currency="COP", amount_original=None, buyer_id=no_amounts.id,
                  title="Obra civil")
    m = contract_map(db_session, "CO", False, "value", 5)
    assert [b["id"] for b in m["buyers"]] == [city.id]


def test_graph_endpoint_validates_and_answers(client, db_session):
    build(db_session)
    db_session.commit()
    assert client.get("/graph/contracts?metric=amount").status_code == 422
    assert client.get("/graph/contracts?metric=value").status_code == 422
    r = client.get("/graph/contracts?country=co&limit=5")
    assert r.status_code == 200
    assert r.json()["total"]["contracts"] == 2
