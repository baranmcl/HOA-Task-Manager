"""Tests for the pure-function CSV parser."""
import datetime as dt
import io
from decimal import Decimal

import pytest

from apps.projects.models import ProjectPriority, ProjectStatus
from apps.projects.services.csv_import import parse_csv
from apps.roster.models import RosterPerson


def _f(text: str) -> io.BytesIO:
    return io.BytesIO(text.encode("utf-8"))


@pytest.mark.django_db
def test_parse_csv_happy_path(category):
    text = f"title,category,priority\nSprinkler upgrade,{category.name},high\n"
    valid, rejected, warnings = parse_csv(_f(text))
    assert rejected == []
    assert warnings == []
    assert len(valid) == 1
    row = valid[0]
    assert row["title"] == "Sprinkler upgrade"
    assert row["category"].pk == category.pk
    assert row["priority"] == ProjectPriority.HIGH


@pytest.mark.django_db
def test_parse_csv_header_case_insensitive(category):
    text = f"Title,CATEGORY\nFoo,{category.name.upper()}\n"
    valid, rejected, _ = parse_csv(_f(text))
    assert len(valid) == 1
    assert valid[0]["title"] == "Foo"
    assert valid[0]["category"].pk == category.pk


@pytest.mark.django_db
def test_parse_csv_unknown_category_rejects_row(category):
    text = "title,category\nFoo,Nonexistent Category\n"
    valid, rejected, _ = parse_csv(_f(text))
    assert valid == []
    assert len(rejected) == 1
    assert "Unknown category" in rejected[0]["error"]
    assert rejected[0]["row_number"] == 2


@pytest.mark.django_db
def test_parse_csv_unknown_person_rejects_row(category):
    text = f"title,category,responsible\nFoo,{category.name},Ghost Person\n"
    valid, rejected, _ = parse_csv(_f(text))
    assert valid == []
    assert "Unknown person" in rejected[0]["error"]


@pytest.mark.django_db
def test_parse_csv_resolves_responsible_person(category):
    person = RosterPerson.objects.create(name="Jane Doe")
    text = f"title,category,responsible\nFoo,{category.name},Jane Doe\n"
    valid, rejected, _ = parse_csv(_f(text))
    assert rejected == []
    assert valid[0]["responsible"].pk == person.pk


@pytest.mark.django_db
def test_parse_csv_responsible_match_case_insensitive(category):
    person = RosterPerson.objects.create(name="Jane Doe")
    text = f"title,category,responsible\nFoo,{category.name},jane doe\n"
    valid, _, _ = parse_csv(_f(text))
    assert valid[0]["responsible"].pk == person.pk


@pytest.mark.django_db
def test_parse_csv_archived_person_does_not_match(category):
    RosterPerson.objects.create(name="Jane Doe", archived=True)
    text = f"title,category,responsible\nFoo,{category.name},Jane Doe\n"
    valid, rejected, _ = parse_csv(_f(text))
    assert valid == []
    assert "Unknown person" in rejected[0]["error"]


@pytest.mark.django_db
def test_parse_csv_date_iso_format(category):
    text = f"title,category,projected_completion_date\nFoo,{category.name},2026-07-15\n"
    valid, _, _ = parse_csv(_f(text))
    assert valid[0]["projected_completion_date"] == dt.date(2026, 7, 15)


@pytest.mark.django_db
def test_parse_csv_date_excel_format(category):
    text = f"title,category,projected_completion_date\nFoo,{category.name},7/15/2026\n"
    valid, _, _ = parse_csv(_f(text))
    assert valid[0]["projected_completion_date"] == dt.date(2026, 7, 15)


@pytest.mark.django_db
def test_parse_csv_invalid_date_rejects_row(category):
    text = f"title,category,projected_completion_date\nFoo,{category.name},not-a-date\n"
    _, rejected, _ = parse_csv(_f(text))
    assert "date" in rejected[0]["error"].lower()


@pytest.mark.django_db
def test_parse_csv_currency_style_budget(category):
    text = f'title,category,budget_amount\nFoo,{category.name},"$1,200.00"\n'
    valid, _, _ = parse_csv(_f(text))
    assert valid[0]["budget_amount"] == Decimal("1200.00")


@pytest.mark.django_db
def test_parse_csv_invalid_budget_rejects_row(category):
    text = f"title,category,budget_amount\nFoo,{category.name},notanumber\n"
    _, rejected, _ = parse_csv(_f(text))
    assert "budget" in rejected[0]["error"].lower()


@pytest.mark.django_db
def test_parse_csv_blank_optional_fields_ok(category):
    text = f"title,category,description,priority\nFoo,{category.name},,\n"
    valid, rejected, _ = parse_csv(_f(text))
    assert rejected == []
    assert valid[0]["description"] == ""
    assert valid[0]["priority"] == ProjectPriority.MEDIUM


@pytest.mark.django_db
def test_parse_csv_status_human_label_accepted(category):
    text = f"title,category,status\nFoo,{category.name},In progress\n"
    valid, _, _ = parse_csv(_f(text))
    assert valid[0]["status"] == ProjectStatus.IN_PROGRESS


@pytest.mark.django_db
def test_parse_csv_invalid_status_rejects_row(category):
    text = f"title,category,status\nFoo,{category.name},flerbgled\n"
    _, rejected, _ = parse_csv(_f(text))
    assert "status" in rejected[0]["error"].lower()


@pytest.mark.django_db
def test_parse_csv_unknown_column_warns_but_imports(category):
    text = f"title,category,notes\nFoo,{category.name},some scratch text\n"
    valid, rejected, warnings = parse_csv(_f(text))
    assert rejected == []
    assert len(valid) == 1
    assert any("notes" in w for w in warnings)


def test_parse_csv_empty_file_raises():
    with pytest.raises(ValueError, match="header"):
        parse_csv(_f(""))


@pytest.mark.django_db
def test_parse_csv_no_data_rows_returns_empty():
    valid, rejected, _ = parse_csv(_f("title,category\n"))
    assert valid == []
    assert rejected == []


def test_parse_csv_missing_required_column_raises():
    with pytest.raises(ValueError, match="title"):
        parse_csv(_f("category\nFoo\n"))


@pytest.mark.django_db
def test_parse_csv_blank_title_rejects_row(category):
    text = f"title,category\n,{category.name}\n"
    _, rejected, _ = parse_csv(_f(text))
    assert "title" in rejected[0]["error"].lower()


@pytest.mark.django_db
def test_parse_csv_utf8_bom_tolerated(category):
    text = f"﻿title,category\nFoo,{category.name}\n"
    valid, rejected, _ = parse_csv(_f(text))
    assert rejected == []
    assert valid[0]["title"] == "Foo"


@pytest.mark.django_db
def test_parse_csv_trailing_blank_rows_ignored(category):
    text = f"title,category\nFoo,{category.name}\n,\n,\n"
    valid, rejected, _ = parse_csv(_f(text))
    assert len(valid) == 1
    assert rejected == []
