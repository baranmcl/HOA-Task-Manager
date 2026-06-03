"""Views for RosterGroup management: list, create/edit/delete, member ops.

Group membership changes do NOT retroactively update RACI assignments
that were previously created via group-expansion — those assignments
keep their existing person/role until a board member manually edits or
removes them on the project page. See RosterGroup docstring for the
audit-trail rationale.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import RosterGroupForm
from .models import GroupMembership, RosterGroup, RosterPerson


@login_required
def group_list(request):
    groups = RosterGroup.objects.all().prefetch_related("memberships__person")
    return render(request, "roster/group_list.html", {"groups": groups})


@login_required
def group_detail(request, pk):
    group = get_object_or_404(RosterGroup, pk=pk)
    members = group.memberships.select_related("person").all()
    available_people = RosterPerson.active.exclude(
        group_memberships__group=group,
    )
    return render(request, "roster/group_detail.html", {
        "group": group,
        "members": members,
        "available_people": available_people,
    })


@login_required
def group_create(request):
    if request.method == "POST":
        form = RosterGroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            messages.success(request, f"Created {group.name}.")
            return redirect("roster:group_detail", pk=group.pk)
    else:
        form = RosterGroupForm()
    return render(request, "roster/group_form.html", {"form": form, "group": None})


@login_required
def group_edit(request, pk):
    group = get_object_or_404(RosterGroup, pk=pk)
    if request.method == "POST":
        form = RosterGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved.")
            return redirect("roster:group_detail", pk=group.pk)
    else:
        form = RosterGroupForm(instance=group)
    return render(request, "roster/group_form.html", {"form": form, "group": group})


@login_required
@require_http_methods(["POST"])
def group_delete(request, pk):
    """Delete a group. Existing RACIAssignments that reference this group
    via source_group get SET_NULL — the assignment itself stays put on
    the project, only the 'via X Committee' annotation disappears."""
    group = get_object_or_404(RosterGroup, pk=pk)
    name = group.name
    group.delete()
    messages.success(request, f"Deleted {name}.")
    return redirect("roster:group_list")


@login_required
@require_http_methods(["POST"])
def group_member_add(request, pk):
    group = get_object_or_404(RosterGroup, pk=pk)
    person_id = request.POST.get("person", "").strip()
    if not person_id.isdigit():
        messages.error(request, "Please pick a person.")
        return redirect("roster:group_detail", pk=group.pk)
    person = get_object_or_404(RosterPerson, pk=int(person_id))
    if person.archived:
        messages.error(request, "Cannot add an archived person.")
        return redirect("roster:group_detail", pk=group.pk)
    _, created = GroupMembership.objects.get_or_create(group=group, person=person)
    if created:
        messages.success(request, f"Added {person.name} to {group.name}.")
    else:
        messages.info(request, f"{person.name} is already a member.")
    return redirect("roster:group_detail", pk=group.pk)


@login_required
@require_http_methods(["POST"])
def group_member_remove(request, pk):
    """Remove a membership row by its own pk (NOT the group/person pks)."""
    membership = get_object_or_404(GroupMembership, pk=pk)
    group_pk = membership.group_id
    name = membership.person.name
    membership.delete()
    messages.success(request, f"Removed {name} from the group.")
    return redirect("roster:group_detail", pk=group_pk)
