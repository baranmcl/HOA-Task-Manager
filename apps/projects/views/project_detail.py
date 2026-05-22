from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.roster.models import RosterPerson

from ..models import (
    ActivityLog,
    Project,
    ProjectPriority,
    ProjectStatus,
    RACIRole,
)


@login_required
def detail(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("category", "board_approval", "created_by").prefetch_related(
            "raci_assignments__person",
            "tags",
            "notes__author",
            "attachments__uploaded_by",
        ),
        pk=pk,
    )
    activity = ActivityLog.objects.filter(project=project).select_related("actor")[:30]
    available_people = RosterPerson.active.exclude(
        raci_assignments__project=project,
    ).distinct()
    return render(
        request,
        "projects/detail.html",
        {
            "project": project,
            "activity": activity,
            "raci_role_choices": RACIRole.choices,
            "status_choices": ProjectStatus.choices,
            "priority_choices": ProjectPriority.choices,
            "available_people": available_people,
        },
    )
