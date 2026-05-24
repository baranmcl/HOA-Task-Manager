# Kanban Board View — Design

**Date:** 2026-05-24

## Goal

A `/projects/board/` page that shows projects as cards arranged in columns
by status. Drag a card from one column to another and the status updates
server-side. Built for visibility at board meetings and for one-glance
scanning of in-flight work.

## Columns

Three columns by default: **Not started**, **In progress**, **Delayed**.

A "Show completed" checkbox (mirroring the existing project list page)
adds a fourth **Completed** column. Hidden by default because the
dashboard already handles "done this month".

## Cards

Each card shows, top to bottom:

- A small priority dot (red/amber/grey) matching the project list page.
- The project title, linked to the detail page.
- The Responsible person (one line, truncated). "—" if none.
- The due date, with overdue dates in red.

Click the title to open the project page (normal navigation). Drag
anywhere else on the card to move it.

## Drag-and-drop interaction

Uses **Sortable.js** (CDN, ~10KB, no build step). Each column is a
sortable list; cards drop between them.

On drop, the JS:

1. Reads the target column's `data-status`.
2. If target is `delayed`, prompts the user for a delay reason via
   `window.prompt`. If they cancel or enter empty, the card snaps back.
3. POSTs to the existing `/projects/<pk>/inline/status/save/` endpoint
   with `status` (+ `delay_reason` if delayed). Reuses the existing
   inline-save view because it already implements all the validation
   (including the "delayed needs a reason" rule).
4. On a non-2xx response, the JS reverts the move and shows an alert
   with the response text.
5. The response body (an HTML partial of the field) is discarded — the
   card is already in the right column visually.

The activity log fires automatically via the existing status-change
signal, so dragging a card produces a real audit entry with the actor.

## Filters

A single `?person=<id>` filter, mirroring the dashboard. Default is
"All people". No category/tag filters in v1; the user can add them
later if the board gets too crowded.

## URL & sidebar

- New URL: `/projects/board/`, name `projects:board`.
- New sidebar link: **Board**, placed between **Calendar** and **Recurring**.

## What's intentionally out of scope

- WIP limits per column.
- Saved filtered views.
- Drag to reorder within a column (no `display_order` field on Project).
- Inline edit of fields other than status from the card.
- Mobile drag — Sortable.js handles touch, but small screens will be
  cramped. Mobile users should keep using the list page.

## Testing

`apps/projects/tests/test_views_board.py`:

- Login gate.
- Page renders with three columns by default; fourth appears with
  `?show_completed=1`.
- Projects appear in the correct column based on status.
- Recurring templates are excluded (`Project.instances`).
- `?person=<id>` filter scopes the board.
- "All people" sentinel works (matches dashboard/calendar pattern).
- Sidebar contains the "Board" link.

Drag-and-drop itself isn't unit-tested (would need Playwright). The
`status_save` endpoint that handles the POST is already covered.
