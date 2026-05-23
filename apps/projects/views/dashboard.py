import datetime as dt

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.roster.models import RosterPerson

from ..models import ActivityLog, Project, ProjectStatus


def _resolve_person_filter(request):
    """Returns (person_id_or_None, show_unlinked_banner, selected_value).

    - person_id_or_None: the RosterPerson pk to filter on, or None for "show all".
    - show_unlinked_banner: True only when the user has no roster_person link
      AND did not explicitly choose `?person=all` or `?person=<id>` themselves.
    - selected_value: the value to render in the dropdown — "all", a numeric
      pk as a string, or "" if no explicit choice was made.
    """
    raw = request.GET.get("person")
    linked = getattr(request.user.profile, "roster_person", None)

    if raw == "all":
        return None, False, "all"
    if raw and raw.isdigit():
        return int(raw), False, raw
    # No explicit choice — auto-default to linked person if available.
    if linked is not None:
        return linked.pk, False, str(linked.pk)
    return None, True, ""


@login_required
def dashboard(request):
    today = dt.date.today()
    horizon = today + dt.timedelta(days=14)

    person_id, banner, selected_person = _resolve_person_filter(request)

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

    activity_qs = ActivityLog.objects.select_related("actor", "project")
    if person_id is not None:
        activity_qs = activity_qs.filter(
            project__raci_assignments__person_id=person_id,
        ).distinct()
    activity = list(activity_qs[:10])

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
        "people": RosterPerson.active.all(),
        "selected_person": selected_person,
        "unlinked_user_banner": banner,
    })
