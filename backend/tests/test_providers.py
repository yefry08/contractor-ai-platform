"""Unit tests for app/providers.py.

Important context for reading these: there is no supplier/provider field
anywhere in the schema (see providers.py's own module docstring and the
`buyer as proxy for provider` comments) -- every "provider" metric here is
actually computed over `buyer_id`. That is a real, tracked limitation, not
something these tests paper over: test_get_top_providers_repeat_buyer_count_is_always_one_under_the_buyer_proxy
below exists specifically to pin down and document the consequence, so a
future supplier-extraction change has something concrete to change *to*.
"""

from datetime import date

from app import providers
from tests.conftest import make_buyer, make_contract, make_country


def _seed_two_countries(db_session):
    make_country(db_session, code="PY", name="Paraguay")
    make_country(db_session, code="CO", name="Colombia")


# ---------- calculate_hhi ----------


def test_hhi_is_zero_with_no_spending_data(db_session):
    make_country(db_session)
    db_session.commit()
    assert providers.calculate_hhi(db_session) == 0.0


def test_hhi_is_10000_for_a_single_provider_monopoly(db_session):
    make_country(db_session)
    buyer = make_buyer(db_session)
    for _ in range(3):
        make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0)
    db_session.commit()

    assert providers.calculate_hhi(db_session) == 10000.0


def test_hhi_for_two_equal_share_providers(db_session):
    make_country(db_session)
    b1 = make_buyer(db_session, name="Proveedor A")
    b2 = make_buyer(db_session, name="Proveedor B")
    make_contract(db_session, buyer_id=b1.id, amount_usd=500.0)
    make_contract(db_session, buyer_id=b2.id, amount_usd=500.0)
    db_session.commit()

    # HHI = (0.5^2 + 0.5^2) * 10000 = 5000
    assert providers.calculate_hhi(db_session) == 5000.0


def test_hhi_filters_by_country(db_session):
    _seed_two_countries(db_session)
    py_buyer = make_buyer(db_session, country_code="PY", name="PY Corp")
    co_buyer = make_buyer(db_session, country_code="CO", name="CO Corp")
    make_contract(db_session, country_code="PY", buyer_id=py_buyer.id, amount_usd=100.0)
    make_contract(db_session, country_code="CO", buyer_id=co_buyer.id, amount_usd=999.0)
    db_session.commit()

    # Each country has exactly one provider taking 100% of that country's
    # spend, so both should independently report a monopoly regardless of
    # the other country's (much larger) amount.
    assert providers.calculate_hhi(db_session, "PY") == 10000.0
    assert providers.calculate_hhi(db_session, "CO") == 10000.0


def test_hhi_ignores_contracts_with_no_amount(db_session):
    make_country(db_session)
    buyer = make_buyer(db_session)
    make_contract(db_session, buyer_id=buyer.id, amount_usd=None)
    db_session.commit()

    # No priced contracts at all -> total_spending is 0 -> defined as 0.0,
    # not a divide-by-zero error.
    assert providers.calculate_hhi(db_session) == 0.0


# ---------- get_provider_stats ----------


def test_provider_stats_on_empty_db_returns_zeros_not_errors(db_session):
    make_country(db_session)
    db_session.commit()
    stats = providers.get_provider_stats(db_session)

    assert stats.total_providers == 0
    assert stats.total_contracts == 0
    assert stats.total_spending_usd == 0.0
    assert stats.hhi_concentration == 0.0
    assert stats.top_10_share == 0.0


def test_provider_stats_counts_and_top_10_share(db_session):
    make_country(db_session)
    # 11 distinct buyers, one of them ("whale") holding the majority of spend.
    whale = make_buyer(db_session, name="Whale Corp")
    make_contract(db_session, buyer_id=whale.id, amount_usd=1000.0)
    for i in range(10):
        small = make_buyer(db_session, name=f"Small {i}")
        make_contract(db_session, buyer_id=small.id, amount_usd=10.0)
    db_session.commit()

    stats = providers.get_provider_stats(db_session)

    assert stats.total_providers == 11
    assert stats.total_contracts == 11
    assert stats.total_spending_usd == 1100.0
    # Top 10 by spending = whale (1000) + 9 of the 10 smalls (90) = 1090 / 1100
    assert round(stats.top_10_share, 2) == round(1090 / 1100 * 100, 2)


