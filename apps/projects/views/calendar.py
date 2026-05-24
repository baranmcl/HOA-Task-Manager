"""Month-view calendar page for projects."""
import calendar as stdlib_calendar
import datetime as dt

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from apps.roster.models import RosterPerson

from ..models import Project
from ._filters import resolve_person_filter

_CAL = stdlib_calendar.Calendar(firstweekday=stdlib_calendar.SUNDAY)

# Max chips rendered in a single day cell before showing a "+N more" link.
CELL_CHIP_LIMIT = 3

# Status → chip background+text classes. Matches the palette used by the
# project list row (templates/projects/_list_row.html).
STATUS_CHIP_CLASSES = {
    "completed": "bg-green-100 text-green-800",
    "delayed": "bg-red-100 text-red-800",
    "in_progress": "bg-blue-100 text-blue-800",
    "not_started": "bg-gray-100 text-gray-700",
}


def build_month_grid(year: int, month: int) -> tuple[dt.date, dt.date, list[list[dt.date]]]:
    """Build the 6×7 (sometimes 5×7) date grid for a calendar month view.

    Returns:
        (first_visible_date, last_visible_date, weeks)
        weeks is a list of weeks; each week is a list of 7 dates (Sun-Sat).
        Adjacent-month days are real dates outside the requested month — the
        caller dims them in the template.
    """
    weeks = _CAL.monthdatescalendar(year, month)
    first = weeks[0][0]
    last = weeks[-1][-1]
    return first, last, weeks


@login_required
def calendar_view(request, year: int | None = None, month: int | None = None):
    today = dt.date.today()
    if year is None or month is None:
        year, month = today.year, today.month
    if not (1 <= month <= 12) or not (1900 <= year <= 2100):
        raise Http404("Invalid year/month")

    person_id, banner, selected_person = resolve_person_filter(request)

    first, last, weeks = build_month_grid(year, month)

    qs = Project.instances.select_related("category").filter(
        projected_completion_date__gte=first,
        projected_completion_date__lte=last,
    )
    if person_id is not None:
        qs = qs.filter(raci_assignments__person_id=person_id).distinct()
    projects = list(qs)

    # Bucket projects by their due date.
    by_date: dict[dt.date, list[Project]] = {}
    for p in projects:
        by_date.setdefault(p.projected_completion_date, []).append(p)

    # Build the cell structure the template iterates over.
    cells_by_week = []
    for week in weeks:
        row = []
        for day in week:
            day_projects = by_date.get(day, [])
            row.append({
                "date": day,
                "is_other_month": day.month != month,
                "is_today": day == today,
                "projects": day_projects[:CELL_CHIP_LIMIT],
                "overflow_count": max(0, len(day_projects) - CELL_CHIP_LIMIT),
            })
        cells_by_week.append(row)

    # Prev/next/today navigation URLs.
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)

    return render(request, "projects/calendar.html", {
        "year": year,
        "month": month,
        "month_label": dt.date(year, month, 1).strftime("%B %Y"),
        "weeks": cells_by_week,
        "prev_year": prev_year, "prev_month": prev_month,
        "next_year": next_year, "next_month": next_month,
        "today_year": today.year, "today_month": today.month,
        "weekday_headers": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "status_chip_classes": STATUS_CHIP_CLASSES,
        "people": RosterPerson.active.all(),
        "selected_person": selected_person,
        "unlinked_user_banner": banner,
    })
