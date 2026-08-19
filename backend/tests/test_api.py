from app import main
from tests.conftest import make_contract, make_country


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_countries_lists_seeded_country(client, db_session):
    make_country(db_session, code="PY", name="Paraguay")
    db_session.commit()
    res = client.get("/countries")
    assert res.status_code == 200
    assert any(c["code"] == "PY" for c in res.json())


def test_contracts_pagination_shape(client, db_session):
    make_country(db_session)
    for _ in range(3):
        make_contract(db_session)
    db_session.commit()

    res = client.get("/contracts?limit=2")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert len(body["items"]) == 2


def test_contract_detail_404_for_unknown_id(client):
    res = client.get("/contracts/does-not-exist")
    assert res.status_code == 404


def test_contract_detail_200_for_known_id(client, db_session):
    make_country(db_session)
    c = make_contract(db_session)
    db_session.commit()

    res = client.get(f"/contracts/{c.id}")
    assert res.status_code == 200
    assert res.json()["id"] == c.id


def test_analyze_compare_rejects_non_positive_amount(client, db_session):
    make_country(db_session)
    db_session.commit()
    res = client.post("/analyze/compare", json={"country": "PY", "currency": "PYG", "amount": 0})
    assert res.status_code == 400


def test_analyze_compare_rejects_unknown_country(client):
    res = client.post("/analyze/compare", json={"country": "ZZ", "currency": "USD", "amount": 100})
    assert res.status_code == 400


def test_analyze_compare_422_when_not_enough_reference_data(client, db_session):
    make_country(db_session)
    db_session.commit()
    res = client.post("/analyze/compare", json={"country": "PY", "currency": "PYG", "amount": 100})
    assert res.status_code == 422


# ---------- citizen reports ----------

def test_citizen_reports_404_for_unknown_contract(client):
    res = client.get("/contracts/does-not-exist/reports")
    assert res.status_code == 404


def test_citizen_report_create_and_list(client, db_session):
    make_country(db_session)
    c = make_contract(db_session)
    db_session.commit()

    create = client.post(f"/contracts/{c.id}/reports", json={"comment": "Esto parece un sobreprecio importante."})
    assert create.status_code == 201
    assert create.json()["stance"] == "flag"

    listed = client.get(f"/contracts/{c.id}/reports")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_citizen_report_rejects_too_short_comment(client, db_session):
    make_country(db_session)
    c = make_contract(db_session)
    db_session.commit()

    res = client.post(f"/contracts/{c.id}/reports", json={"comment": "no"})
    assert res.status_code == 422


def test_citizen_report_honeypot_is_silently_ignored(client, db_session):
    make_country(db_session)
    c = make_contract(db_session)
    db_session.commit()

    res = client.post(
        f"/contracts/{c.id}/reports",
        json={"comment": "Comentario de un bot spam.", "website": "http://spam.example"},
    )
    # Looks like success to whatever sent it...
    assert res.status_code == 201
    # ...but nothing was actually persisted.
    listed = client.get(f"/contracts/{c.id}/reports")
    assert listed.json() == []


def test_citizen_report_rate_limit(client, db_session, monkeypatch):
    make_country(db_session)
    c = make_contract(db_session)
    db_session.commit()

    monkeypatch.setattr(main, "MAX_REPORTS_PER_WINDOW", 2)

    codes = []
    for _ in range(3):
        res = client.post(f"/contracts/{c.id}/reports", json={"comment": "Comentario legitimo de prueba."})
        codes.append(res.status_code)

    assert codes == [201, 201, 429]


def test_dashboard_summary_reflects_seeded_contracts(client, db_session):
    make_country(db_session)
    for _ in range(5):
        make_contract(db_session)
    db_session.commit()

    res = client.get("/dashboard/summary?country=PY")
    assert res.status_code == 200
    assert res.json()["total_contracts"] == 5


def test_analyze_narrative_unavailable_without_key(client):
    res = client.post("/analyze/narrative", json={"text": "algún texto", "comparison_summary": "verdict: normal"})
    assert res.status_code == 200
    assert res.json() == {"available": False, "narrative": None}


def test_analyze_narrative_rate_limit(client, monkeypatch):
    from app import ai, main

    monkeypatch.setattr(ai.settings, "bazaarlink_api_key", "sk-bl-fake-test-key")
    monkeypatch.setattr(ai, "generate_narrative", lambda *a, **k: "Resumen de prueba.")
    monkeypatch.setattr(main, "MAX_NARRATIVE_PER_WINDOW", 2)

    codes = []
    for _ in range(3):
        res = client.post("/analyze/narrative", json={"text": "algún texto", "comparison_summary": "verdict: normal"})
        codes.append(res.status_code)

    assert codes == [200, 200, 429]


def test_tenders_portals_covers_all_countries(client):
    res = client.get("/tenders/portals")
    assert res.status_code == 200
    codes = {p["country_code"] for p in res.json()}
    assert codes == {"PY", "CO", "CR", "DO"}
    for p in res.json():
        assert p["portal_url"].startswith("https://")


def test_tenders_categories_reflects_seeded_data(client, db_session):
    from app.stats import MIN_GROUP_SIZE

    make_country(db_session)
    for _ in range(MIN_GROUP_SIZE):
        make_contract(db_session, category_code="servicios")
    db_session.commit()

    res = client.get("/tenders/categories?country=PY")
    assert res.status_code == 200
    assert res.json() == [{"category_code": "servicios", "contracts": MIN_GROUP_SIZE}]


def test_tenders_benchmark_422_when_not_enough_data(client, db_session):
    make_country(db_session)
    db_session.commit()
    res = client.get("/tenders/benchmark?country=PY&category=servicios")
    assert res.status_code == 422


def test_tenders_benchmark_200_with_enough_data(client, db_session):
    from app.stats import MIN_GROUP_SIZE

    make_country(db_session)
    for _ in range(MIN_GROUP_SIZE):
        make_contract(db_session, category_code="servicios", amount_original=1_000_000, currency="PYG")
    db_session.commit()

    res = client.get("/tenders/benchmark?country=PY&category=servicios")
    assert res.status_code == 200
    body = res.json()
    assert body["sample_size"] == MIN_GROUP_SIZE
    assert body["currency"] == "PYG"


def test_export_csv_headers(client, db_session):
    make_country(db_session)
    make_contract(db_session)
    db_session.commit()

    res = client.get("/export/contracts.csv")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