def test_provider_stats_scoped_to_country_excludes_others(db_session):
    _seed_two_countries(db_session)
    py_buyer = make_buyer(db_session, country_code="PY")
    co_buyer = make_buyer(db_session, country_code="CO")
    make_contract(db_session, country_code="PY", buyer_id=py_buyer.id, amount_usd=100.0)
    make_contract(db_session, country_code="CO", buyer_id=co_buyer.id, amount_usd=200.0)
    db_session.commit()

    py_stats = providers.get_provider_stats(db_session, "PY")
    assert py_stats.total_providers == 1
    assert py_stats.total_spending_usd == 100.0


# ---------- get_top_providers ----------


def test_top_providers_excludes_below_min_contracts_threshold(db_session):
    make_country(db_session)
    lonely = make_buyer(db_session, name="Solo Corp")
    make_contract(db_session, buyer_id=lonely.id, amount_usd=1_000_000.0)
    db_session.commit()

    # Default min_contracts=2 -- a single contract must not appear, no matter
    # how large, or "top providers" becomes noise from one-off buyers.
    results = providers.get_top_providers(db_session, min_contracts=2)
    assert results == []


def test_top_providers_ranked_by_spending_descending(db_session):
    make_country(db_session)
    big = make_buyer(db_session, name="Big Corp")
    small = make_buyer(db_session, name="Small Corp")
    for _ in range(2):
        make_contract(db_session, buyer_id=big.id, amount_usd=500.0)
        make_contract(db_session, buyer_id=small.id, amount_usd=50.0)
    db_session.commit()

    results = providers.get_top_providers(db_session, min_contracts=2)

    assert [r.provider_name for r in results] == ["Big Corp", "Small Corp"]
    assert results[0].total_spending_usd == 1000.0
    assert results[0].avg_contract_value_usd == 500.0


def test_top_providers_market_and_spending_share_sum_correctly(db_session):
    make_country(db_session)
    a = make_buyer(db_session, name="A")
    b = make_buyer(db_session, name="B")
    for _ in range(3):
        make_contract(db_session, buyer_id=a.id, amount_usd=100.0)
    for _ in range(3):
        make_contract(db_session, buyer_id=b.id, amount_usd=100.0)
    db_session.commit()

    results = providers.get_top_providers(db_session, min_contracts=2)
    assert len(results) == 2
    # Equal split -> each provider is exactly half of both contracts and spend.
    for r in results:
        assert round(r.market_share, 4) == 50.0
        assert round(r.spending_share, 4) == 50.0


def test_top_providers_anomaly_rate_only_counts_open_anomalies(db_session):
    from app import models

    make_country(db_session)
    buyer = make_buyer(db_session, name="Flagged Corp")
    c1 = make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0)
    c2 = make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0)
    db_session.add(models.Anomaly(contract_id=c1.id, anomaly_type="overcost", status="open"))
    # A dismissed anomaly on the *other* contract must not count toward the rate.
    db_session.add(models.Anomaly(contract_id=c2.id, anomaly_type="overcost", status="dismissed"))
    db_session.commit()

    results = providers.get_top_providers(db_session, min_contracts=2)
    assert len(results) == 1
    assert results[0].anomaly_rate == 0.5  # 1 open anomaly / 2 contracts


def test_top_providers_repeat_buyer_count_is_always_one_under_the_buyer_proxy(db_session):
    """Documents a real, known limitation rather than hiding it: `provider`
    here IS `buyer_id` (no supplier field exists yet), so "how many distinct
    buyers does this provider serve" is asking "how many distinct values does
    a column equal to itself have" -- always exactly one. This is not a
    useful signal today; it becomes one only once real supplier data lands.
    If this test starts failing, the underlying data model changed and this
    field's meaning (and this comment) need to be revisited together."""
    make_country(db_session)
    buyer = make_buyer(db_session)
    for _ in range(3):
        make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0)
    db_session.commit()

    results = providers.get_top_providers(db_session, min_contracts=2)
    assert results[0].repeat_buyer_count == 1


def test_top_providers_respects_limit(db_session):
    make_country(db_session)
    for i in range(5):
        b = make_buyer(db_session, name=f"Provider {i}")
        for _ in range(2):
            make_contract(db_session, buyer_id=b.id, amount_usd=float(100 + i))
    db_session.commit()

    results = providers.get_top_providers(db_session, min_contracts=2, limit=3)
    assert len(results) == 3


# ---------- get_price_favoritism_trends ----------


def test_price_favoritism_skips_providers_with_fewer_than_two_contracts(db_session):
    make_country(db_session)
    buyer = make_buyer(db_session)
    make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0, award_date=date(2024, 1, 15))
    db_session.commit()

    results = providers.get_price_favoritism_trends(db_session, start_year=2024, end_year=2024)
    assert results == []


