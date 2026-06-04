# Continuity plan — HOA Task Manager

This document exists so that, **if the original maintainer (McLean Baran)
disappears, leaves the HOA, or is otherwise unavailable**, a board
successor or a technically-savvy friend can keep the app running and
recover from breakage without prior context.

It's deliberately short. Detailed steps live in the runbooks under
[`docs/runbooks/`](docs/runbooks/) — this is the navigation layer.

**Last updated: 2026-06-03.** If you make changes that affect anything
listed here (rotated a credential, switched a host, etc.), update this
file in the same commit.

---

## Quick reference — accounts and services

The app depends on the following external accounts. **Logins for each
should be in a shared password vault** (e.g., 1Password / Bitwarden
family plan) accessible to at least two board members.

| Service | What it does | Approx. annual cost | Account holder (as of 2026-06-03) | Where to log in |
|---|---|---|---|---|
| **Fly.io** | Hosts the app at `tasks.cicahoa.com` | $30–60/yr | `baranmcl@gmail.com` | <https://fly.io/dashboard> |
| **Cloudflare R2** | Stores attachments + daily DB backups | $0 (free tier) | `baranmcl@gmail.com` | <https://dash.cloudflare.com> |
| **Resend** | Sends transactional emails (password resets, invites) | $0 (free tier) | `baranmcl@gmail.com` | <https://resend.com> |
| **Squarespace Domains** | Holds the `cicahoa.com` domain registration | ~$12/yr | **A board member (NOT McLean)** — see "Known risks" | <https://account.squarespace.com> |
| **Google Workspace** | Provides `@cicahoa.com` mailboxes | $6/mailbox/month | Same board member as Squarespace | <https://admin.google.com> |
| **GitHub** | Source code; CI/CD pipeline | $0 | `baranmcl` | <https://github.com/baranmcl/HOA-Task-Manager> |
| **PythonAnywhere** | **Dormant fallback host.** Account preserved, web app disabled. | $0 (free tier) | `baranmcl@gmail.com`, username `cica` | <https://www.pythonanywhere.com> |

**If any password vault credential goes missing**, every service above
supports email-based account recovery — but recovery is only possible
if the recovery email itself is accessible. **The Gmail address
`baranmcl@gmail.com` is the recovery anchor for everything above except
Squarespace and Google Workspace.**

---

## Architecture in 30 seconds

- **App code:** Django 5 + Python 3.12. Source on GitHub. Tests run in
  CI on every push.
- **Hosting:** A single Fly.io machine in the `iad` region, with a 1 GB
  persistent volume for the SQLite database. Auto-stops when idle;
  wakes on the first HTTP request.
- **Custom domain:** `tasks.cicahoa.com` is a CNAME (in Squarespace's
  DNS panel) pointing at `hoa-task-manager-staging.fly.dev`. Fly
  manages the Let's Encrypt TLS cert; renewal is automatic.
- **Storage:** SQLite for everything except file attachments and daily
  database backups, which go to Cloudflare R2 (S3-compatible).
- **Email:** Outbound mail uses Resend's HTTPS API via the
  `django-anymail` library. The sender domain `cicahoa.com` is
  verified at Resend with SPF, DKIM, and DMARC DNS records — those
  live alongside the CNAME in Squarespace's DNS panel.
- **Deploy pipeline:** Push to `main` on GitHub → GitHub Actions builds
  a Docker image → pushes to Fly's registry → rolls the machine onto
  it. About 60 seconds from push to live.

For diagrams or deeper architecture explanation, the source code is the
authoritative reference. Start with `config/settings.py` and
`apps/projects/models/`.

---

## Common scenarios

### "I need to deploy a code change"

1. Commit and push to `main`.
2. Watch the deploy workflow at
   <https://github.com/baranmcl/HOA-Task-Manager/actions> — should go
   green in ~1 minute.
3. Verify at <https://tasks.cicahoa.com/>.

If the auto-deploy fails (red workflow run): expand the failed step in
Actions to see the error. Most likely cause is an expired
`FLY_API_TOKEN` — see [`docs/runbooks/switch-back-to-fly.md`](docs/runbooks/switch-back-to-fly.md)
for how to generate a fresh one.

### "I want to invite a new board member"

Log in → sidebar → **Invite user** (visible to staff users only) →
enter their email. They'll get an activation link by email; clicking it
lets them set their own password.

### "I want to make someone else a staff user (admin)"

There's no UI for this yet — must be done via the Django admin:
1. Log in to <https://tasks.cicahoa.com/admin/> with a superuser account.
2. **Users** → click the target user.
3. Check **Staff status** and (if they need full admin) **Superuser status**.
4. Save.

### "I forgot my password"

"Forgot password?" link on the sign-in page. You'll receive a reset
link by email. Link expires in 3 days.

### "The site is down"

1. Check Fly's status dashboard: <https://status.fly.io>.
2. Check the app's health from the Fly dashboard:
   <https://fly.io/apps/hoa-task-manager-staging>.
3. Check the most recent deploy in GitHub Actions — a recent red run
   means a broken push.
4. Roll back: `flyctl releases list -a hoa-task-manager-staging`, then
   `flyctl deploy --image registry.fly.io/hoa-task-manager-staging:<previous-tag>`.
5. If Fly is down for an extended period and the app is business-critical:
   PythonAnywhere is preserved as a dormant fallback. See
   [`docs/runbooks/deploy-pythonanywhere.md`](docs/runbooks/deploy-pythonanywhere.md).

### "The database is corrupted / wrong data is showing"

