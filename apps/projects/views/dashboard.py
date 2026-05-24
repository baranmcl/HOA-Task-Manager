import datetime as dt

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.roster.models import RosterPerson

from ..models import ActivityLog, Project, ProjectStatus
from ._filters import resolve_person_filter


@login_required
def dashboard(request):
    today = dt.date.today()
    horizon = today + dt.timedelta(days=14)

    person_id, banner, selected_person = resolve_person_filter(request)

    base = Project.instances.exclude(status=ProjectStatus.COMPLETED)
    if person_id is not None:
        base = base.filter(raci_assignments__person_id=person_id).distinct()

    overdue = list(base.filter(projected_completion_date__lt=today)
                       .order_by("projected_completion_date")[:20])
    upcoming = list(base.filter(
        projected_completion_date__gte=today,
        projected_completion_date__lte=horizon,
    ).order_by("projected_completion_date")[:20])

    in_progress_count = base.filter(status=ProjectStatus.IN_PROGRESS).count()

    first_of_month = today.replace(day=1)
    done_this_month_qs = Project.instances.filter(
        status=ProjectStatus.COMPLETED,
        actual_completion_date__gte=first_of_month,
    )
    if person_id is not None:
        done_this_month_qs = done_this_month_qs.filter(
            raci_assignments__person_id=person_id,
        ).distinct()
    done_this_month = done_this_month_qs.count()

    activity_qs = ActivityLog.objects.select_related(
        "actor__profile__roster_person", "project",
    )
    if person_id is not None:
        activity_qs = activity_qs.filter(
            project__raci_assignments__person_id=person_id,
        ).distinct()
    activity = list(activity_qs[:10])

    recurring_qs = Project.instances.filter(
        status=ProjectStatus.NOT_STARTED,
        parent_template__isnull=False,
    ).select_related("parent_template").order_by("projected_completion_date")
    if person_id is not None:
        recurring_qs = recurring_qs.filter(
            raci_assignments__person_id=person_id,
        ).distinct()
    recurring_on_deck = list(recurring_qs[:10])

    return render(request, "home.html", {
        "stats": {
            "overdue": len(overdue),
            "upcoming": len(upcoming),
            "in_progress": in_progress_count,
            "done_this_month": done_this_month,
        },
        "overdue": overdue,
        "upcoming": upcoming,
        "activity": activity,
        "recurring_on_deck": recurring_on_deck,
        "people": RosterPerson.active.all(),
        "selected_person": selected_person,
        "unlinked_user_banner": banner,
    })
