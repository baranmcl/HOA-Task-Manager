"""Bulk-delete view for the project list page.

Posts an `ids` list and a literal `confirm=delete` flag. The frontend
modal forces the user to type 'delete' before submitting; the view
re-verifies that flag server-side so a curl request can't bypass it.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseNotAllowed
from django.shortcuts import redirect

from ..models import ActivityLog, Project
from ..signals import set_actor


@login_required
def bulk_delete(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    if request.POST.get("confirm") != "delete":
        return HttpResponseBadRequest("Confirmation word required.")

    raw_ids = request.POST.getlist("ids")
    pks = [int(x) for x in raw_ids if x.isdigit()]
    if not pks:
        messages.info(request, "Nothing selected.")
        return redirect("projects:list")

    set_actor(None)
    try:
        with transaction.atomic():
            projects = list(Project.objects.filter(pk__in=pks))
            for p in projects:
                ActivityLog.objects.create(
                    actor=request.user, project=None, verb="deleted project",
                    before_value={"title": p.title},
                )
            Project.objects.filter(pk__in=pks).delete()
    finally:
        set_actor(request.user)

    messages.success(request, f"Deleted {len(projects)} project(s).")
    return redirect("projects:list")
