from datetime import date

from app import main
from tests.conftest import make_buyer, make_contract, make_country


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


# ---------- negative/zero limit: was an unhandled 500, now a clean 422 ----------
# GET /contracts?limit=-1 reproduced this live against production (see the
# session's security pass): `limit` fed straight into SQLAlchemy's .limit(),
# and Postgres/SQLite both reject a negative LIMIT at the SQL level, which
# surfaced as a bare, unhandled 500 to an unauthenticated caller. `offset` on
# these same endpoints already had `ge=0`; `limit` was simply missed on every
# endpoint that has one. FastAPI's `ge=1` now rejects it before it reaches the
# database at all.


def test_contracts_rejects_negative_limit(client):
    res = client.get("/contracts?limit=-1")
    assert res.status_code == 422


def test_anomalies_rejects_negative_limit(client):
    res = client.get("/anomalies?limit=-1")
    assert res.status_code == 422


def test_rankings_buyers_rejects_negative_limit(client):
    res = client.get("/rankings/buyers?limit=-1")
    assert res.status_code == 422


def test_export_csv_rejects_negative_limit(client):
    res = client.get("/export/contracts.csv?limit=-1")
    assert res.status_code == 422


def test_providers_top_rejects_negative_limit(client):
    res = client.get("/providers/top?limit=-1")
    assert res.status_code == 422


def test_providers_price_favoritism_rejects_year_out_of_range(client):
    res = client.get("/providers/price-favoritism?start_year=1500")
    assert res.status_code == 422


# ---------- /providers/* : no endpoint-level coverage existed before this ----------
# app/providers.py's own functions are covered in test_providers.py; these
# confirm the FastAPI layer around them -- routing, param parsing, and
# response-model serialization -- actually works end to end, which is exactly
# where get_temporal_patterns's ArgumentError (see test_providers.py) would
# have surfaced if this test had existed before that bug was introduced.


def test_providers_stats_shape(client, db_session):
    make_country(db_session)
    buyer = make_buyer(db_session)
    make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0)
    db_session.commit()

    res = client.get("/providers/stats")
    assert res.status_code == 200
    body = res.json()
    assert body["total_providers"] == 1
    assert body["hhi_concentration"] == 10000.0


def test_providers_top_shape(client, db_session):
    make_country(db_session)
    buyer = make_buyer(db_session)
    for _ in range(2):
        make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0)
    db_session.commit()

    res = client.get("/providers/top")
    assert res.status_code == 200
    body = res.json()
    assert body[0]["provider_name"] == buyer.name


def test_providers_price_favoritism_empty_is_200_not_500(client, db_session):
    make_country(db_session)
    db_session.commit()
    res = client.get("/providers/price-favoritism")
    assert res.status_code == 200
    assert res.json() == []


def test_providers_geographic_empty_is_200_not_500(client, db_session):
    make_country(db_session)
    db_session.commit()
    res = client.get("/providers/geographic")
    assert res.status_code == 200
    assert res.json() == []


def test_providers_temporal_patterns_endpoint_does_not_500(client, db_session):
    """Regression test for the joinedload/ArgumentError bug fixed in
    app/providers.py -- this specific request shape (a buyer with 3+ contracts
    in the same month, hit through the real HTTP layer rather than calling the
    function directly) is what would have caught it before deploy."""
    make_country(db_session)
    buyer = make_buyer(db_session)
    for day in (1, 10, 20):
        make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0, award_date=date(2024, 5, day))
    db_session.commit()

    res = client.get("/providers/temporal-patterns")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 3
    assert body[0]["consecutive_awards"] == 3
