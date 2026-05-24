# CSV Bulk Import & Bulk Delete — Design

**Date:** 2026-05-23
**Status:** Draft for user review

## Goal

Let a board member paste an Excel export into the app and have it create projects in bulk — with minimal training, sane error messages, and a safe path to undo if a row was wrong. Also provide a bulk-delete escape hatch in case the import goes sideways.

## Audience

HOA board members. They will copy-paste from Excel/Google Sheets, not write CSV by hand. Translation: **be forgiving** about whitespace, header casing, blank trailing rows, and quote styles. Reject the file with a clear error if it's structurally broken; otherwise warn on per-row problems but commit the good rows.

## Non-goals

- No edit-by-CSV. Imports only create new projects; existing projects are edited through the normal UI.
- No round-trip CSV export of existing projects in this spec (covered by Item 3's reporting work).
- No background processing — the dataset is small (dozens of rows at a time). Synchronous request handling is fine.
- No M2M tag import. Tags are noisy and would slow adoption; can be added later if asked for.
- No RACI assignment beyond a single optional "Responsible" person — anything richer should be set via the UI.

## CSV columns

One header row, exact names (case-insensitive matching, leading/trailing whitespace stripped):

| Column | Required | Format | Notes |
|---|---|---|---|
| `title` | yes | text, ≤200 chars | The only truly required column. |
| `category` | yes | text, must match an existing `ProjectCategory.name` (case-insensitive) | Mismatch = row rejected with "Unknown category: X". We do NOT auto-create categories — that's an admin call. |
| `description` | no | text | |
| `status` | no | one of `not_started`, `in_progress`, `delayed`, `completed` (or the human label) | Default `not_started`. |
| `priority` | no | one of `high`, `medium`, `low` | Default `medium`. |
| `projected_completion_date` | no | `YYYY-MM-DD` or `M/D/YYYY` (Excel default) | Both accepted. |
| `budget_amount` | no | number, decimal | `$1,200.00` is tolerated — strip `$` and commas. |
| `vendor_name` | no | text | |
| `vendor_bid_amount` | no | number | Same tolerance as budget. |
| `responsible` | no | text, must match an existing `RosterPerson.name` (case-insensitive, active people only) | Mismatch = row rejected with "Unknown person: X". Sets a single RACI assignment with role=`responsible`. |

Unknown columns are ignored (with a warning shown after import). That way "Notes" or other Excel scratch columns don't break things.

## UI flow

Two new pages, both gated by `@login_required` (matching the rest of the app). No staff-only restriction for now — every logged-in board member can use this.

### 1. `/projects/import/`

A simple form page with:
- A file input that accepts `.csv` only.
- A "Download template" link that returns a 1-row example CSV with the header row and one example row of plausible HOA data. Saves the board from guessing the format.
- A short inline help block listing the required columns and the date format.

Submitting POSTs the file. The view parses it server-side and renders a **preview page** before any DB writes happen.

### 2. `/projects/import/preview/` (POST destination)

Shows what was parsed:
- A green table of valid rows (will be created) with the resolved category and responsible person.
- A red table of rejected rows with the row number and the per-row error message.
- A yellow "warnings" block for ignored unknown columns.
- A "Confirm import" button (submits valid rows to actually create them) and a "Cancel" link back to the form.

The preview holds the parsed rows in the session, not the DB, until confirmation. This keeps the flow simple — no temp-record cleanup if the user navigates away.

Confirming creates rows inside a single transaction. If a write fails mid-batch (e.g., a race condition where a category got deleted between preview and confirm), the whole batch is rolled back and the user sees an error. Activity log entries are created per project as if they had been created in the UI.

### 3. Sidebar entry

Add an "Import projects" link in the sidebar under the existing "Projects" section, below "Calendar". Reachable from any logged-in page.

## Bulk delete

Same logged-in gating. Approach: **filter-based deletion driven from the project list page**, not a separate page.

- Add checkboxes on each row in `projects/list.html` plus a "Select all" toggle.
- Add a "Delete selected" action button that appears only when ≥1 row is checked.
- Submitting opens a confirmation modal: shows the count and the list of titles, requires typing the word `delete` (lower case) into a confirmation input before the Delete button enables.
- POST `/projects/bulk-delete/` with the list of IDs. View deletes inside a transaction, logs an ActivityLog row per delete (verb: "deleted"), redirects back to the list with a success message.

Hard delete, not soft delete. The user's words were "I hopefully won't need it" — a soft-delete column would add complexity to every query for a feature meant to be rarely used. If they later regret a delete, they restore from backup.

## Error handling

- **File-level rejection** (no header row, no rows at all, unparseable CSV): show a single error on the import page, no preview screen.
- **Row-level rejection**: shown in the preview's red table with row number and reason; valid rows still get the chance to import.
- **Mid-batch DB failure**: full rollback, generic "Import failed, please try again" message; nothing partial gets committed.

## Testing strategy

Tests live in `apps/projects/tests/test_views_csv_import.py` and `apps/projects/tests/test_views_bulk_delete.py`. Each covers:

- **Import: happy path** — 3 valid rows, preview renders all 3, confirm creates 3 Project rows with the right field values, ActivityLog entries exist.
- **Import: header case-insensitive** — `Title,CATEGORY,Description` works.
- **Import: unknown category** — row rejected, reason rendered.
- **Import: unknown responsible person** — row rejected.
- **Import: invalid date format** — row rejected.
- **Import: currency-style budget `$1,200.00`** — parsed as `1200.00`.
- **Import: blank optional fields** — accepted, project saved with defaults.
- **Import: unknown extra column** — ignored, warning shown, rows still import.
- **Import: empty file / no header** — file-level rejection, no preview.
- **Import: requires login** — anonymous → 302.
- **Bulk delete: happy path** — 2 IDs deleted, ActivityLog entries exist, no other projects touched.
- **Bulk delete: typing the wrong confirmation word** — frontend gate; we'll have one server-side test that posting without the confirm flag returns a 400.
- **Bulk delete: requires login** — anonymous → 302.

## Implementation notes

- Use Python's stdlib `csv` module — no Pandas. Excel-CSV quirks (BOM, CRLF, double quotes) are handled by `csv.DictReader` plus `open(..., encoding='utf-8-sig')`.
- Hold the preview rows in `request.session["pending_import"]` as a JSON-serializable list. The session backend is already configured.
- Put the per-row parsing logic in `apps/projects/services/csv_import.py` (new module) — pure-function `parse_csv(file_obj) -> (valid_rows, rejected_rows, warnings)`. View is just glue. Keeps the parser independently testable.
- Bulk delete view also lives in `apps/projects/views/bulk.py` (new module). Both new URLs added to `apps/projects/urls.py`.

## Out of scope (parked, not done)

- Updating existing projects via CSV (use the UI).
- Tag/M2M import (low value for board adoption, easy to add later).
- Async/background processing (small file sizes don't justify Celery).
- Soft-delete with restore UI.
- Per-row CSV export from filtered list (lives in Item 3 reporting work).
