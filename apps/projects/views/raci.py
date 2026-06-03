from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.roster.models import RosterGroup, RosterPerson

from ..models import Project, RACIAssignment, RACIRole


def _render_list(request, project):
    return render(request, "projects/_raci_list_swap.html", {
        "project": project,
        "raci_role_choices": RACIRole.choices,
        # All active roster people. Multi-role-per-person is allowed by
        # the data model; the IntegrityError catch in raci_add rejects
        # true (project, person, role) duplicates.
        "available_people": RosterPerson.active.all(),
        "available_groups": RosterGroup.objects.all(),
    })


@login_required
@require_http_methods(["POST"])
def raci_add(request, pk):
    project = get_object_or_404(Project, pk=pk)
    person_id = request.POST.get("person", "").strip()
    role = request.POST.get("role", "")
    if not person_id.isdigit() or role not in dict(RACIRole.choices):
        return HttpResponseBadRequest("Invalid person or role")
    person = get_object_or_404(RosterPerson, pk=int(person_id))
    if person.archived:
        return HttpResponseBadRequest("Cannot assign archived person to a new role.")
    try:
        RACIAssignment.objects.create(project=project, person=person, role=role)
    except IntegrityError:
        return HttpResponseBadRequest("That person is already in that role.")
    return _render_list(request, project)


@login_required
@require_http_methods(["POST"])
def raci_add_group(request, pk):
    """Expand a group's active members into individual RACIAssignment rows.

    Each new row records source_group so the UI can show "via <Group>".
    Existing (project, person, role) triples are skipped silently — the
    operation is idempotent so a board member can re-apply a group after
    membership changes without worrying about duplicates.

    All-or-nothing: wrapped in a transaction. If any row blows up for an
    unexpected reason, the whole expansion rolls back.
    """
    project = get_object_or_404(Project, pk=pk)
    group_id = request.POST.get("group", "").strip()
    role = request.POST.get("role", "")
    if not group_id.isdigit() or role not in dict(RACIRole.choices):
        return HttpResponseBadRequest("Invalid group or role")
    group = get_object_or_404(RosterGroup, pk=int(group_id))

    with transaction.atomic():
        for person in group.active_members():
            RACIAssignment.objects.get_or_create(
                project=project, person=person, role=role,
                defaults={"source_group": group},
            )
    return _render_list(request, project)


@login_required
@require_http_methods(["POST"])
def raci_remove(request, pk):
    a = get_object_or_404(RACIAssignment, pk=pk)
    project = a.project
    a.delete()
    return _render_list(request, project)