Daily backups live in R2 at `db-backups/YYYY-MM-DD.sqlite3`, retained
for 30 days. Restore procedure:
[`docs/runbooks/restore-database.md`](docs/runbooks/restore-database.md)
covers it end-to-end. The short version: upload the desired backup to
the bucket root with the name `db.sqlite3`, then set the
`RESTORE_FROM_R2_KEY` Fly secret to that filename and restart the
machine. The container's entrypoint runs the restore on boot.

**Always unset `RESTORE_FROM_R2_KEY` after a successful restore.**
Otherwise every restart will re-overwrite the database with the same
backup file.

### "I want to rotate the Django SECRET_KEY"

```powershell
$key = python -c "import secrets; print(secrets.token_urlsafe(64))"
flyctl secrets set DJANGO_SECRET_KEY="$key" -a hoa-task-manager-staging
```

(For the secret hygiene reason, prefer the PowerShell here-string pattern
documented in the deploy runbook over inline shell args.)

### "I want to rotate R2 / Resend / Fly credentials"

- **R2**: Cloudflare → R2 → API Tokens → revoke old, create new (scoped
  to the `hoa-task-manager` bucket), update the Fly secrets
  `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`.
- **Resend**: Resend dashboard → API Keys → revoke old, create new
  (scoped to `cicahoa.com`), update the Fly secret `RESEND_API_KEY`.
- **Fly token (used by GitHub Actions)**: `flyctl tokens create deploy
  --name github-actions-hoa`, paste into GitHub repo → Settings →
  Secrets → `FLY_API_TOKEN`.

---

## Known risks (in priority order)

### 1. The domain is in a personal account, not a board account
`cicahoa.com` is registered through Squarespace under a board member's
personal `@mac.com` account. If she leaves the board, her Squarespace
account goes with her — and the domain along with it. **Mitigation:**
transfer the domain to a board-owned account (`hoa-task-manager@gmail.com`
or similar) or to a board officer with continuity of role. Transfer
process: ~5 days, ~$10. **Not yet done as of 2026-06-03.** This is
flagged as the highest-priority continuity task.

### 2. Google Workspace billing is on the same personal account
The `@cicahoa.com` mailboxes are billed through the same board member's
Google Workspace account. If she leaves, the email service goes with
her. **Mitigation:** add a second account holder in Google Workspace
admin, OR transfer the subscription to a board-owned billing account.

### 3. Single point of admin failure
Currently only one user (`baranmcl@gmail.com`) is a Django superuser.
If McLean is unavailable, no one can promote other users to staff,
restore from backups, or change Django admin settings. **Mitigation:**
promote at least one other board member to superuser via the Django
admin. Do this **soon**.

### 4. Secrets rotation is manual and undocumented per-secret
The current operational pattern is "rotate when someone notices the key
shouldn't be where it is." There's no scheduled rotation. **Mitigation:**
not strictly necessary for an HOA's threat model, but document the
last rotation date in this file the next time it happens.

### 5. The "Forgot password" flow depends on the Resend HTTPS API
If Resend goes down, password resets break. Workaround: an admin can
manually set a user's password from the Django admin (`/admin/auth/user/`).

### 6. Date-bombed tests
Some tests use literal future dates (e.g., `dt.date(2026, 6, 1)`) that
become past dates as time passes and can fail unexpectedly. We've
already fixed one such test
(`test_board_excludes_recurring_templates`). If a test starts
failing on a year/date boundary, suspect this class of bug first.

---

## Handoff procedure — transferring the app to a successor

If McLean leaves and someone else takes over operationally:

1. **Add the successor as a GitHub collaborator** on the repo with
   Admin rights. <https://github.com/baranmcl/HOA-Task-Manager/settings/access>
2. **Add them to the shared password vault** with all the service
   credentials.
3. **Walk through this file with them**, especially the "Known risks"
   section.
4. **Make them a Django superuser** via the admin.
5. **Add them as a Fly organization member**: Fly dashboard →
   Organization → Members. Send them an invite.
6. **Add them to the Resend account team**: Resend dashboard → Settings
   → Team.
7. **Add them to the Cloudflare account**: Cloudflare dashboard →
   Members.
8. **Have them watch a deploy land**: they make a tiny doc edit, push,
   confirm the deploy goes green and lands at the live site. Best
   single-test of "do they have what they need."

Once they've done all of the above, the GitHub repo can be transferred
to their ownership (Settings → Transfer ownership) and McLean can be
demoted to a collaborator or removed entirely.

---

## Total cost of ownership

Rough annual cost as of 2026-06-03, assuming the board uses the app
the way it was designed:

| Item | Annual cost |
|---|---|
| Fly.io hosting | $30–60 |
| Cloudflare R2 (free tier covers it) | $0 |
| Resend (free tier covers it) | $0 |
| Domain registration | ~$12 |
| Google Workspace mailboxes | $6/mailbox × 12 = ~$72/box |
| **Total (excluding mailboxes)** | **~$50–75/yr** |

Mailbox costs scale with how many `@cicahoa.com` addresses the board
maintains. The app itself doesn't require any — `tasks@cicahoa.com`
is configured as a forwarding alias (no separate billing).

The total cost is unlikely to change in the foreseeable future at the
board's scale. The free tiers on R2 and Resend cover orders of
magnitude more usage than the board will generate.

---

## Source code license

[MIT License](LICENSE) — anyone can fork, modify, run, or
redistribute. Keep the copyright notice. If a successor wants to
maintain a private fork without sharing it publicly, the license
permits that.

---

*Maintainer of record: McLean Baran (`baranmcl@gmail.com`).
This file should be updated whenever the operational picture changes
materially. If you found it out of date, the commit history at
<https://github.com/baranmcl/HOA-Task-Manager/commits/main/CONTINUITY.md>
will tell you what's been updated and when.*
