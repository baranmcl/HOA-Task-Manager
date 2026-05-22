# HOA Task Manager — Project Form & Category Management — Design

**Date:** 2026-05-22
**Author:** Project owner (Baran) + Claude
**Status:** Approved, ready for implementation planning

---

## 1. Background

Post-launch feedback after the first hands-on use of the project tracker
(Plan 2) on the PythonAnywhere staging site. Three UX refinements to the
project create/edit flow and to category management. No data-model changes —
all three are confined to the `projects` app's views, forms, templates, one
management command, and a small category-management page.

A separate, non-feature note: the project-creation blocker the user hit
("no category to choose") was simply that the `seed_categories` command had
not been run on the server. Running it loads the six standard categories.
That is an operational fix, not part of this design — but see Feature 1,
which adds "Misc" to that seed list.

## 2. Feature 1 — Category management page

A new in-app page for managing `ProjectCategory` records, so the owner can
add and remove categories without using the Django admin.

**Location:** linked from the **Account** page as "Manage project
categories". The main sidebar is left uncluttered — category management is a
rare-touch task. (A top-level sidebar link is a trivial later change if
desired.)

**Page contents** (styled consistently with the existing Roster page —
reuses the `.btn`, `.input`, `.pill`, and table styling already in the app):

- A table of all categories, each row showing the category name and a count
  of projects currently using it.
- An inline "+ Add category" form: a name field; submitting creates a
  `ProjectCategory` with `display_order` set to the current maximum + 1.
- **Rename:** each row allows editing the category name (fixes a typo
  without a delete-and-recreate dance).
- **Delete:** permitted only when **0 projects** reference the category.
  `Project.category` is a `ForeignKey(on_delete=PROTECT)`, so an in-use
  category cannot be deleted. An in-use row shows "in use by N project(s)"
  in place of a delete control.

**Seed change:** the `seed_categories` management command gains a seventh
entry, **"Misc"** (`display_order` 7). The command is already idempotent
(`get_or_create` on name), so re-running it on an existing install adds only
Misc and leaves the original six untouched.

All category-page views require login (`@login_required`), consistent with
the rest of the app's flat single-role auth.

## 3. Feature 2 — Collapsible "Budget & vendor details" on the project form

The four financial/vendor fields — `budget_amount`, `actual_cost`,
`vendor_name`, `vendor_bid_amount` — are already optional (none required).
This change declutters the create/edit form by grouping them inside a native
HTML `<details>` element with the summary **"Budget & vendor details
(optional)"**.

- **New Project form:** the section is **collapsed** by default.
- **Edit Project form:** the section is rendered **open** (`<details open>`)
  when the project already has *any* of the four values set — so opening an
  edit form never appears to have lost existing data.
- The view passes a boolean context flag (e.g. `financial_section_open`)
  computed from the bound `Project` instance; on the create form it is
  always `False`.
- No JavaScript — `<details>` is native, keyboard-accessible HTML.

## 4. Feature 3 — Delay reason appears only when relevant

The **Delay reason** field is shown only when **Status = Delayed**.

- A small vanilla-JavaScript snippet (a file under `static/js/`, loaded by
  the form template) toggles the visibility of the delay-reason field's
  container: it runs on page load and on every `change` event of the status
  `<select>`, showing the container only when the selected value is
  `delayed`.
- The existing server-side rule is **unchanged**: `ProjectForm.clean()`
  still requires `delay_reason` when status is `delayed`.
- Progressive enhancement: with JavaScript disabled, the field is simply
  always visible — no functional breakage, the server rule still holds.

## 5. Data model

**No schema changes.** `ProjectCategory` already exists (Plan 2). Adding
"Misc" is a change to the *seed command's data*, not the schema — no
migration. None of the three features alters a model.

## 6. Components & files (approximate)

- **New:** a category-management view module, its template, URL routes, and
  tests; a small JavaScript file for the delay-reason toggle.
- **Modified:** `seed_categories.py` (+Misc); `ProjectForm` / the project
  `form.html` (the `<details>` grouping + the delay-reason hook); the
  project form view (the `financial_section_open` flag); the Account
  template (the "Manage project categories" link); `apps/projects/urls.py`
  (category-page routes).

## 7. Error handling

- **Add category:** a blank name, or a name that duplicates an existing
  category, is rejected with an inline form error (`ProjectCategory.name` is
  unique).
- **Delete an in-use category:** the UI does not offer delete for in-use
  categories. As a defensive backstop, the delete view catches
  `ProtectedError` and returns a friendly message rather than a 500.
- **Delay reason:** server-side requirement when status is delayed is
  unchanged and remains the source of truth.

## 8. Testing

- **Category page:** add a category; rename a category; delete an unused
  category; deleting an in-use category is blocked; the list shows correct
  per-category project counts.
- **`seed_categories`:** now seeds seven categories including Misc; still
  idempotent on re-run.
- **Form:** the budget/vendor `<details>` is collapsed on the create form
  and open on an edit form for a project that has financial data; the
  server-side `delay_reason`-required-when-delayed rule still passes its
  tests.
- **Delay-reason JS:** the toggle behavior itself is browser-side and not
  unit-tested; a test instead asserts the form renders the status field and
  the delay-reason container with the id/class hooks the script targets, so
  a regression that removes the hook is caught.

## 9. Out of scope

- **Category reordering** (editing `display_order` from the panel) — the
  Django admin can do it in the rare case it is needed.
- **Soft-archive of categories** — categories are not historical records the
  way roster people are; hard delete (when unused) is sufficient.
- **The project detail page's budget/vendor display** — the owner chose the
  form-only treatment for the collapsible section; the detail page is
  unchanged.
