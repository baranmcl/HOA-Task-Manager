"""Tests for the calendar view and its date helper."""
import calendar as stdlib_calendar
import datetime as dt

from apps.projects.views.calendar import build_month_grid


def test_build_month_grid_returns_six_weeks_of_seven_days():
    first, last, weeks = build_month_grid(2026, 5)
    assert len(weeks) >= 4 and len(weeks) <= 6  # months span 4-6 visible weeks
    for week in weeks:
        assert len(week) == 7


def test_build_month_grid_starts_on_sunday():
    _, _, weeks = build_month_grid(2026, 5)
    # First column should be Sunday (weekday() == 6 in Python's Mon=0 convention).
    assert weeks[0][0].weekday() == stdlib_calendar.SUNDAY


def test_build_month_grid_may_2026_includes_adjacent_month_padding():
    """May 1 2026 is a Friday — the first row should include April 26-30."""
    first, _, weeks = build_month_grid(2026, 5)
    # First date in the grid is in April, not May.
    assert weeks[0][0] < dt.date(2026, 5, 1)
    assert first == weeks[0][0]


def test_build_month_grid_last_date_extends_into_next_month_if_needed():
    """May 31 2026 is a Sunday — June 1-6 fills out the last row."""
    _, last, weeks = build_month_grid(2026, 5)
    assert last == weeks[-1][-1]
    assert last >= dt.date(2026, 5, 31)
