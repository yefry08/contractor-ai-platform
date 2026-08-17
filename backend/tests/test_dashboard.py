from datetime import date

from app import dashboard, models
from tests.conftest import make_buyer, make_contract, make_country


def _add_anomaly(session, contract, status="open"):
    anomaly = models.Anomaly(contract_id=contract.id, anomaly_type="overcost", status=status)
    session.add(anomaly)


def test_summary_totals_and_anomaly_rate(db_session):
    make_country(db_session)
    for i in range(4):
        c = make_contract(db_session, amount_usd=100.0, award_date=date(2024, 1, 1))
        if i < 2:
            _add_anomaly(db_session, c)
    db_session.commit()

    summary = dashboard.get_summary(db_session, "PY")
    assert summary.total_contracts == 4
    assert summary.total_anomalies == 2
    assert summary.anomaly_rate == 0.5
    assert summary.total_amount_usd == 400.0


def test_summary_total_anomalies_respects_country_and_status_filters(db_session):
    # Regression test: total_anomalies was previously computed with a query
    # that referenced Anomaly.contract_id directly while also select_from-ing
    # an unrelated subquery, producing a cartesian product that silently
    # ignored both the status="open" and country filters.
    make_country(db_session, code="PY", name="Paraguay")
    make_country(db_session, code="CO", name="Colombia")

    py_contract = make_contract(db_session, country_code="PY")
    _add_anomaly(db_session, py_contract, status="open")

    py_dismissed = make_contract(db_session, country_code="PY")
    _add_anomaly(db_session, py_dismissed, status="dismissed")

    co_contract = make_contract(db_session, country_code="CO", currency="COP")
    _add_anomaly(db_session, co_contract, status="open")
    db_session.commit()

    py_summary = dashboard.get_summary(db_session, "PY")
    assert py_summary.total_anomalies == 1  # only the open PY one

    all_summary = dashboard.get_summary(db_session, None)
    assert all_summary.total_anomalies == 2  # both open ones, not the dismissed one


def test_summary_by_year_groups_correctly(db_session):
    make_country(db_session)
    make_contract(db_session, award_date=date(2023, 6, 1))
    make_contract(db_session, award_date=date(2023, 12, 1))
    make_contract(db_session, award_date=date(2024, 1, 1))
    db_session.commit()

    summary = dashboard.get_summary(db_session, "PY")
    by_year = {p.year: p.contracts for p in summary.by_year}
    assert by_year == {2023: 2, 2024: 1}


def test_summary_by_country_only_populated_when_no_filter(db_session):
    make_country(db_session, code="PY", name="Paraguay")
    make_country(db_session, code="CO", name="Colombia")
    make_contract(db_session, country_code="PY")
    make_contract(db_session, country_code="CO")
    db_session.commit()

    scoped = dashboard.get_summary(db_session, "PY")
    assert scoped.by_country == []

    unscoped = dashboard.get_summary(db_session, None)
    codes = {c.country_code for c in unscoped.by_country}
    assert codes == {"PY", "CO"}


def test_best_buyers_excludes_small_sample_buyers(db_session):
    make_country(db_session)
    small_buyer = make_buyer(db_session, name="Compra Chica")
    for _ in range(dashboard.MIN_BUYER_CONTRACTS - 1):
        make_contract(db_session, buyer_id=small_buyer.id)
    db_session.commit()

    ranking = dashboard.get_best_buyers(db_session, "PY", 10)
    assert ranking == []


def test_best_buyers_ranks_lowest_anomaly_rate_first(db_session):
    make_country(db_session)
    clean_buyer = make_buyer(db_session, name="Comprador Limpio")
    messy_buyer = make_buyer(db_session, name="Comprador Cuestionado")

    for _ in range(dashboard.MIN_BUYER_CONTRACTS):
        make_contract(db_session, buyer_id=clean_buyer.id)

    for i in range(dashboard.MIN_BUYER_CONTRACTS):
        c = make_contract(db_session, buyer_id=messy_buyer.id)
        if i < 3:
            _add_anomaly(db_session, c)
    db_session.commit()

    ranking = dashboard.get_best_buyers(db_session, "PY", 10)
    assert [r.name for r in ranking] == ["Comprador Limpio", "Comprador Cuestionado"]
    assert ranking[0].anomaly_rate == 0.0
    assert ranking[1].anomalies == 3


def test_best_buyers_ignores_dismissed_anomalies(db_session):
    make_country(db_session)
    buyer = make_buyer(db_session)
    for _ in range(dashboard.MIN_BUYER_CONTRACTS):
        c = make_contract(db_session, buyer_id=buyer.id)
        _add_anomaly(db_session, c, status="dismissed")
    db_session.commit()

    ranking = dashboard.get_best_buyers(db_session, "PY", 10)
    assert ranking[0].anomalies == 0
    assert ranking[0].anomaly_rate == 0.0
