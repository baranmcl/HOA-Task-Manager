import datetime as dt

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..models import ActivityLog, Project, ProjectStatus


@login_required
def dashboard(request):
    today = dt.date.today()
    horizon = today + dt.timedelta(days=14)
    base = Project.instances.exclude(status=ProjectStatus.COMPLETED)

    overdue = list(base.filter(projected_completion_date__lt=today)
                       .order_by("projected_completion_date")[:20])
    upcoming = list(base.filter(
        projected_completion_date__gte=today,
        projected_completion_date__lte=horizon,
    ).order_by("projected_completion_date")[:20])

    in_progress_count = base.filter(status=ProjectStatus.IN_PROGRESS).count()

    first_of_month = today.replace(day=1)
    done_this_month = Project.instances.filter(
        status=ProjectStatus.COMPLETED,
        actual_completion_date__gte=first_of_month,
    ).count()

    activity = ActivityLog.objects.select_related("actor", "project")[:10]

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
    })
