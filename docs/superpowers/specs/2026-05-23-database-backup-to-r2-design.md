# HOA Task Manager — Database Backup to R2 — Design

**Date:** 2026-05-23
**Author:** Project owner (Baran) + Claude
**Status:** Draft for owner review

---

## 1. Background

Today the application's data lives entirely in one SQLite file (`db.sqlite3`)
on the PythonAnywhere account's filesystem. There is no automated backup. If
the file is corrupted, the account is suspended, or someone accidentally
`rm`'s it from a Bash console, every project, note, RACI assignment, and
activity log is gone. The owner has explicitly named "losing data" as the
biggest risk going forward.

R2 (Cloudflare's object storage) is already configured for project
attachments — credentials and bucket are in the env (`R2_*` settings). That
same bucket gives us a durable, off-platform destination for database
backups at effectively zero cost.

PythonAnywhere's free tier has no cron, so the backup is fired by the same
"first request of the day" middleware trick that powers
`RecurringGenerationMiddleware`. Traffic-triggered, no scheduler needed.

## 2. Scope

**In scope:** automated daily backup of `db.sqlite3` to R2, 30-day retention,
a management command for manual on-demand backups, a documented restore
runbook, and tests.

**Out of scope:**
- Backing up R2-stored attachments. R2 is the source of truth for those;
  duplicating it inside R2 is silly, and backing R2 to a different cloud
  is engineering effort disproportionate to the threat model.
- Encryption of the backup file beyond R2's server-side encryption.
- Automated restore. Restoring is rare and high-stakes; we want a human
  reading a runbook, not a script that could clobber live data.
- Off-cloud backup destinations. R2 free tier is 10 GB; even at 30 MB per
  backup × 30 days, we use 900 MB. Plenty of room.

## 3. Architecture

### Trigger — `BackupMiddleware`

A new middleware in `apps/accounts/middleware.py` (alongside the timezone
middleware) modeled on `RecurringGenerationMiddleware`:

```python
class BackupMiddleware:
    """Runs the database backup once per day, lazily.

    PythonAnywhere's free tier has no scheduled tasks, so the backup is
    triggered by the first web request of each day. The backup is idempotent
    within a day (the BackupLog row prevents re-runs).
    """
    def __call__(self, request):
        self._maybe_backup()
        return self.get_response(request)
```

The middleware:
1. Looks up today's `BackupLog` row by date; if it exists, returns immediately.
2. Otherwise, calls the backup command and writes the log row to mark it done.
3. Wraps the call in `try/except Exception` so a backup failure (R2 outage,
   credential issue, disk full) never breaks a web request — just emits a
   structured log entry and a `BackupLog.error` field.

Registered immediately after `TimezoneMiddleware`. Order matters: it must run
before `RecurringGenerationMiddleware` so a slow recurring-generation call
doesn't stall the backup, but after `AuthenticationMiddleware` (no auth
dependency, just ordering preference).

### Idempotency — `BackupLog` model

A new tiny model in `apps/accounts/models.py`:

```python
class BackupLog(models.Model):
    run_date = models.DateField(unique=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    bytes_uploaded = models.PositiveIntegerField(null=True, blank=True)
    object_key = models.CharField(max_length=200, blank=True)
    error = models.TextField(blank=True)
```

The `unique=True` on `run_date` prevents two requests on the same day from
both racing into a backup. The remaining fields are observability — when did
it run, how big was the file, what's the R2 key, was there an error.

### Backup operation — `backup_database.py` management command

A new command at `apps/accounts/management/commands/backup_database.py`:

