from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import UpdateNoteForm
from ..models import Project


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
    return render(request, "projects/_notes_list_swap.html", {"project": project})
