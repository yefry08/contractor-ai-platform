import pytest

from app.stats import ZSCORE_CAP, compute_group_stats, modified_zscore


def test_modified_zscore_zero_mad_returns_zero():
    # A degenerate group (every value identical) has MAD 0 -- dividing by it
    # would blow up, so the function short-circuits instead.
    assert modified_zscore(100, 50, 0) == 0.0


def test_modified_zscore_matches_iglewicz_hoaglin_formula():
    z = modified_zscore(120, 100, 10)
    assert z == pytest.approx(0.6745 * (120 - 100) / 10)


def test_modified_zscore_is_antisymmetric_around_the_median():
    above = modified_zscore(120, 100, 10)
    below = modified_zscore(80, 100, 10)
    assert below == pytest.approx(-above)


def test_modified_zscore_is_capped_both_directions():
    assert modified_zscore(1_000_000, 0, 0.0001) == ZSCORE_CAP
    assert modified_zscore(-1_000_000, 0, 0.0001) == -ZSCORE_CAP


def test_compute_group_stats_basic_median_and_iqr():
    stats = compute_group_stats([1, 2, 3, 4, 5, 6, 7, 8, 9])
    assert stats["median"] == 5
    assert stats["n"] == 9
    assert stats["iqr"] == pytest.approx(stats["q3"] - stats["q1"])


def test_compute_group_stats_single_value_has_no_spread():
    stats = compute_group_stats([42])
    assert stats["median"] == 42
    assert stats["mad"] == 0
    assert stats["iqr"] == 0


def test_compute_group_stats_mad_resists_a_single_outlier():
    # This is the entire point of using MAD instead of standard deviation
    # for anomaly detection: one huge outlier shouldn't distort the spread
    # of the "normal" values around it.
    values = [10, 11, 9, 10, 10, 11, 9, 10, 100_000]
    stats = compute_group_stats(values)
    assert stats["mad"] < 5
