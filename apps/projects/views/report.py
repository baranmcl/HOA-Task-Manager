"""Completion report view.

Free-date-range with preset query strings. Defaults to current calendar
year (Jan 1 -> today).
"""
import datetime as dt

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..services.reports import compute_completion_report


def _default_window():
    today = dt.date.today()
    return dt.date(today.year, 1, 1), today


def _parse_iso(raw):
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


def _presets(today):
    first_of_month = today.replace(day=1)
    last_of_prev_month = first_of_month - dt.timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)

    q_start_month = ((today.month - 1) // 3) * 3 + 1
    q_start = dt.date(today.year, q_start_month, 1)

    if q_start_month == 1:
        prev_q_year, prev_q_start_month = today.year - 1, 10
    else:
        prev_q_year, prev_q_start_month = today.year, q_start_month - 3
    prev_q_start = dt.date(prev_q_year, prev_q_start_month, 1)
    prev_q_end = q_start - dt.timedelta(days=1)

    year_start = dt.date(today.year, 1, 1)
    last_year_start = dt.date(today.year - 1, 1, 1)
    last_year_end = dt.date(today.year - 1, 12, 31)

    return [
        ("This month", first_of_month, today),
        ("This quarter", q_start, today),
        ("This year", year_start, today),
        ("Last month", first_of_prev_month, last_of_prev_month),
        ("Last quarter", prev_q_start, prev_q_end),
        ("Last year", last_year_start, last_year_end),
    ]


@login_required
def report_view(request):
    default_from, default_to = _default_window()
    from_date = _parse_iso(request.GET.get("from")) or default_from
    to_date = _parse_iso(request.GET.get("to")) or default_to

    report = compute_completion_report(from_date, to_date)

    today = dt.date.today()
    presets = [
        {"label": label, "from": f.isoformat(), "to": t.isoformat()}
        for (label, f, t) in _presets(today)
    ]

    return render(request, "projects/report.html", {
        "report": report,
        "from_date": from_date,
        "to_date": to_date,
        "presets": presets,
    })