```python
class Command(BaseCommand):
    def handle(self, *args, **options):
        date_str = dt.date.today().isoformat()
        object_key = f"db-backups/{date_str}.sqlite3"
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
            tmp_path = tmp.name
        # SQLite's backup API: safe under concurrent writes.
        src = sqlite3.connect(str(settings.DATABASES["default"]["NAME"]))
        dst = sqlite3.connect(tmp_path)
        with dst:
            src.backup(dst)
        src.close(); dst.close()
        # Upload via the same boto3-compatible client used for attachments.
        client = _r2_client()  # boto3.client("s3", endpoint_url=R2_ENDPOINT_URL, ...)
        client.upload_file(tmp_path, settings.R2_BUCKET, object_key)
        os.unlink(tmp_path)
        # Retention: delete db-backups/* objects older than 30 days.
        _prune_old_backups(client, settings.R2_BUCKET, keep_days=30)
        self.stdout.write(self.style.SUCCESS(f"Backed up {object_key}"))
```

Two reasons to keep this as a management command rather than inlining it in
the middleware:
- The middleware just orchestrates "should this run now?" The management
  command does the actual work, so it can be invoked manually from the Bash
  console (`python manage.py backup_database`) for on-demand backups.
- It mirrors the existing pattern (`generate_recurring_instances` is also a
  command called by middleware).

### Retention — `_prune_old_backups`

After a successful upload, list all keys under `db-backups/`, parse the
`YYYY-MM-DD` date from each, and delete any older than `today - 30 days`.
`list_objects_v2` + `delete_objects`, both standard boto3 calls.

### Local-dev safety

The middleware and command both short-circuit gracefully if any of
`R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` is
empty — the case for local development. In that case the `BackupLog` row is
written with an explanatory `error` field so dashboards still show a clean
status.

## 4. Data model changes

One new model in `apps/accounts/models.py`:

- `BackupLog(run_date unique, started_at, finished_at, bytes_uploaded, object_key, error)`

One auto-generated migration: `apps/accounts/migrations/0003_backuplog.py`.

No changes to existing models.

## 5. Storage layout (R2)

```
<R2_BUCKET>/
├── attachments/        ← existing, untouched
│   └── ...
└── db-backups/         ← new
    ├── 2026-05-23.sqlite3
    ├── 2026-05-24.sqlite3
    └── ...
```

A single date string per filename. One backup per day. No times because the
trigger is "first request of day" and there's only ever one.

## 6. Restore procedure

The runbook lives at `docs/runbooks/restore-database.md`:

1. **Identify** the backup to restore. From the Cloudflare R2 dashboard,
   navigate to the bucket → `db-backups/` and pick a date. Or run
   `python manage.py list_backups` from the PythonAnywhere console (small
   companion command listed under "Out of scope but easy" below).

2. **Download** the chosen file. From the Cloudflare R2 dashboard, click the
   object and Download. (No CLI step needed; the dashboard works fine.)

3. **Upload to PythonAnywhere.** On the **Files** tab, upload the downloaded
   `.sqlite3` to `~/HOA-Task-Manager/` (or any path).

4. **Replace the live DB.** In the Bash console:
   ```bash
   cd ~/HOA-Task-Manager
   # Always back up the current DB first, in case the restore is wrong.
   cp db.sqlite3 db.sqlite3.PRE-RESTORE-$(date +%Y%m%d-%H%M%S)
   mv 2026-05-23.sqlite3 db.sqlite3   # the file you just uploaded
   ```

5. **Reload** the Web tab. Verify the app loads, projects are visible, and the
   date/state matches the chosen backup.

6. **Clean up** the `.PRE-RESTORE-*` and any temp files after verifying the
   restore is good.

The runbook is also a checklist; checked in as a markdown file so it can be
updated, not lost in this design doc.

## 7. Error handling

- **R2 credentials missing** — Middleware writes `BackupLog(error="R2 not
  configured; backup skipped")` and continues. No exception raised; the local
  dev case is the canonical example.
- **R2 upload fails** (network error, auth error, rate limit) — Middleware
  catches the exception, writes `BackupLog(error=<exception text>)`, logs via
  `logger.exception(...)`, and continues. The next day's request retries.
- **SQLite backup fails** (rare — disk full, file locked) — Same handling.
- **Pruning fails** — Treated as non-fatal. The backup itself succeeded; the
  prune is a cleanup nicety. Logged but doesn't fail the run.
