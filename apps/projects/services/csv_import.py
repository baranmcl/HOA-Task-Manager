"""Pure-function CSV parser for bulk project import.

Returns three lists:
- valid_rows: dicts with already-resolved FK objects and parsed primitives.
- rejected_rows: dicts with row_number, the raw row, and an error string.
- warnings: human-readable strings about unknown columns.

The parser does NOT write to the DB. The view layer constructs Project
rows from valid_rows on confirmation.
"""
import csv
import datetime as dt
import io
from decimal import Decimal, InvalidOperation

from apps.projects.models import ProjectCategory, ProjectPriority, ProjectStatus
from apps.roster.models import RosterPerson

REQUIRED_COLUMNS = {"title", "category"}
KNOWN_COLUMNS = {
    "title", "category", "description", "status", "priority",
    "projected_completion_date", "budget_amount", "vendor_name",
    "vendor_bid_amount", "responsible",
}

_STATUS_LOOKUP = {}
for value, label in ProjectStatus.choices:
    _STATUS_LOOKUP[value.lower()] = value
    _STATUS_LOOKUP[label.lower()] = value

_PRIORITY_LOOKUP = {}
for value, label in ProjectPriority.choices:
    _PRIORITY_LOOKUP[value.lower()] = value
    _PRIORITY_LOOKUP[label.lower()] = value


class _RowError(ValueError):
    pass


def parse_csv(file_obj):
    raw = file_obj.read()
    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig")
    else:
        text = raw

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV is missing a header row.")

    normalized_headers = [h.strip().lower() for h in reader.fieldnames]
    reader.fieldnames = normalized_headers

    missing = REQUIRED_COLUMNS - set(normalized_headers)
    if missing:
        raise ValueError(
            f"CSV is missing required column(s): {', '.join(sorted(missing))}."
        )

    warnings = []
    unknown = set(normalized_headers) - KNOWN_COLUMNS
    if unknown:
        warnings.append(
            "Ignoring unknown column(s): " + ", ".join(sorted(unknown))
        )

    categories_by_name = {
        c.name.lower(): c for c in ProjectCategory.objects.all()
    }
    people_by_name = {
        p.name.lower(): p for p in RosterPerson.active.all()
    }

    valid_rows = []
    rejected_rows = []

    for i, raw_row in enumerate(reader, start=2):
        if all((v or "").strip() == "" for v in raw_row.values()):
            continue
        try:
            parsed = _parse_row(raw_row, categories_by_name, people_by_name)
        except _RowError as e:
            rejected_rows.append({
                "row_number": i,
                "raw": dict(raw_row),
                "error": str(e),
            })
            continue
        valid_rows.append(parsed)

    return valid_rows, rejected_rows, warnings


def _parse_row(raw, categories_by_name, people_by_name):
    title = (raw.get("title") or "").strip()
    if not title:
        raise _RowError("Title is required.")
    if len(title) > 200:
        raise _RowError("Title is longer than 200 characters.")

    category_name = (raw.get("category") or "").strip()
    if not category_name:
        raise _RowError("Category is required.")
    category = categories_by_name.get(category_name.lower())
    if category is None:
        raise _RowError(f"Unknown category: {category_name}")

    out = {
        "title": title,
        "category": category,
        "description": (raw.get("description") or "").strip(),
        "vendor_name": (raw.get("vendor_name") or "").strip(),
    }

    status_raw = (raw.get("status") or "").strip()
    if status_raw:
        status = _STATUS_LOOKUP.get(status_raw.lower())
        if status is None:
            raise _RowError(f"Unknown status: {status_raw}")
        out["status"] = status
    else:
        out["status"] = ProjectStatus.NOT_STARTED

    priority_raw = (raw.get("priority") or "").strip()
    if priority_raw:
        priority = _PRIORITY_LOOKUP.get(priority_raw.lower())
        if priority is None:
            raise _RowError(f"Unknown priority: {priority_raw}")
        out["priority"] = priority
    else:
        out["priority"] = ProjectPriority.MEDIUM

    date_raw = (raw.get("projected_completion_date") or "").strip()
    if date_raw:
        out["projected_completion_date"] = _parse_date(date_raw)
    else:
        out["projected_completion_date"] = None

    budget_raw = (raw.get("budget_amount") or "").strip()
    if budget_raw:
        out["budget_amount"] = _parse_money(budget_raw, field="budget_amount")
    else:
        out["budget_amount"] = None

    bid_raw = (raw.get("vendor_bid_amount") or "").strip()
    if bid_raw:
        out["vendor_bid_amount"] = _parse_money(bid_raw, field="vendor_bid_amount")
    else:
        out["vendor_bid_amount"] = None

    responsible_raw = (raw.get("responsible") or "").strip()
    if responsible_raw:
        person = people_by_name.get(responsible_raw.lower())
        if person is None:
            raise _RowError(f"Unknown person: {responsible_raw}")
        out["responsible"] = person
    else:
        out["responsible"] = None

    return out


def _parse_date(raw):
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    parts = raw.split("/")
    if len(parts) == 3:
        try:
            m, d, y = (int(p) for p in parts)
            return dt.date(y, m, d)
        except ValueError:
            pass
    raise _RowError(f"Unrecognized date format: {raw}")


def _parse_money(raw, *, field):
    cleaned = raw.replace("$", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation as e:
        raise _RowError(f"Unrecognized {field} value: {raw}") from e
