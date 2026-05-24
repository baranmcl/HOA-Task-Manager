"""Bulk import view: form -> preview-in-session -> confirm."""
import datetime as dt
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render

from ..models import ActivityLog, Project, RACIAssignment, RACIRole
from ..services.csv_import import parse_csv
from ..signals import set_actor

SESSION_KEY = "pending_csv_import"


@login_required
def import_form(request):
    if request.method != "POST":
        return render(request, "projects/import_form.html")

    upload = request.FILES.get("file")
    if upload is None:
        return render(request, "projects/import_form.html", {
            "error": "Please choose a CSV file to upload.",
        })

    try:
        valid, rejected, warnings = parse_csv(upload)
    except ValueError as e:
        return render(request, "projects/import_form.html", {
            "error": str(e),
        })

    request.session[SESSION_KEY] = {
        "valid": [_row_to_session(r) for r in valid],
    }
    request.session.modified = True

    return render(request, "projects/import_preview.html", {
        "valid_rows": valid,
        "rejected_rows": rejected,
        "warnings": warnings,
    })


@login_required
def import_confirm(request):
    if request.method != "POST":
        return redirect("projects:import_form")

    pending = request.session.pop(SESSION_KEY, None)
    if not pending or not pending.get("valid"):
        return redirect("projects:import_form")

    rows = pending["valid"]
    created_count = 0

    # Silence the auto-activity-log signal so the bulk import writes a
    # single tidy "imported via CSV" entry per project instead of two
    # entries ("created project" + "added RACI assignment") per row.
    set_actor(None)
    try:
        with transaction.atomic():
            for serialized in rows:
                project = _project_from_session_row(serialized, request.user)
                project.save()
                if serialized.get("responsible_id"):
                    RACIAssignment.objects.create(
                        project=project,
                        person_id=serialized["responsible_id"],
                        role=RACIRole.RESPONSIBLE,
                    )
                ActivityLog.objects.create(
                    actor=request.user, project=project, verb="imported via CSV",
                    after_value={"title": project.title},
                )
                created_count += 1
    except Exception:
        messages.error(request, "Import failed, please try again.")
        return redirect("projects:import_form")
    finally:
        set_actor(request.user)

    messages.success(request, f"Imported {created_count} project(s).")
    return redirect("projects:list")


@login_required
def import_template(request):
    body = (
        "title,category,description,status,priority,projected_completion_date,"
        "budget_amount,vendor_name,vendor_bid_amount,responsible\n"
        "Sprinkler repair,Landscaping,Replace zone 3 valve,not_started,medium,"
        "2026-07-15,1200.00,Acme Sprinklers,1100.00,Jane Doe\n"
    )
    response = HttpResponse(body, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="project-import-template.csv"'
    return response


def _row_to_session(row):
    return {
        "title": row["title"],
        "category_id": row["category"].pk,
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "projected_completion_date": (
            row["projected_completion_date"].isoformat()
            if row["projected_completion_date"] else None
        ),
        "budget_amount": (
            str(row["budget_amount"]) if row["budget_amount"] is not None else None
        ),
        "vendor_name": row["vendor_name"],
        "vendor_bid_amount": (
            str(row["vendor_bid_amount"]) if row["vendor_bid_amount"] is not None else None
        ),
        "responsible_id": row["responsible"].pk if row["responsible"] else None,
    }


def _project_from_session_row(s, user):
    return Project(
        title=s["title"],
        category_id=s["category_id"],
        description=s["description"],
        status=s["status"],
        priority=s["priority"],
        projected_completion_date=(
            dt.date.fromisoformat(s["projected_completion_date"])
            if s["projected_completion_date"] else None
        ),
        budget_amount=Decimal(s["budget_amount"]) if s["budget_amount"] else None,
        vendor_name=s["vendor_name"],
        vendor_bid_amount=Decimal(s["vendor_bid_amount"]) if s["vendor_bid_amount"] else None,
        created_by=user,
    )