- **Two requests racing** within a millisecond on the day's first hit — the
  `unique=True` on `BackupLog.run_date` raises `IntegrityError` on the loser,
  caught and treated as "another request already started this; bail."

## 8. Observability

- `BackupLog` model is visible in the Django admin (register it).
- An Account-page section "**Last backup**" shows the most recent
  `BackupLog` row's date, size, and a green/red status. One row, four lines
  of HTML, no new view code beyond the existing `accounts.views.profile`.

## 9. Testing

- `BackupLog`: `run_date` unique constraint enforced.
- `BackupMiddleware`:
  - First call of the day triggers the backup (mocked); creates the log row.
  - Second call of the same day does nothing.
  - R2 credentials missing → log row written with `error` set; no crash.
  - R2 upload raises → log row written with `error`; request still succeeds.
- `backup_database` management command:
  - Successful end-to-end run uploads with the right object key
    (`db-backups/YYYY-MM-DD.sqlite3`), records bytes, calls prune.
  - SQLite `Connection.backup()` produces a file readable as a valid SQLite
    DB containing the test fixtures.
- `_prune_old_backups`:
  - Given a bucket listing with 35 daily backups and a 30-day retention,
    deletes exactly the 5 oldest.
- The Account-page "Last backup" panel renders the latest `BackupLog`.

All R2 calls are mocked via `moto` or a small custom fake — we do not hit
real R2 in tests.

## 10. Security

- R2 server-side encryption is enabled by default on the bucket.
- HTTPS in transit (boto3 default for `endpoint_url` with `https://`).
- `BackupLog.error` may contain raw exception text — confirm it never
  includes credentials. Boto3 exceptions don't normally embed credentials,
  but we'll truncate to 2000 chars defensively.
- The `db-backups/` prefix uses the same bucket as `attachments/`. If the
  bucket's access policy changes (e.g., made public), backups become
  exposed. The bucket is private today (confirmed during attachment setup);
  worth a one-line note in the runbook to re-verify after any R2 dashboard
  change.

## 11. Cost

- R2 storage: 10 GB free, $0.015/GB-month after. With 30 daily backups of
  ~10 MB each = 300 MB. Free for the foreseeable future.
- R2 egress: $0/byte within Cloudflare; no egress charge at this scale.
- R2 Class A operations (writes): 1M free/month. We do 1 PUT/day + N
  DELETEs (≤ 5/day during pruning). ~200/month. Free.
- R2 Class B operations (reads): 10M free/month. We do 1 LIST/day for
  pruning. ~30/month. Free.

**Total monthly cost: $0.**

## 12. Out of scope but easy follow-ups

- A `list_backups` management command (and matching CLI on the Account
  page) so the user can see what's in R2 without leaving the app.
- A `restore_database` management command. Tempting but **deliberately
  rejected**: restore should be a deliberate, human-paced operation with a
  pre-restore safety copy. Automating it raises the risk of accidental
  data loss without much human-time saved.
- A health check that pings the latest backup's age and alerts if >48h.
  Email alerts depend on the SMTP provider work that's queued separately.

## 13. Open decisions for owner sign-off

1. **30-day retention OK?** Could be 7, 14, 60, or 90. 30 is the default;
   tell me if you'd prefer shorter (less storage) or longer (more recovery
   distance).
2. **Backup time of day?** Locked to "first request after midnight UTC" by
   the middleware trigger. If you want it pinned to a different rollover
   time (e.g., midnight Central), I can do that with one timezone-aware
   check. Default: UTC midnight is fine; no perceptible user impact.
3. **Same bucket vs separate bucket?** Today's plan: same bucket as
   attachments, separate prefix (`db-backups/`). If you'd rather isolate
   them (a separate R2 bucket, separate access key), tell me — adds about
   10 minutes of Cloudflare-dashboard setup on your end.

If you're fine with the defaults on all three, no action needed — I'll
proceed straight to the plan and implementation.
