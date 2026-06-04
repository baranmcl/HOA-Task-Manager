"""Kanban board view.

Groups projects by status into columns. Drag-and-drop in the template
posts to the existing inline status_save endpoint, so all the status-
change validation (including 'delayed needs a reason') stays in one
place.
"""
import datetime as dt

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.roster.models import RosterPerson

from ..models import Project, ProjectStatus
from ._filters import resolve_person_filter

BOARD_STATUSES = [
    (ProjectStatus.NOT_STARTED, "Not started"),
    (ProjectStatus.IN_PROGRESS, "In progress"),
    (ProjectStatus.DELAYED, "Delayed"),
]
COMPLETED_COLUMN = (ProjectStatus.COMPLETED, "Completed")

# Sentinel so projects with no due date sort to the bottom of each column.
_MAX_DATE = dt.date(9999, 12, 31)


@login_required
def board_view(request):
    show_completed = request.GET.get("show_completed") == "1"
    person_id, _banner, selected_person = resolve_person_filter(request)

    qs = (
        Project.instances
        .select_related("category")
        .prefetch_related("raci_assignments__person")
    )

    statuses = list(BOARD_STATUSES)
    if show_completed:
        statuses.append(COMPLETED_COLUMN)
    qs = qs.filter(status__in=[s for s, _ in statuses])

    if person_id is not None:
        qs = qs.filter(raci_assignments__person_id=person_id).distinct()

    columns = []
    for status_value, label in statuses:
        cards = [p for p in qs if p.status == status_value]
        cards.sort(key=lambda p: (p.projected_completion_date or _MAX_DATE, p.title))
        columns.append({"status": status_value, "label": label, "cards": cards})

    any_filter_active = bool(
        show_completed or (person_id is not None and selected_person != "all")
    )

    return render(request, "projects/board.html", {
        "columns": columns,
        "show_completed": show_completed,
        "people": RosterPerson.active.all(),
        "selected_person": selected_person,
        "any_filter_active": any_filter_active,
    })
