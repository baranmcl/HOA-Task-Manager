# Switching back to Fly.io from PythonAnywhere

**Status: ✅ COMPLETED on 2026-06-03.** Staging now runs on Fly. This
runbook is retained as a record of how the cutover happened and as a
fallback reference if we ever need to do it again.

This runbook walks through migrating the running staging app from
PythonAnywhere back to Fly.io. The Fly infrastructure has been retained
in this repo continuously since the original switch — see
`docs/runbooks/deploy-pythonanywhere.md` for context — so the work here
is mostly configuration restoration, not new implementation.

**One deviation from the runbook in practice (2026-06-03):** The
documented SFTP upload step (Part 3 step 3) failed on the operator's
local network — `flyctl ssh sftp` couldn't complete the WireGuard
WebSocket handshake to `dfw2.gateway.6pn.dev`, returning
`tls: first record does not look like a TLS handshake`. The workaround
was to upload the DB to R2 via the Cloudflare dashboard, then
have the container's entrypoint download it on boot via a new
`RESTORE_FROM_R2_KEY` env var hook (see entrypoint.sh). This hook is
retained as a permanent disaster-recovery mechanism. To use it for
future restores: upload a backup to R2, `fly secrets set
RESTORE_FROM_R2_KEY=<key>`, wait for the auto-restart, then
`fly secrets unset RESTORE_FROM_R2_KEY` to prevent re-overwriting on
subsequent restarts.

**When to do this:** When the friction of PythonAnywhere's manual deploy,
virtualenv activation, or CPU-second limits outweighs the $0 baseline,
and roughly $2-3/month for proper PaaS infra feels worth it.

**Estimated time:** 30-60 minutes, mostly waiting for the Fly machine
to provision and the first deploy to complete.

**Cost:** ~$2-3/month for one `shared-cpu-1x` machine + a 1 GB volume.

---

## Pre-flight checklist

- [ ] You have a Fly.io account with billing set up (a card on file).
      Sign up at https://fly.io/app/sign-up if needed.
- [ ] You have `flyctl` (the Fly CLI) installed locally.
      Mac/Linux: `curl -L https://fly.io/install.sh | sh`
      Windows: `iwr https://fly.io/install.ps1 -useb | iex`
- [ ] You've authenticated: `fly auth login`
- [ ] You have a recent backup of the staging DB downloaded locally.
      Either:
      - From the Cloudflare R2 dashboard, download today's
        `db-backups/YYYY-MM-DD.sqlite3`, **OR**
      - From PythonAnywhere's Files tab, download `db.sqlite3` directly.

---

## Part 1 — Recreate the Fly app

- [ ] **1. Check whether the old Fly app still exists.**

```bash
fly apps list | grep hoa
```

If the app appears (likely named `hoa-task-manager` or similar from the
original setup), it was retained — skip to step 3. If it doesn't appear,
it was destroyed when the trial ended — continue to step 2.

- [ ] **2. (Re)create the app if needed.**

From the repo root:

```bash
fly launch --no-deploy --copy-config
```

This reads `fly.toml`, prompts you to confirm the app name, region, and
volume. Accept the defaults from the existing `fly.toml`. The
`--no-deploy` flag stops it from immediately deploying — we want to set
secrets first.

If `fly launch` complains the volume already exists, that's fine — it
means the old volume is still there with your data on it.

