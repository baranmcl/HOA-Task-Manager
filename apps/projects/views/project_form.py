from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import ProjectForm
from ..models import Project, RACIAssignment, RACIRole


def _has_financial_data(project):
    """True when the project already has any budget/vendor value set."""
    return bool(
        project.budget_amount is not None
        or project.actual_cost is not None
        or project.vendor_name
        or project.vendor_bid_amount is not None
    )


@login_required
def create(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            form.save_m2m_with_tags(project)
            responsible = form.cleaned_data.get("initial_responsible")
            if responsible:
                RACIAssignment.objects.create(
                    project=project,
                    person=responsible,
                    role=RACIRole.RESPONSIBLE,
                )
            messages.success(request, "Project created.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = ProjectForm()
    return render(request, "projects/form.html", {
        "form": form,
        "project": None,
        "financial_section_open": False,
    })


@login_required
def edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            form.save_m2m_with_tags(project)
            messages.success(request, "Saved.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, "projects/form.html", {
        "form": form,
        "project": project,
        "financial_section_open": _has_financial_data(project),
    })
