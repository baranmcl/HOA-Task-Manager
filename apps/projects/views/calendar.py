"""Month-view calendar page for projects."""
import calendar as stdlib_calendar
import datetime as dt

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from apps.roster.models import RosterPerson

from ..models import ChecklistItem, Project, ProjectCategory, ProjectStatus
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

# Stable per-project border colors for checklist items. Hashing the
# project pk → palette index gives the same color across cells for
# the same project, so a user can visually trace "all the items
# belonging to Bike Room Renovation are pink-bordered". 10 colors is
# plenty for the realistic distinct-project count in any month.
CHECKLIST_BORDER_PALETTE = [
    "border-purple-500",
    "border-pink-500",
    "border-yellow-500",
    "border-orange-500",
    "border-teal-500",
    "border-indigo-500",
    "border-amber-500",
    "border-lime-500",
    "border-rose-500",
    "border-cyan-500",
]


def project_border_class(project_pk: int) -> str:
    """Deterministic color class for a project's checklist items."""
    return CHECKLIST_BORDER_PALETTE[project_pk % len(CHECKLIST_BORDER_PALETTE)]


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

    cat_id_raw = request.GET.get("category", "").strip()
    selected_category = cat_id_raw if cat_id_raw.isdigit() else ""
    status_raw = request.GET.get("status", "")
    selected_status = status_raw if status_raw in dict(ProjectStatus.choices) else ""

    first, last, weeks = build_month_grid(year, month)

    # Build the base queryset of "projects whose own due date falls in
    # this window" and a separate "all projects matching the filters"
    # set used to scope checklist-item visibility.
    base_qs = Project.instances.select_related("category")
    if person_id is not None:
        base_qs = base_qs.filter(raci_assignments__person_id=person_id)
    if selected_category:
        base_qs = base_qs.filter(category_id=int(selected_category))
    if selected_status:
        base_qs = base_qs.filter(status=selected_status)
    base_qs = base_qs.distinct()

    qs = base_qs.filter(
        projected_completion_date__gte=first,
        projected_completion_date__lte=last,
    )
    projects = list(qs)

    # Bucket projects by their due date.
    by_date: dict[dt.date, list[Project]] = {}
    for p in projects:
        by_date.setdefault(p.projected_completion_date, []).append(p)

    # Checklist items: show incomplete items with due dates in this window.
    # Visibility follows project visibility — items from projects hidden
    # by filters are also hidden. The visible set is the union of
    # "projects with due dates in window" and "all projects matching
    # filters" (the latter covers projects without their own due dates
    # but with dated checklist items).
    visible_project_ids = {p.pk for p in projects}
    visible_project_ids |= set(base_qs.values_list("pk", flat=True))

    items_qs = ChecklistItem.objects.filter(
        project_id__in=visible_project_ids,
        completed=False,
        due_date__isnull=False,
        due_date__gte=first,
        due_date__lte=last,
    ).select_related("project")

    # Attach a stable border color per item, derived from its project pk.
    items_by_date: dict[dt.date, list[ChecklistItem]] = {}
    for item in items_qs:
        item.border_class = project_border_class(item.project_id)
        items_by_date.setdefault(item.due_date, []).append(item)

    # Build the cell structure the template iterates over.
    cells_by_week = []
    for week in weeks:
        row = []
        for day in week:
            day_projects = by_date.get(day, [])
            day_items = items_by_date.get(day, [])
            row.append({
                "date": day,
                "is_other_month": day.month != month,
                "is_today": day == today,
                "projects": day_projects[:CELL_CHIP_LIMIT],
                "overflow_count": max(0, len(day_projects) - CELL_CHIP_LIMIT),
                # Checklist items get their own list — rendered smaller +
                # below project pills so the visual hierarchy stays
                # projects-first.
                "checklist_items": day_items,
            })
        cells_by_week.append(row)

    # Prev/next/today navigation URLs.
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)

    any_filter_active = bool(
        (person_id is not None and selected_person != "all")
        or selected_category
        or selected_status
    )

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
        "categories": ProjectCategory.objects.all(),
        "status_choices": ProjectStatus.choices,
        "selected_person": selected_person,
        "selected_category": selected_category,
        "selected_status": selected_status,
        "any_filter_active": any_filter_active,
        "unlinked_user_banner": banner,
    })
