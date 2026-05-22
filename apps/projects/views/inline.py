import datetime as dt
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..models import Project, ProjectPriority, ProjectStatus


def _render_field(request, project, partial: str):
    return render(request, f"projects/{partial}", {"project": project})


@login_required
def status_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    return render(request, "projects/_field_status_edit.html", {
        "project": project, "status_choices": ProjectStatus.choices,
    })


@login_required
@require_http_methods(["POST"])
def status_save(request, pk):
    project = get_object_or_404(Project, pk=pk)
    new_status = request.POST.get("status", "")
    if new_status not in dict(ProjectStatus.choices):
        return HttpResponseBadRequest("Invalid status")
    delay_reason = request.POST.get("delay_reason", "").strip()
    if new_status == ProjectStatus.DELAYED and not delay_reason:
        return HttpResponseBadRequest("delay_reason is required")
    project.status = new_status
    if new_status == ProjectStatus.DELAYED:
        project.delay_reason = delay_reason
    project.save()
    return _render_field(request, project, "_field_status.html")


@login_required
def priority_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    return render(request, "projects/_field_priority_edit.html", {
        "project": project, "priority_choices": ProjectPriority.choices,
    })


@login_required
@require_http_methods(["POST"])
def priority_save(request, pk):
    project = get_object_or_404(Project, pk=pk)
    new_priority = request.POST.get("priority", "")
    if new_priority not in dict(ProjectPriority.choices):
        return HttpResponseBadRequest("Invalid priority")
    project.priority = new_priority
    project.save()
    return _render_field(request, project, "_field_priority.html")


@login_required
def dates_edit(request, pk):
    return render(request, "projects/_field_dates_edit.html", {
        "project": get_object_or_404(Project, pk=pk),
    })


@login_required
@require_http_methods(["POST"])
def dates_save(request, pk):
    project = get_object_or_404(Project, pk=pk)
    raw = request.POST.get("projected_completion_date", "").strip()
    if raw:
        try:
            project.projected_completion_date = dt.date.fromisoformat(raw)
        except ValueError:
            return HttpResponseBadRequest("Invalid date")
    else:
        project.projected_completion_date = None
    project.save()
    return _render_field(request, project, "_field_dates.html")


def _parse_decimal(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return "INVALID"


@login_required
def budget_edit(request, pk):
    return render(request, "projects/_field_budget_edit.html", {
        "project": get_object_or_404(Project, pk=pk),
    })


@login_required
@require_http_methods(["POST"])
def budget_save(request, pk):
    project = get_object_or_404(Project, pk=pk)
    b = _parse_decimal(request.POST.get("budget_amount", ""))
    a = _parse_decimal(request.POST.get("actual_cost", ""))
    if b == "INVALID" or a == "INVALID":
        return HttpResponseBadRequest("Invalid amount")
    project.budget_amount = b
    project.actual_cost = a
    project.save()
    return _render_field(request, project, "_field_budget.html")


@login_required
def vendor_edit(request, pk):
    return render(request, "projects/_field_vendor_edit.html", {
        "project": get_object_or_404(Project, pk=pk),
    })


@login_required
@require_http_methods(["POST"])
def vendor_save(request, pk):
    project = get_object_or_404(Project, pk=pk)
    project.vendor_name = request.POST.get("vendor_name", "").strip()
    bid = _parse_decimal(request.POST.get("vendor_bid_amount", ""))
    if bid == "INVALID":
        return HttpResponseBadRequest("Invalid amount")
    project.vendor_bid_amount = bid
    project.save()
    return _render_field(request, project, "_field_vendor.html")


@login_required
def status_show(request, pk):
    return _render_field(request, get_object_or_404(Project, pk=pk), "_field_status.html")


@login_required
def priority_show(request, pk):
    return _render_field(request, get_object_or_404(Project, pk=pk), "_field_priority.html")


@login_required
def dates_show(request, pk):
    return _render_field(request, get_object_or_404(Project, pk=pk), "_field_dates.html")


@login_required
def budget_show(request, pk):
    return _render_field(request, get_object_or_404(Project, pk=pk), "_field_budget.html")


@login_required
def vendor_show(request, pk):
    return _render_field(request, get_object_or_404(Project, pk=pk), "_field_vendor.html")
