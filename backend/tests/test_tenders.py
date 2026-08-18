from app import tenders
from app.stats import MIN_GROUP_SIZE
from tests.conftest import make_contract, make_country


def test_official_portals_cover_all_four_countries():
    assert set(tenders.OFFICIAL_PORTALS.keys()) == {"PY", "CO", "CR", "DO"}
    for portal in tenders.OFFICIAL_PORTALS.values():
        assert portal["url"].startswith("https://")


def test_categories_excludes_small_samples(db_session):
    make_country(db_session)
    for _ in range(MIN_GROUP_SIZE - 1):
        make_contract(db_session, category_code="obras")
    for _ in range(MIN_GROUP_SIZE):
        make_contract(db_session, category_code="servicios")
    db_session.commit()

    cats = tenders.get_categories(db_session, "PY")
    assert [c.category_code for c in cats] == ["servicios"]
    assert cats[0].contracts == MIN_GROUP_SIZE


def test_categories_sorted_by_volume_descending(db_session):
    make_country(db_session)
    for _ in range(MIN_GROUP_SIZE):
        make_contract(db_session, category_code="small")
    for _ in range(MIN_GROUP_SIZE + 5):
        make_contract(db_session, category_code="big")
    db_session.commit()

    cats = tenders.get_categories(db_session, "PY")
    assert [c.category_code for c in cats] == ["big", "small"]


def test_benchmark_returns_none_below_min_group_size(db_session):
    make_country(db_session)
    for _ in range(MIN_GROUP_SIZE - 1):
        make_contract(db_session, category_code="servicios")
    db_session.commit()

    assert tenders.get_price_benchmark(db_session, "PY", "servicios") is None


def test_benchmark_median_and_range_reflect_the_data(db_session):
    make_country(db_session)
    amounts = [800_000, 900_000, 950_000, 1_000_000, 1_000_000, 1_050_000, 1_100_000, 1_200_000]
    for amount in amounts:
        make_contract(db_session, category_code="servicios", amount_original=amount, currency="PYG")
    db_session.commit()

    result = tenders.get_price_benchmark(db_session, "PY", "servicios")
    assert result is not None
    assert result.currency == "PYG"
    assert result.sample_size == len(amounts)
    assert result.typical_low < result.median_amount < result.typical_high


def test_benchmark_picks_dominant_currency_when_mixed(db_session):
    # Shouldn't normally happen within one country, but the schema allows
    # mixed currencies per category -- the benchmark should still be
    # internally consistent instead of averaging apples and oranges.
    make_country(db_session)
    for _ in range(MIN_GROUP_SIZE):
        make_contract(db_session, category_code="servicios", amount_original=1_000_000, currency="PYG")
    for _ in range(2):
        make_contract(db_session, category_code="servicios", amount_original=500, currency="USD")
    db_session.commit()

    result = tenders.get_price_benchmark(db_session, "PY", "servicios")
    assert result is not None
    assert result.currency == "PYG"
    assert result.sample_size == MIN_GROUP_SIZE
