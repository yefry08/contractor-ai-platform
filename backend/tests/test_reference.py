import math

from app import reference
from tests.conftest import make_buyer, make_contract, make_country


def _anomaly(session, contract):
    from app import models

    session.add(models.Anomaly(contract_id=contract.id, anomaly_type="overcost", status="open", stat_component=4.0))


# The deviation round-trips through log/exp, so it lands a few float ulps off
# an exact ratio: log(200) - log(100) exponentiates to 1.9999999999999984.
def close(actual, expected):
    return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)


def test_deviation_is_percentage_over_the_group_median(db_session):
    make_country(db_session)
    for _ in range(8):
        make_contract(db_session, amount_original=1_000.0)
    doubled = make_contract(db_session, amount_original=2_000.0)
    db_session.commit()

    # Median of the category group is 1000, so 2000 sits 100% over it.
    assert close(reference.deviation_for(db_session, doubled), 1.0)


def test_deviation_is_negative_below_the_median(db_session):
    make_country(db_session)
    for _ in range(8):
        make_contract(db_session, amount_original=1_000.0)
    cheap = make_contract(db_session, amount_original=250.0)
    db_session.commit()

    assert close(reference.deviation_for(db_session, cheap), -0.75)


def test_deviation_prefers_the_buyer_group_over_the_category(db_session):
    make_country(db_session)
    buyer = make_buyer(db_session)
    for _ in range(8):
        make_contract(db_session, amount_original=100.0, buyer_id=buyer.id)
    for _ in range(8):
        make_contract(db_session, amount_original=10_000.0)
    target = make_contract(db_session, amount_original=200.0, buyer_id=buyer.id)
    db_session.commit()

    # Against this buyer's own contracts 200 is double; against the category
    # median (which the far pricier contracts pull up) it would be far below.
    assert close(reference.deviation_for(db_session, target), 1.0)


def test_deviation_is_none_without_a_usable_amount(db_session):
    make_country(db_session)
    make_contract(db_session, amount_original=1_000.0)
    db_session.commit()

    assert reference.deviation_for(db_session, None) is None
    assert reference.deviation_for(db_session, make_contract(db_session, amount_original=0.0)) is None


def test_anomalies_endpoint_exposes_the_deviation(client, db_session):
    make_country(db_session)
    for _ in range(8):
        make_contract(db_session, amount_original=1_000.0)
    flagged = make_contract(db_session, amount_original=3_000.0)
    _anomaly(db_session, flagged)
    db_session.commit()

    body = client.get("/anomalies").json()
    item = next(i for i in body["items"] if i["contract"]["id"] == flagged.id)
    assert math.isclose(item["stat_deviation"], 2.0, rel_tol=1e-9)
