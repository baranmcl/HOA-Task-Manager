from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.roster.models import RosterPerson

from ..models import Project, RACIAssignment, RACIRole


def _render_list(request, project):
    return render(request, "projects/_raci_list_swap.html", {
        "project": project,
        "raci_role_choices": RACIRole.choices,
        # All active roster people. Multi-role-per-person is allowed by
        # the data model; the IntegrityError catch in raci_add rejects
        # true (project, person, role) duplicates.
        "available_people": RosterPerson.active.all(),
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
def raci_remove(request, pk):
    a = get_object_or_404(RACIAssignment, pk=pk)
    project = a.project
    a.delete()
    return _render_list(request, project)
