"""Tests for analysis.compare_amount -- the live statistical comparison used
by POST /analyze/compare. Seeds a small reference group directly via the ORM
rather than going through the API, so these stay focused on the comparison
math instead of the HTTP layer (covered separately in test_api.py)."""

from app import analysis
from app.stats import MIN_GROUP_SIZE
from tests.conftest import make_buyer, make_contract, make_country


def _seed_group(session, amounts, **contract_overrides):
    make_country(session)
    for amount in amounts:
        make_contract(session, amount_original=amount, **contract_overrides)
    session.commit()


def test_returns_none_when_group_too_small(db_session):
    _seed_group(db_session, [1_000_000] * (MIN_GROUP_SIZE - 1))
    result = analysis.compare_amount(db_session, "PY", "PYG", 1_000_000, None, None)
    assert result is None


def test_typical_amount_is_verdict_normal(db_session):
    # A tight cluster around 1,000,000 -- submitting right at the middle
    # should never be flagged.
    _seed_group(db_session, [950_000, 980_000, 1_000_000, 1_010_000, 1_020_000, 990_000, 1_005_000, 995_000, 1_000_000])
    result = analysis.compare_amount(db_session, "PY", "PYG", 1_000_000, None, None)
    assert result is not None
    assert result.verdict == "normal"
    assert result.group_size == 9


def test_extreme_outlier_is_verdict_alta(db_session):
    _seed_group(db_session, [950_000, 980_000, 1_000_000, 1_010_000, 1_020_000, 990_000, 1_005_000, 995_000, 1_000_000])
    # 50x the reference median.
    result = analysis.compare_amount(db_session, "PY", "PYG", 50_000_000, None, None)
    assert result is not None
    assert result.verdict == "alta"
    assert result.zscore_flagged is True


def test_group_size_reflects_reference_group_only(db_session):
    make_country(db_session)
    for amount in [1_000_000] * 9:
        make_contract(db_session, amount_original=amount, currency="PYG")
    for amount in [1_000_000] * 9:
        make_contract(db_session, amount_original=amount, currency="COP")  # different currency, must be excluded
    db_session.commit()

    result = analysis.compare_amount(db_session, "PY", "PYG", 1_000_000, None, None)
    assert result is not None
    assert result.group_size == 9


def test_prefers_buyer_group_when_it_has_enough_data(db_session):
    make_country(db_session)
    buyer = make_buyer(db_session, name="Municipalidad Grande")
    for amount in [500_000] * MIN_GROUP_SIZE:
        make_contract(db_session, amount_original=amount, buyer_id=buyer.id)
    for amount in [2_000_000] * MIN_GROUP_SIZE:
        make_contract(db_session, amount_original=amount)  # no buyer -- country-wide pool
    db_session.commit()

    result = analysis.compare_amount(db_session, "PY", "PYG", 500_000, None, "Municipalidad Grande")
    assert result is not None
    assert result.reference_group == "PY:comprador"
    assert result.group_size == MIN_GROUP_SIZE


def test_falls_back_to_country_when_buyer_group_too_small(db_session):
    make_country(db_session)
    buyer = make_buyer(db_session, name="Municipalidad Chica")
    for amount in [500_000] * (MIN_GROUP_SIZE - 1):  # not enough for its own group
        make_contract(db_session, amount_original=amount, buyer_id=buyer.id)
    for amount in [500_000] * MIN_GROUP_SIZE:
        make_contract(db_session, amount_original=amount)
    db_session.commit()

    result = analysis.compare_amount(db_session, "PY", "PYG", 500_000, None, "Municipalidad Chica")
    assert result is not None
    assert result.reference_group == "PY:country"
