# Restoring the database from an R2 backup

The HOA Task Manager backs up `db.sqlite3` to R2 daily under
`db-backups/YYYY-MM-DD.sqlite3` (30-day retention). This runbook walks
through restoring from one of those backups.

**Do this when:** the live DB is corrupted, missing, or has bad data that
needs to be rolled back to a prior day's state.

**Estimated time:** 10 minutes.

---

## 1. Pick which backup to restore

In the [Cloudflare R2 dashboard](https://dash.cloudflare.com), open the
HOA Task Manager bucket → `db-backups/`. Each object is a daily snapshot
named `YYYY-MM-DD.sqlite3`. Pick the most recent one that predates the
problem you're recovering from.

(Alternative: in the PythonAnywhere Bash console,
`python manage.py shell -c "from apps.accounts.backup import list_backup_keys; print('\n'.join(list_backup_keys()))"`
will print the list.)

## 2. Download the chosen file

In the R2 dashboard, click the object's row → **Download**. Save it
locally. Don't rename it.

## 3. Upload to PythonAnywhere

On the PythonAnywhere **Files** tab, navigate to `/home/CICA/HOA-Task-Manager/`.
Click **Upload a file** and select the `.sqlite3` you downloaded.

## 4. Replace the live DB

In the PythonAnywhere Bash console:

```bash
cd ~/HOA-Task-Manager

# ALWAYS back up the current DB first — in case the restore is wrong.
cp db.sqlite3 "db.sqlite3.PRE-RESTORE-$(date -u +%Y%m%dT%H%M%SZ)"

# Replace. Use the actual filename you uploaded.
mv 2026-05-23.sqlite3 db.sqlite3
```

## 5. Reload the web app

On the PythonAnywhere **Web** tab, click **Reload cica.pythonanywhere.com**.

## 6. Verify

Open the app in your browser and confirm:
- You can log in.
- The Projects list shows the data you expect for the restored date.
- The Dashboard activity feed shows activity up to the restore date.

## 7. Clean up

Once you've confirmed the restore is good, delete the `PRE-RESTORE-*` file
in the next backup window (give it a couple of days first in case you
need to undo the restore):

```bash
cd ~/HOA-Task-Manager
ls -la db.sqlite3.PRE-RESTORE-*
rm db.sqlite3.PRE-RESTORE-<timestamp>   # only after you're sure
```

---

## Troubleshooting

- **"OperationalError: database is locked" after restore.** Reload the
  Web tab again — a stale connection can hold the old file open.
- **App loads but shows the wrong data.** Double-check the date of the
  file you uploaded. The filename is the snapshot's date in UTC.
- **R2 dashboard doesn't show recent backups.** Check the Account page —
  the "Last backup" panel will show when the most recent attempt ran and
  whether it errored.

## Notes

- **Backups roll daily at the first web request after UTC midnight.** If
  you need a backup of the current moment (not just yesterday's snapshot),
  run `python manage.py backup_database` from the Bash console first.
- **The PRE-RESTORE file is your safety net.** Keep it for at least one
  business day in case the restore turns out to be the wrong choice.
