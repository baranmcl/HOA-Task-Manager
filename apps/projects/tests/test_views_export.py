"""Tests for the project list CSV export."""
import csv
import datetime as dt
import io
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.projects.models import (
    ChecklistItem,
    Project,
    ProjectPriority,
    ProjectStatus,
    RACIAssignment,
    RACIRole,
    Tag,
)
from apps.roster.models import RosterPerson


def _read_csv(response):
    """Strip the BOM (if present), return a list of dict rows."""
    body = response.content.decode("utf-8")
    if body.startswith("﻿"):
        body = body[1:]
    return list(csv.DictReader(io.StringIO(body)))


@pytest.mark.django_db
def test_export_requires_login(client):
    response = client.get(reverse("projects:export_csv"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_export_returns_csv_content_type(auth_client):
    response = auth_client.get(reverse("projects:export_csv"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")


@pytest.mark.django_db
def test_export_filename_has_today_date(auth_client):
    response = auth_client.get(reverse("projects:export_csv"))
    disposition = response["Content-Disposition"]
    today = dt.date.today().isoformat()
    assert today in disposition
    assert "hoa-projects-" in disposition


@pytest.mark.django_db
def test_export_starts_with_utf8_bom(auth_client):
    response = auth_client.get(reverse("projects:export_csv"))
    # Excel needs the BOM to recognize the file as UTF-8.
    assert response.content.startswith("﻿".encode())


@pytest.mark.django_db
def test_export_header_row_has_expected_columns(auth_client):
    response = auth_client.get(reverse("projects:export_csv"))
    rows = _read_csv(response)
    # Even with no projects, the DictReader should report fieldnames.
    body = response.content.decode("utf-8").lstrip("﻿")
    reader = csv.reader(io.StringIO(body))
    header = next(reader)
    for required in [
        "project_id", "title", "category", "description", "status",
        "priority", "projected_completion_date", "actual_completion_date",
        "budget_amount", "actual_cost", "vendor_name", "vendor_bid_amount",
        "tags", "responsible", "accountable", "consulted", "informed",
        "checklist_total", "checklist_completed",
        "note_count", "attachment_count",
        "created_at", "created_by",
    ]:
        assert required in header, f"Missing column: {required}"
    assert rows == []


@pytest.mark.django_db
def test_export_one_row_per_project(auth_client, user, category):
    Project.objects.create(title="P1", category=category, created_by=user)
    Project.objects.create(title="P2", category=category, created_by=user)
    Project.objects.create(title="P3", category=category, created_by=user)
    response = auth_client.get(reverse("projects:export_csv"))
    rows = _read_csv(response)
    assert len(rows) == 3
    assert {r["title"] for r in rows} == {"P1", "P2", "P3"}


@pytest.mark.django_db
def test_export_respects_status_filter(auth_client, user, category):
    Project.objects.create(
        title="Active", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
    )
    Project.objects.create(
        title="Stuck", category=category, created_by=user,
        status=ProjectStatus.DELAYED, delay_reason="vendor",
    )
    response = auth_client.get(reverse("projects:export_csv") + "?status=in_progress")
    titles = [r["title"] for r in _read_csv(response)]
    assert titles == ["Active"]


@pytest.mark.django_db
def test_export_respects_overdue_shortcut(auth_client, user, category):
    today = dt.date.today()
    Project.objects.create(
        title="Late", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today - dt.timedelta(days=2),
    )
    Project.objects.create(
        title="Future", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today + dt.timedelta(days=2),
    )
    response = auth_client.get(reverse("projects:export_csv") + "?overdue=1")
    titles = [r["title"] for r in _read_csv(response)]
    assert titles == ["Late"]


@pytest.mark.django_db
def test_export_includes_completed_when_show_completed_set(auth_client, user, category):
    Project.objects.create(title="Active", category=category, created_by=user)
    Project.objects.create(
        title="Done", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    response = auth_client.get(reverse("projects:export_csv") + "?show_completed=1")
    titles = {r["title"] for r in _read_csv(response)}
    assert titles == {"Active", "Done"}


@pytest.mark.django_db
def test_export_excludes_completed_by_default(auth_client, user, category):
    Project.objects.create(title="Active", category=category, created_by=user)
    Project.objects.create(
        title="Done", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    response = auth_client.get(reverse("projects:export_csv"))
    titles = {r["title"] for r in _read_csv(response)}
    assert titles == {"Active"}


@pytest.mark.django_db
def test_export_aggregates_raci_by_role(auth_client, user, category):
    project = Project.objects.create(title="P", category=category, created_by=user)
    mike = RosterPerson.objects.create(name="Mike Smith")
    laurel = RosterPerson.objects.create(name="Laurel Baran")
    paul = RosterPerson.objects.create(name="Paul Stone")
    RACIAssignment.objects.create(project=project, person=mike, role=RACIRole.RESPONSIBLE)
    RACIAssignment.objects.create(project=project, person=laurel, role=RACIRole.RESPONSIBLE)
    RACIAssignment.objects.create(project=project, person=paul, role=RACIRole.ACCOUNTABLE)

    response = auth_client.get(reverse("projects:export_csv"))
    rows = _read_csv(response)
    row = rows[0]
    # Multiple Responsibles → semicolon-joined.
    assert "Mike Smith" in row["responsible"]
    assert "Laurel Baran" in row["responsible"]
    assert "; " in row["responsible"]
    # Single Accountable → just the name, no separator.
    assert row["accountable"] == "Paul Stone"
    # Empty roles → empty string.
    assert row["consulted"] == ""
    assert row["informed"] == ""


@pytest.mark.django_db
def test_export_joins_tags_with_semicolons(auth_client, user, category):
    project = Project.objects.create(title="P", category=category, created_by=user)
    project.tags.add(Tag.get_or_create_from_input("Roof"))
    project.tags.add(Tag.get_or_create_from_input("Vendor RFP"))
    response = auth_client.get(reverse("projects:export_csv"))
    row = _read_csv(response)[0]
    assert "Roof" in row["tags"]
    assert "Vendor RFP" in row["tags"]
    assert "; " in row["tags"]


@pytest.mark.django_db
def test_export_includes_checklist_counts(auth_client, user, category):
    project = Project.objects.create(title="P", category=category, created_by=user)
    ChecklistItem.objects.create(project=project, text="Step 1", order=0, completed=True)
    ChecklistItem.objects.create(project=project, text="Step 2", order=1, completed=True)
    ChecklistItem.objects.create(project=project, text="Step 3", order=2)
    response = auth_client.get(reverse("projects:export_csv"))
    row = _read_csv(response)[0]
    assert row["checklist_total"] == "3"
    assert row["checklist_completed"] == "2"


@pytest.mark.django_db
def test_export_dates_in_iso_format(auth_client, user, category):
    project = Project.objects.create(
        title="P", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 8, 15),
    )
    Project.objects.filter(pk=project.pk).update(
        actual_completion_date=dt.date(2026, 8, 20),
    )
    response = auth_client.get(reverse("projects:export_csv"))
    row = _read_csv(response)[0]
    assert row["projected_completion_date"] == "2026-08-15"
    assert row["actual_completion_date"] == "2026-08-20"


@pytest.mark.django_db
def test_export_decimals_unformatted(auth_client, user, category):
    """Money columns come out as bare decimal strings — Excel parses
    them as numbers, downstream tools (CPAs, BI) get a clean type."""
    Project.objects.create(
        title="P", category=category, created_by=user,
        budget_amount=Decimal("1234.56"),
        actual_cost=Decimal("999.00"),
        vendor_bid_amount=Decimal("1100.50"),
    )
    response = auth_client.get(reverse("projects:export_csv"))
    row = _read_csv(response)[0]
    assert row["budget_amount"] == "1234.56"
    assert row["actual_cost"] == "999.00"
    assert row["vendor_bid_amount"] == "1100.50"
    # No $ sign or thousands separators.
    assert "$" not in row["budget_amount"]


@pytest.mark.django_db
def test_export_status_and_priority_are_human_labels(auth_client, user, category):
    """The display labels (e.g. 'In progress', 'High') are what board
    users expect to see in a spreadsheet — not the raw db values."""
    Project.objects.create(
        title="P", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        priority=ProjectPriority.HIGH,
    )
    response = auth_client.get(reverse("projects:export_csv"))
    row = _read_csv(response)[0]
    assert row["status"] == "In progress"
    assert row["priority"] == "High"


@pytest.mark.django_db
def test_export_handles_commas_and_quotes_in_text(auth_client, user, category):
    """csv.DictWriter is supposed to escape, but verifying our pipeline
    actually round-trips the punctuation is cheap insurance against
    future changes that might introduce raw string formatting."""
    Project.objects.create(
        title='Tricky, "quoted" title',
        description="With\na newline.",
        category=category, created_by=user,
    )
    response = auth_client.get(reverse("projects:export_csv"))
    rows = _read_csv(response)
    assert len(rows) == 1
    assert rows[0]["title"] == 'Tricky, "quoted" title'
    assert "newline" in rows[0]["description"]


@pytest.mark.django_db
def test_export_unicode_characters_survive(auth_client, user, category):
    """The point of the UTF-8 BOM. A title with a curly quote or em-dash
    should land in Excel unmangled."""
    Project.objects.create(
        title="Bistré — façade — naïveté",
        category=category, created_by=user,
    )
    response = auth_client.get(reverse("projects:export_csv"))
    row = _read_csv(response)[0]
    assert row["title"] == "Bistré — façade — naïveté"


@pytest.mark.django_db
def test_list_page_includes_export_button(auth_client):
    response = auth_client.get(reverse("projects:list"))
    content = response.content.decode()
    assert "Export CSV" in content
    assert reverse("projects:export_csv") in content


@pytest.mark.django_db
def test_export_button_preserves_filter_query_params(auth_client):
    """If user is filtered to in_progress, the Export CSV link they see
    should carry that filter forward — otherwise a click downloads the
    unfiltered set and surprises them."""
    response = auth_client.get(reverse("projects:list") + "?status=in_progress")
    content = response.content.decode()
    # The export link's href should include status=in_progress.
    assert reverse("projects:export_csv") + "?status=in_progress" in content