def test_price_favoritism_markup_is_positive_above_market_average(db_session):
    make_country(db_session)
    baseline_buyer = make_buyer(db_session, name="Average Corp")
    premium_buyer = make_buyer(db_session, name="Premium Corp")

    # Two "average" contracts near 100 to establish the year's baseline...
    make_contract(db_session, buyer_id=baseline_buyer.id, amount_usd=100.0, award_date=date(2024, 3, 1))
    make_contract(db_session, buyer_id=baseline_buyer.id, amount_usd=100.0, award_date=date(2024, 6, 1))
    # ...and one provider consistently paid double.
    make_contract(db_session, buyer_id=premium_buyer.id, amount_usd=200.0, award_date=date(2024, 2, 1))
    make_contract(db_session, buyer_id=premium_buyer.id, amount_usd=200.0, award_date=date(2024, 9, 1))
    db_session.commit()

    results = providers.get_price_favoritism_trends(db_session, start_year=2024, end_year=2024)
    by_name = {r.provider_name: r for r in results}

    # Baseline = avg(100, 100, 200, 200) = 150
    assert by_name["Average Corp"].market_baseline_usd == 150.0
    assert by_name["Average Corp"].markup_percent < 0  # below the market average
    assert by_name["Premium Corp"].markup_percent > 0  # above the market average
    assert round(by_name["Premium Corp"].markup_percent, 2) == round((200 - 150) / 150 * 100, 2)


def test_price_favoritism_excludes_years_outside_the_requested_range(db_session):
    make_country(db_session)
    buyer = make_buyer(db_session)
    make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0, award_date=date(2020, 1, 1))
    make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0, award_date=date(2020, 6, 1))
    db_session.commit()

    results = providers.get_price_favoritism_trends(db_session, start_year=2023, end_year=2025)
    assert results == []


# ---------- get_geographic_favoritism ----------


def test_geographic_favoritism_market_share_within_country(db_session):
    _seed_two_countries(db_session)
    dominant = make_buyer(db_session, country_code="PY", name="Dominant")
    minor = make_buyer(db_session, country_code="PY", name="Minor")
    make_contract(db_session, country_code="PY", buyer_id=dominant.id, amount_usd=900.0)
    make_contract(db_session, country_code="PY", buyer_id=minor.id, amount_usd=100.0)
    db_session.commit()

    results = providers.get_geographic_favoritism(db_session)
    by_name = {r.provider_name: r for r in results}

    assert round(by_name["Dominant"].market_share_in_country, 2) == 90.0
    assert round(by_name["Minor"].market_share_in_country, 2) == 10.0


def test_geographic_favoritism_respects_limit_per_country(db_session):
    make_country(db_session)
    for i in range(8):
        b = make_buyer(db_session, name=f"Provider {i}")
        make_contract(db_session, buyer_id=b.id, amount_usd=float(100 + i))
    db_session.commit()

    results = providers.get_geographic_favoritism(db_session, limit_per_country=3)
    assert len(results) == 3


# ---------- get_temporal_patterns ----------


def test_temporal_patterns_requires_at_least_three_awards_in_the_same_month(db_session):
    make_country(db_session)
    buyer = make_buyer(db_session)
    make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0, award_date=date(2024, 5, 1))
    make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0, award_date=date(2024, 5, 15))
    db_session.commit()

    # Only two awards in May -- below the clustering threshold.
    assert providers.get_temporal_patterns(db_session) == []


def test_temporal_patterns_flags_three_or_more_awards_in_one_month(db_session):
    make_country(db_session)
    buyer = make_buyer(db_session, name="Clustered Corp")
    for day in (1, 10, 20):
        make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0, award_date=date(2024, 5, day))
    db_session.commit()

    results = providers.get_temporal_patterns(db_session)
    assert len(results) == 3
    assert all(r.provider_name == "Clustered Corp" for r in results)
    assert all(r.consecutive_awards == 3 for r in results)


def test_temporal_patterns_does_not_cross_month_boundaries(db_session):
    make_country(db_session)
    buyer = make_buyer(db_session)
    # Two in April, two in May -- neither month alone reaches the threshold of
    # three, so nothing should be flagged even though four awards exist total.
    make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0, award_date=date(2024, 4, 28))
    make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0, award_date=date(2024, 4, 29))
    make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0, award_date=date(2024, 5, 1))
    make_contract(db_session, buyer_id=buyer.id, amount_usd=100.0, award_date=date(2024, 5, 2))
    db_session.commit()

    assert providers.get_temporal_patterns(db_session) == []
