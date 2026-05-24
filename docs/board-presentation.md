# HOA Task Manager — for the Board

A short walkthrough of the tool I've been building to replace our ad-hoc
mix of spreadsheets, email chains, and "didn't we discuss this in April?"

---

## The problem we have today

Most of what the board does sits in three places:

- **Spreadsheets** — for tracking who owes what, project budgets, vendor quotes.
- **Email** — for context, decisions, attachments.
- **Memory** — for "wait, didn't Mike say he'd handle that?"

The spreadsheets get out of date. The email context is hard to find.
Memory is unreliable. Nobody knows what's overdue until something falls
through.

## What this is

A small web app, built for *us specifically*, that puts every HOA project
in one place — with:

- **A clear owner and a clear status.** Not "Mike, probably?" — *Mike is
  the Responsible party on this RACI assignment, and the project is
  In Progress, due May 30.*
- **The supporting context next to the work.** Vendor quotes attached
  directly to the project. Notes that read like a project diary. A pinned
  "what is this project" description anyone can read to catch up in 30
  seconds.
- **A dashboard that tells you what's on your plate.** Log in, see your
  overdue items, your upcoming items, your in-progress work — defaulted
  to *you specifically*, not a firehose of everyone's work.
- **An automatic record of who did what, when.** Every status change,
  budget update, and note edit is logged. "Who changed this and why?"
  becomes a one-click answer instead of an archaeology project.

## How you use it

### Step 1 — Log in

The board secretary creates your account; you set your password the
first time you log in. After that, it's bookmark-and-go.

### Step 2 — Set yourself up

Account page → pick your timezone, link your name to your roster entry.
That's it. Takes 30 seconds, once.

### Step 3 — Use the dashboard

Land on the dashboard. By default it shows **your** tasks:

- **Overdue** card with the red count means "something needs attention now."
- **Upcoming (14 days)** lists what's coming this week and next.
- **In progress** shows what you're actively working on.
- **Done this month** is the satisfying number that proves we got things done.

You can switch the "Showing tasks for" dropdown to see another board
member's work, or **All people** to see everything.

### Step 4 — Click into a project

Every project page shows:

- The basic facts (status, priority, dates, category, budget vs. actual).
- **RACI** — Responsible / Accountable / Consulted / Informed assignments.
  No more "I thought you were handling that."
- **Attachments** — vendor quotes, permit applications, photos.
- **Notes** — a living record of where the project stands. Pin one note
  as the "what is this project" anchor so any board member can catch up
  in 30 seconds. Add more notes as things happen. Edit or delete notes
  as needed (the system remembers original authorship).
- **Activity** — a system-generated audit log: "Mike changed status from
  Not Started to In Progress on May 14." Trust the audit, not memory.

### Step 5 — Add new projects, recurring or one-off

One-off project: click **New project**, fill in the form.

Recurring (e.g. "Monthly financial review"): create it once as a
template, the system generates a fresh instance automatically every
month with the same RACI and category preserved.

---

## Why this instead of a Google Sheet

I've tracked HOA stuff in sheets for years. Sheets are great for tabular
data and free, but they break down when the work involves:

| Need | Spreadsheet | This app |
|---|---|---|
| **Who's responsible** | A name in a cell that may or may not be current | Structured RACI; pick from the roster |
| **Project context** | Linked Google Docs, attached emails, memory | Pinned note + chronological log, all in one place |
| **Vendor quote PDFs** | "Check the shared drive folder" | Attached directly to the project |
| **Overdue / what's on my plate** | Sort and squint | Dashboard tells you on login |
| **"Who edited what, when?"** | Version history is per-cell and unreadable | Activity log shows every change with author and timestamp |
| **Recurring tasks** | Copy a row, forget for two months | Auto-generated on schedule |
| **Two people editing at once** | "Sorry, that cell is locked" | No conflict — everyone edits independently |
| **Mobile use** | Pinch-and-zoom hell | Responsive layout that works on a phone |

The Google Sheet is fine for the *list*. It's terrible for everything
*around* the list.

## Why this instead of paid project-management software

Asana, Monday, ClickUp, Trello, Wrike — all good products. They start
around **$10–30 per user per month**. For a five-person board, that's
**$600–1,800/year**, recurring forever.

For our use case, that money buys features we don't need (timelines,
gantt charts, dependencies, sprints, multi-team permissions) and forces
us to bend our workflow to theirs.

This tool costs us:

- **$0/month** for hosting (PythonAnywhere free tier).
- **Effectively $0/month** for file storage (Cloudflare R2 free tier
  covers more than we'll ever use).
- **A few minutes a year** for maintenance.

It also speaks *our* vocabulary — RACI roles, recurring board reviews,
HOA categories — instead of forcing us into generic "tasks" with
"assignees."

Bonus: we own the data. The database is backed up daily to encrypted
cloud storage. If we ever want to leave, the database is a single
portable file we control. Try doing that with Asana.

## What it doesn't do (yet)

Honest list:

- No email notifications yet. (Coming soon — daily digest of overdue
  items.)
- No calendar view. (Coming soon — visualize all due dates at once.)
- No board votes / formal approval workflows yet.
- No mobile app — but the web UI works on phones.

These are decisions, not omissions. I'm holding off on bells and
whistles until we're all *actually using the core* and know what we
actually want.

## What I'd like from you

Try it. The app is at **https://cica.pythonanywhere.com**. I'll set up
your account and email you a one-time link to choose a password.

Spend 10 minutes:

- Click into a project that involves you. Read the pinned note. See
  whose name is on the RACI.
- Add a note from your own perspective ("met with vendor today, quote
  attached"). Attach a file if you have one handy.
- Toggle the dashboard's "Showing tasks for" dropdown to **All people**
  and look at what's in flight across the board.

Then tell me what's missing or annoying. The whole point of building
this ourselves is that we can fix what bugs us.

---

*Built by Baran, May 2026. Source: <github.com/baranmcl/HOA-Task-Manager>.*
