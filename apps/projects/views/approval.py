from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import BoardApprovalForm
from ..models import BoardApproval, Project


@login_required
def approval_add(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if hasattr(project, "board_approval"):
        return redirect("projects:approval_edit", pk=project.pk)
    if request.method == "POST":
        form = BoardApprovalForm(request.POST)
        if form.is_valid():
            approval = form.save(commit=False)
            approval.project = project
            approval.save()
            messages.success(request, "Board approval recorded.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = BoardApprovalForm()
    ctx = {"form": form, "project": project, "is_new": True}
    return render(request, "projects/approval_form.html", ctx)


@login_required
def approval_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    approval = get_object_or_404(BoardApproval, project=project)
    if request.method == "POST":
        form = BoardApprovalForm(request.POST, instance=approval)
        if form.is_valid():
            form.save()
            messages.success(request, "Approval updated.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = BoardApprovalForm(instance=approval)
    ctx = {"form": form, "project": project, "is_new": False}
    return render(request, "projects/approval_form.html", ctx)
