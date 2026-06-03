"""Checklist views — HTMX-driven inline add/check/edit/delete.

Pattern mirrors the existing inline editors (status, priority, etc.):
each action returns a small partial that the calling template swaps in.
When the LAST remaining incomplete item is checked, the partial also
emits a JS confirm() that asks "Mark project as Completed?" — if the
user accepts, an HTMX POST fires to flip the project's status. Pure
opt-in; the user can dismiss without consequence.
"""
import datetime as dt

from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import ChecklistItem, Project, ProjectStatus


def _render_section(request, project, just_completed_last=False):
    """Re-render the whole checklist section.

    `just_completed_last` is set to True when the most recent action
    flipped the final incomplete item to completed — the template uses
    it to emit a prompt-and-confirm flow for marking the project done.
    """
    items = project.checklist_items.all()
    return render(request, "projects/_checklist_section.html", {
        "project": project,
        "items": items,
        "just_completed_last": just_completed_last,
    })


def _was_last_incomplete_item(project, item):
    """True iff `item` is now completed AND no other incomplete items
    remain for the project (and there's at least one item total)."""
    if not item.completed:
        return False
    return (
        project.checklist_items.count() >= 1
        and not project.checklist_items.filter(completed=False).exists()
    )


@login_required
@require_http_methods(["POST"])
def checklist_add(request, pk):
    project = get_object_or_404(Project, pk=pk)
    text = request.POST.get("text", "").strip()
    if not text:
        return HttpResponseBadRequest("Checklist item text is required.")
    if len(text) > 200:
        return HttpResponseBadRequest("Text is longer than 200 characters.")

    due_raw = request.POST.get("due_date", "").strip()
    due_date = None
    if due_raw:
        try:
            due_date = dt.date.fromisoformat(due_raw)
        except ValueError:
            return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD.")

    # Order: append. Use max(order)+1 so future drag-reorder works.
    last_order = project.checklist_items.aggregate(
        max_order=Max("order"),
    )["max_order"] or 0
    ChecklistItem.objects.create(
        project=project, text=text, due_date=due_date, order=last_order + 1,
    )
    return _render_section(request, project)


@login_required
@require_http_methods(["POST"])
def checklist_toggle(request, pk):
    """Flip completed on or off. Stamps completed_at/_by when going to
    True; clears them when going back to False."""
    item = get_object_or_404(ChecklistItem, pk=pk)
    project = item.project
    item.completed = not item.completed
    if item.completed:
        item.completed_at = timezone.now()
        item.completed_by = request.user
    else:
        item.completed_at = None
        item.completed_by = None
    item.save()

    just_done = _was_last_incomplete_item(project, item)
    return _render_section(request, project, just_completed_last=just_done)


@login_required
@require_http_methods(["POST"])
def checklist_delete(request, pk):
    item = get_object_or_404(ChecklistItem, pk=pk)
    project = item.project
    item.delete()
    return _render_section(request, project)


@login_required
@require_http_methods(["POST"])
def checklist_mark_project_complete(request, pk):
    """Used by the 'all items complete — mark project done?' prompt.
    Flips the project's status to COMPLETED. The Project.save() hook
    sets actual_completion_date automatically."""
    project = get_object_or_404(Project, pk=pk)
    project.status = ProjectStatus.COMPLETED
    project.save()
    return _render_section(request, project)
