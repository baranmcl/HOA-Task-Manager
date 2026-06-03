from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.roster.models import RosterGroup, RosterPerson

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
            "raci_assignments__source_group",
            "tags",
            "notes__author__profile__roster_person",
            "attachments__uploaded_by",
            "checklist_items",
        ),
        pk=pk,
    )
    activity = (
        ActivityLog.objects.filter(project=project)
        .select_related("actor__profile__roster_person")[:30]
    )
    # All active roster people. The unique constraint on
    # (project, person, role) and the IntegrityError catch in raci_add
    # prevent true duplicates — letting the same person appear here
    # enables assigning them to multiple roles on the same project.
    available_people = RosterPerson.active.all()
    available_groups = RosterGroup.objects.all()
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
            "available_groups": available_groups,
            "items": project.checklist_items.all(),
        },
    )