- [ ] **3. Create the persistent volume (only if `fly launch` didn't already).**

```bash
fly volumes create hoa_data --size 1 --region <your-region>
```

Use the same region listed in `fly.toml` (e.g. `iad` for US East).
1 GB is plenty for the SQLite DB at this scale.

---

## Part 2 — Restore secrets

Fly stores secrets as env vars on the app. The list of secrets the app
needs (from `config/settings.py`):

```bash
fly secrets set \
  DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
  DJANGO_DEBUG=False \
  DJANGO_ALLOWED_HOSTS="*" \
  DJANGO_CSRF_TRUSTED_ORIGINS="https://hoa-task-manager.fly.dev" \
  R2_ENDPOINT_URL="<from-cloudflare>" \
  R2_ACCESS_KEY_ID="<from-cloudflare>" \
  R2_SECRET_ACCESS_KEY="<from-cloudflare>" \
  R2_BUCKET="<from-cloudflare>"
```

Replace `hoa-task-manager.fly.dev` with the actual hostname Fly assigns
(visible in the `fly launch` output or `fly info`).

For the R2 values: open the same Cloudflare R2 page that PythonAnywhere
points at — the bucket and credentials are reusable across both hosts.

You also need a superuser bootstrap on first boot. The existing
`entrypoint.sh` creates one from these env vars if they're set:

```bash
fly secrets set \
  DJANGO_SUPERUSER_USERNAME="baranmcl@gmail.com" \
  DJANGO_SUPERUSER_EMAIL="baranmcl@gmail.com" \
  DJANGO_SUPERUSER_PASSWORD="<pick a strong throwaway>"
```

You can rotate this password on first login from the **Account** page.

---

## Part 3 — Deploy and restore data

- [ ] **1. Deploy.**

```bash
fly deploy
```

The Docker image builds, pushes to Fly's registry, and the machine
boots. `entrypoint.sh` runs `migrate`, `collectstatic`, and
`createsuperuser` (idempotently). Watch the logs:

```bash
fly logs
```

You're looking for a final line like
`Listening at: http://0.0.0.0:8080`. Once it appears, open
`https://<app>.fly.dev` in a browser and confirm the login page loads.

- [ ] **2. Verify a clean install works end-to-end.**

Log in with the superuser credentials. The DB is fresh (post-migrate
only), so you'll see no projects, no roster. That's expected — the next
step restores the real data.

- [ ] **3. Upload the staging DB to Fly.**

Get a temporary shell with the volume mounted:

```bash
fly ssh sftp shell
```

In the SFTP shell:

```
put /local/path/to/db.sqlite3 /data/db.sqlite3
exit
```

The `/data/` path is the volume mount point defined in `fly.toml`.

- [ ] **4. Restart the machine to pick up the new DB.**

```bash
fly machine restart
```

Refresh the browser — you should now see your real projects, roster, and
RACI data.

---

## Part 4 — Re-enable auto-deploy

In [.github/workflows/deploy-staging.yml](.github/workflows/deploy-staging.yml),
change:

```yaml
on:
  workflow_dispatch:
```

to:

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
```

Also update the workflow's `name:` header from "Deploy to staging (Fly —
dormant)" to "Deploy to staging (Fly)". Commit and push:

```bash
git add .github/workflows/deploy-staging.yml
git commit -m "ops: re-enable Fly auto-deploy from main"
git push
```

The push itself triggers the first auto-deploy. Watch it on
`https://github.com/baranmcl/HOA-Task-Manager/actions`.

You'll need to set the `FLY_API_TOKEN` repo secret if it isn't already:
`fly auth token` prints the token; paste it at
GitHub → Settings → Secrets and variables → Actions → New repository
secret.

---

## Part 5 — Update docs to reflect the switch

- [ ] **1. Move PythonAnywhere from "active" to "dormant".**

Edit the top of `docs/runbooks/deploy-pythonanywhere.md` — flip the
opening paragraph to mirror what the Fly file currently says
(retained but dormant, see this file for the active host).

- [ ] **2. Mark this Fly-switch runbook as "completed".**

Add a "Switched: YYYY-MM-DD" line at the top of this file once the
cutover is done, and link back to the PythonAnywhere file for the
fallback path.

- [ ] **3. Update the memory file** so future sessions know which host is
      active. See `~/.claude/projects/.../memory/hoa-hosting-decision.md`.

---

## Part 6 — Shut down PythonAnywhere (optional)

If you want to keep PythonAnywhere as a warm fallback, do nothing —
it'll keep running until you stop renewing it monthly.

If you want to fully decommission it:

- [ ] **1. Stop the web app** — on the Web tab, click **Disable**.
- [ ] **2. Download a final copy of `db.sqlite3`** for archival.
- [ ] **3. The free account itself can sit dormant** — no recurring cost.
      Leaving it gives you a "go back" option if something goes wrong on
      Fly within the first week or two.

---

## What stays the same after the switch

- **R2 attachments and backups** — same bucket, same credentials, no
  data migration needed.
- **All application code** — zero changes.
- **The BackupMiddleware daily backup** — works identically on Fly.
  Once you're settled in, you could optionally replace it with a real
  Fly Machines scheduled task (cron-equivalent), but that's polish, not
  required.

## What changes after the switch

- Deploys: `git push` → done in 2 minutes (vs. manual 4-step on
  PythonAnywhere).
- No `workon hoa-venv` activation step ever again — Docker bakes it in.
- No monthly renewal click on the PythonAnywhere Web tab.
- No 100 CPU-second daily limit.
- Real shell access via `fly ssh console`.
- Monthly bill: ~$2-3.

---

## Troubleshooting

- **`fly deploy` fails with `unhealthy machine`** — check `fly logs`. The
  most common cause used to be migrations being run by `release_command`
  before the volume was mounted; this was fixed by moving migrations
  into `entrypoint.sh`. If you see SQLite "unable to open database file"
  errors, that change has regressed — restore the entrypoint-based
  migration step.
- **App loads but shows no data** — you probably skipped step 3 of
  Part 3 (SFTP upload of the DB). The machine has a fresh
  post-migrations DB; upload your real one and restart.
- **Cloudflare R2 returns 403 on attachments after the switch** — verify
  `R2_BUCKET` was set as a secret, not just as an env var in the
  Dockerfile. `fly secrets list` shows what's configured.
- **HTTPS redirects in a loop** — Fly handles HTTPS termination at its
  proxy; the app speaks HTTP internally. The `SECURE_PROXY_SSL_HEADER`
  setting in `config/settings.py` (`("HTTP_X_FORWARDED_PROTO", "https")`)
  is what tells Django to trust Fly's protocol header. If redirects
  loop, that setting got dropped.
