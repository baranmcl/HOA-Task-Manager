from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import RecurringTemplateForm
from ..models import Project


@login_required
def recurring_list(request):
    templates = Project.templates.select_related("category").order_by("title")
    return render(request, "projects/recurring_list.html", {"templates": templates})


@login_required
def recurring_create(request):
    if request.method == "POST":
        form = RecurringTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.is_recurring_template = True
            template.created_by = request.user
            template.save()
            messages.success(request, "Recurring template created.")
            return redirect("projects:recurring_list")
    else:
        form = RecurringTemplateForm()
    return render(request, "projects/recurring_form.html", {"form": form, "template": None})


@login_required
def recurring_edit(request, pk):
    template = get_object_or_404(Project, pk=pk, is_recurring_template=True)
    if request.method == "POST":
        form = RecurringTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved.")
            return redirect("projects:recurring_list")
    else:
        form = RecurringTemplateForm(instance=template)
    return render(request, "projects/recurring_form.html", {"form": form, "template": template})


@login_required
def recurring_toggle(request, pk):
    if request.method != "POST":
        return redirect("projects:recurring_list")
    template = get_object_or_404(Project, pk=pk, is_recurring_template=True)
    template.is_active = not template.is_active
    template.save()
    verb = "Resumed" if template.is_active else "Paused"
    messages.success(request, f"{verb} {template.title}")
    return redirect("projects:recurring_list")
