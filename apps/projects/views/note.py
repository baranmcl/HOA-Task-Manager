from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import UpdateNoteForm
from ..models import Project, UpdateNote


def _render_card(request, note):
    return render(request, "projects/_note_card.html", {
        "n": note, "project": note.project,
    })


def _render_notes_list(request, project):
    return render(request, "projects/_notes_list_swap.html", {"project": project})


@login_required
@require_http_methods(["POST"])
def note_add(request, pk):
    project = get_object_or_404(Project, pk=pk)
    form = UpdateNoteForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest(", ".join(form.errors.get("body", [])))
    note = form.save(commit=False)
    note.project = project
    note.author = request.user
    note.save()
    return _render_notes_list(request, project)


@login_required
def note_edit(request, pk):
    note = get_object_or_404(UpdateNote, pk=pk)
    return render(request, "projects/_note_edit_form.html", {
        "n": note, "project": note.project,
    })


@login_required
def note_show(request, pk):
    note = get_object_or_404(UpdateNote, pk=pk)
    return _render_card(request, note)


@login_required
@require_http_methods(["POST"])
def note_save(request, pk):
    note = get_object_or_404(UpdateNote, pk=pk)
    form = UpdateNoteForm(request.POST, instance=note)
    if not form.is_valid():
        return HttpResponseBadRequest(", ".join(form.errors.get("body", [])))
    form.save()
    return _render_card(request, note)
