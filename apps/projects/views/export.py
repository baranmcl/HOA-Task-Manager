"""CSV export of the project list.

Reuses the list view's filter helper so the export respects whatever
filters are currently active. The column shape is a superset of the
import CSV's accepted columns — exports can be round-tripped through
the import view as long as multi-value fields (multiple Responsible
people, etc.) are pared down to single values first.
"""
import csv
import datetime as dt
from collections import defaultdict
from io import StringIO

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse

from ..models import RACIRole
from .project_list import apply_list_filters

# UTF-8 BOM — without it, Excel opens CSVs interpreting the bytes as
# Windows-1252 and mangles any non-ASCII characters in titles, names,
# vendor names, etc. The 3-byte prefix is the universal "this file is
# UTF-8" signal Excel respects.
UTF8_BOM = "﻿"

# Column order in the output. Names match the import CSV where the same
# concept exists (title, category, description, status, priority,
# projected_completion_date, budget_amount, vendor_name, vendor_bid_amount,
# responsible), so a board user can edit-then-reimport in the common
# single-Responsible-person case. The extra columns the import doesn't
# accept are ignored at import time with a warning.
EXPORT_COLUMNS = [
    "project_id",
    "title",
    "category",
    "description",
    "status",
    "priority",
    "projected_completion_date",
    "actual_completion_date",
    "budget_amount",
    "actual_cost",
    "vendor_name",
    "vendor_bid_amount",
    "tags",
    "responsible",
    "accountable",
    "consulted",
    "informed",
    "checklist_total",
    "checklist_completed",
    "note_count",
    "attachment_count",
    "created_at",
    "created_by",
]


def _format_date(d):
    if d is None:
        return ""
    return d.isoformat()


def _format_datetime(d):
    if d is None:
        return ""
    return d.strftime("%Y-%m-%d %H:%M:%S")


def _format_decimal(d):
    if d is None:
        return ""
    return str(d)


def _project_row(project):
    """Build a CSV row dict for a single project.

    Aggregates RACI assignments by role and joins names with semicolons
    so multi-person roles fit on one line per project. Tags get the same
    treatment.
    """
    by_role: dict[str, list[str]] = defaultdict(list)
    for a in project.raci_assignments.all():
        by_role[a.role].append(a.person.name)

    tag_names = [t.name for t in project.tags.all()]

    items = list(project.checklist_items.all())
    checklist_total = len(items)
    checklist_completed = sum(1 for i in items if i.completed)

    return {
        "project_id": project.pk,
        "title": project.title,
        "category": project.category.name if project.category_id else "",
        "description": project.description,
        "status": project.get_status_display(),
        "priority": project.get_priority_display(),
        "projected_completion_date": _format_date(project.projected_completion_date),
        "actual_completion_date": _format_date(project.actual_completion_date),
        "budget_amount": _format_decimal(project.budget_amount),
        "actual_cost": _format_decimal(project.actual_cost),
        "vendor_name": project.vendor_name,
        "vendor_bid_amount": _format_decimal(project.vendor_bid_amount),
        "tags": "; ".join(tag_names),
        "responsible": "; ".join(by_role.get(RACIRole.RESPONSIBLE, [])),
        "accountable": "; ".join(by_role.get(RACIRole.ACCOUNTABLE, [])),
        "consulted": "; ".join(by_role.get(RACIRole.CONSULTED, [])),
        "informed": "; ".join(by_role.get(RACIRole.INFORMED, [])),
        "checklist_total": checklist_total,
        "checklist_completed": checklist_completed,
        "note_count": getattr(project, "note_count", project.notes.count()),
        "attachment_count": getattr(
            project, "attachment_count", project.attachments.count(),
        ),
        "created_at": _format_datetime(project.created_at),
        "created_by": project.created_by.email if project.created_by else "",
    }


@login_required
def export_csv(request):
    """Stream a CSV of the currently-filtered project list.

    Same query params as the list view (status, category, person, role,
    tag, q, due, sort, show_completed, plus the dashboard-tile shortcuts
    overdue / upcoming / completed_this_month). The filename includes
    today's date so successive exports don't overwrite each other on
    the user's machine.
    """
    qs, _ = apply_list_filters(request)
    qs = qs.prefetch_related(
        "raci_assignments__person",
        "tags",
        "checklist_items",
    ).annotate(
        note_count=Count("notes", distinct=True),
        attachment_count=Count("attachments", distinct=True),
    )

    buf = StringIO()
    buf.write(UTF8_BOM)
    writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    for project in qs:
        writer.writerow(_project_row(project))

    today = dt.date.today().isoformat()
    filename = f"hoa-projects-{today}.csv"
    response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
