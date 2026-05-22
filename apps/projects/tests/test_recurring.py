import datetime as dt

import pytest

from apps.projects.recurring import advance, suffix_for


@pytest.mark.parametrize("rule,start,expected", [
    ("weekly", dt.date(2026, 5, 5), dt.date(2026, 5, 12)),
    ("monthly", dt.date(2026, 5, 5), dt.date(2026, 6, 5)),
    ("monthly", dt.date(2026, 1, 31), dt.date(2026, 2, 28)),
    ("quarterly", dt.date(2026, 5, 5), dt.date(2026, 8, 5)),
    ("semiannual", dt.date(2026, 5, 5), dt.date(2026, 11, 5)),
    ("annual", dt.date(2026, 5, 5), dt.date(2027, 5, 5)),
])
def test_advance(rule, start, expected):
    assert advance(rule, start) == expected


@pytest.mark.parametrize("rule,date,expected", [
    ("weekly", dt.date(2026, 4, 6), "Week of 2026-04-06"),
    ("monthly", dt.date(2026, 4, 1), "April 2026"),
    ("quarterly", dt.date(2026, 4, 1), "Q2 2026"),
    ("quarterly", dt.date(2026, 7, 1), "Q3 2026"),
    ("semiannual", dt.date(2026, 1, 1), "H1 2026"),
    ("semiannual", dt.date(2026, 7, 1), "H2 2026"),
    ("annual", dt.date(2026, 4, 1), "2026"),
])
def test_suffix(rule, date, expected):
    assert suffix_for(rule, date) == expected
