from datetime import datetime, timedelta

from starlette.requests import Request

from app import models, security
from app.config import settings
from tests.conftest import make_buyer, make_contract, make_country


def make_opportunity(session, **overrides):
    defaults = dict(
        country_code="CO",
        source="secop2",
        external_id="CO1.REQ.1",
        title="Suministro de papelería",
        buyer_name="Alcaldía de Prueba",
        currency="COP",
        estimated_amount=50_000_000.0,
        deadline=datetime.utcnow() + timedelta(days=5),
        url="https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.1",
    )
    defaults.update(overrides)
    o = models.Opportunity(**defaults)
    session.add(o)
    session.flush()
    return o


def inquiry(**overrides):
    body = dict(
        kind="reclamo",
        country_code="CO",
        subject="Pliego hecho a la medida",
        body="Los requisitos de experiencia solo los cumple un proveedor de la zona.",
    )
    body.update(overrides)
    return body


# --- opportunities ---------------------------------------------------------


def test_opportunities_hide_closed_calls_and_sort_by_deadline(client, db_session):
    make_country(db_session, "CO", "Colombia")
    make_opportunity(db_session, external_id="late", deadline=datetime.utcnow() + timedelta(days=20))
    make_opportunity(db_session, external_id="soon", deadline=datetime.utcnow() + timedelta(days=1))
    make_opportunity(db_session, external_id="closed", deadline=datetime.utcnow() - timedelta(days=1))
    db_session.commit()

    res = client.get("/opportunities").json()
    assert res["total"] == 2
    assert res["items"][0]["deadline"] < res["items"][1]["deadline"]
    assert res["counts_by_country"] == {"CO": 2}


def test_opportunities_filters(client, db_session):
    make_country(db_session, "CO", "Colombia")
    make_country(db_session, "DO", "República Dominicana")
    make_opportunity(db_session, external_id="a", title="Compra de computadoras")
    make_opportunity(db_session, external_id="b", country_code="DO", for_smes=True, title="Uniformes escolares")
    make_opportunity(db_session, external_id="c", deadline=datetime.utcnow() + timedelta(days=40))
    db_session.commit()

    assert client.get("/opportunities", params={"country": "DO"}).json()["total"] == 1
    assert client.get("/opportunities", params={"q": "COMPUTADORAS"}).json()["total"] == 1
    assert client.get("/opportunities", params={"for_smes": True}).json()["total"] == 1
    assert client.get("/opportunities", params={"closing_within_days": 7}).json()["total"] == 2


def test_opportunity_carries_the_buyers_history(client, db_session):
    make_country(db_session, "CO", "Colombia")
    buyer = make_buyer(db_session, country_code="CO", name="Alcaldía de Prueba")
    contracts = [
        make_contract(db_session, country_code="CO", currency="COP", buyer_id=buyer.id, amount_original=float(i * 1000))
        for i in range(1, 11)
    ]
    db_session.add(models.Anomaly(contract_id=contracts[0].id, anomaly_type="overcost", status="open"))
    make_opportunity(db_session, buyer_name="  ALCALDÍA de Prueba ")
    db_session.commit()

    history = client.get("/opportunities").json()["items"][0]["buyer_history"]
    assert history["contracts"] == 10
    assert history["median_amount"] == 5500.0
    assert history["currency"] == "COP"
    assert history["anomaly_rate"] == 0.1


def test_small_buyer_history_has_no_rate(client, db_session):
    make_country(db_session, "CO", "Colombia")
    buyer = make_buyer(db_session, country_code="CO", name="Alcaldía de Prueba")
    c = make_contract(db_session, country_code="CO", currency="COP", buyer_id=buyer.id)
    db_session.add(models.Anomaly(contract_id=c.id, anomaly_type="overcost", status="open"))
    make_opportunity(db_session)
    db_session.commit()

    history = client.get("/opportunities").json()["items"][0]["buyer_history"]
    assert history["contracts"] == 1
    assert history["anomaly_rate"] is None and history["median_amount"] is None


# --- inquiries -------------------------------------------------------------


def test_inquiry_gets_a_code_and_the_official_channels(client, db_session):
    res = client.post("/inquiries", json=inquiry())
    assert res.status_code == 201
    receipt = res.json()
    assert receipt["code"].startswith("CAI-") and len(receipt["code"]) == 12
    assert [c["role"] for c in receipt["channels"]] == ["procurement", "oversight"]

    status = client.get(f"/inquiries/{receipt['code'].lower()}").json()
    assert status["status"] == "recibido"
    assert "body" not in status and "contact_email" not in status  # the text is never public


def test_inquiry_validation(client):
    assert client.post("/inquiries", json=inquiry(kind="insulto")).status_code == 422
    assert client.post("/inquiries", json=inquiry(body="corto")).status_code == 422
    assert client.post("/inquiries", json=inquiry(contact_email="no-es-un-correo")).status_code == 422
    assert client.post("/inquiries", json=inquiry(country_code="MX")).status_code == 422


def test_inquiry_honeypot_stores_nothing(client, db_session):
    res = client.post("/inquiries", json=inquiry(website="http://spam.example"))
    assert res.status_code == 201
    assert db_session.query(models.Inquiry).count() == 0


def test_inquiry_rate_limit(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "MAX_INQUIRIES_PER_WINDOW", 2)
    codes = [client.post("/inquiries", json=inquiry()).status_code for _ in range(3)]
    assert codes == [201, 201, 429]


def test_turnstile_is_enforced_when_configured(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "turnstile_secret_key", "secret")
    calls = []

    def fake_verify(token, request):
        calls.append(token)
        return token == "good"

    monkeypatch.setattr(security, "verify_turnstile", fake_verify)
    assert client.post("/inquiries", json=inquiry()).status_code == 403
    assert client.post("/inquiries", json=inquiry(turnstile_token="good")).status_code == 201
    assert calls == [None, "good"]


def test_admin_endpoints_hidden_without_token(client, monkeypatch):
    assert client.get("/admin/inquiries").status_code == 404
    monkeypatch.setattr(settings, "admin_token", "s3cret")
    assert client.get("/admin/inquiries", headers={"Authorization": "Bearer wrong"}).status_code == 404
    code = client.post("/inquiries", json=inquiry()).json()["code"]
    listed = client.get("/admin/inquiries", headers={"Authorization": "Bearer s3cret"}).json()
    assert listed[0]["code"] == code and listed[0]["body"].startswith("Los requisitos")
    updated = client.post(
        f"/admin/inquiries/{code}",
        json={"status": "derivado", "response": "Lo enviamos a la Secretaría de Transparencia."},
        headers={"Authorization": "Bearer s3cret"},
    )
    assert updated.json()["status"] == "derivado"
    assert client.get(f"/inquiries/{code}").json()["response"].startswith("Lo enviamos")


# --- security --------------------------------------------------------------


def _request(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": ("10.0.0.1", 1234)})


def test_client_ip_ignores_what_the_client_puts_first_in_x_forwarded_for():
    assert security.client_ip(_request({"X-Forwarded-For": "1.1.1.1, 203.0.113.9"})) == "203.0.113.9"
    assert security.client_ip(_request({"CF-Connecting-IP": "198.51.100.7", "X-Forwarded-For": "1.1.1.1"})) == "198.51.100.7"
    assert security.client_ip(_request({})) == "10.0.0.1"


def test_security_headers_on_api_responses(client):
    res = client.get("/health")
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]
