from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RosterPersonForm
from .models import RosterPerson


@login_required
def list_view(request):
    show_archived = request.GET.get("show_archived") == "1"
    qs = RosterPerson.objects.all() if show_archived else RosterPerson.active.all()
    return render(request, "roster/list.html", {
        "people": qs,
        "show_archived": show_archived,
    })


@login_required
def detail(request, pk):
    person = get_object_or_404(RosterPerson, pk=pk)
    return render(request, "roster/detail.html", {"person": person})


@login_required
def create(request):
    if request.method == "POST":
        form = RosterPersonForm(request.POST)
        if form.is_valid():
            person = form.save()
            messages.success(request, f"Added {person.name}.")
            return redirect("roster:detail", pk=person.pk)
    else:
        form = RosterPersonForm()
    return render(request, "roster/form.html", {"form": form, "person": None})


@login_required
def edit(request, pk):
    person = get_object_or_404(RosterPerson, pk=pk)
    if request.method == "POST":
        form = RosterPersonForm(request.POST, instance=person)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved.")
            return redirect("roster:detail", pk=person.pk)
    else:
        form = RosterPersonForm(instance=person)
    return render(request, "roster/form.html", {"form": form, "person": person})


@login_required
def archive(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    person = get_object_or_404(RosterPerson, pk=pk)
    person.archived = True
    person.save()
    messages.success(request, f"Archived {person.name}.")
    return redirect("roster:list")


@login_required
def unarchive(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    person = get_object_or_404(RosterPerson, pk=pk)
    person.archived = False
    person.save()
    messages.success(request, f"Restored {person.name}.")
    return redirect("roster:detail", pk=person.pk)
