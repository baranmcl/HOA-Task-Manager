# Deploying to PythonAnywhere (current staging host)

PythonAnywhere is the **active** host for the HOA Task Manager staging app.
It is genuinely free. The Fly.io setup (`Dockerfile`, `fly.toml`,
`entrypoint.sh`, `.github/workflows/deploy-staging.yml`) is retained but
dormant — see the bottom of this file to switch back.

PythonAnywhere has no Docker, no CLI, and no SSH on free accounts, so this
is a manual, one-time setup done through their **Bash console** and **web
dashboard**. After setup, updates are a quick three-step routine (see
"Updating the app later").

Replace `USERNAME` with your PythonAnywhere username everywhere below.

---

## Prerequisites

- A free PythonAnywhere account ("Beginner" plan) — sign up at
  https://www.pythonanywhere.com/registration/register/beginner/
- The repo is public at https://github.com/baranmcl/HOA-Task-Manager — no
  auth needed to clone.

---

## Part 1 — Bash console setup

Open a **Bash console** from the PythonAnywhere **Consoles** tab.

- [ ] **1. Clone the repo**

```bash
git clone https://github.com/baranmcl/HOA-Task-Manager.git
cd HOA-Task-Manager
```

This creates `/home/USERNAME/HOA-Task-Manager/`.

- [ ] **2. Create a virtualenv on Python 3.12**

```bash
mkvirtualenv --python=/usr/bin/python3.12 hoa-venv
```

`mkvirtualenv` activates the venv automatically and creates it at
`/home/USERNAME/.virtualenvs/hoa-venv` — note that path, the Web tab needs it.
Your prompt should now show `(hoa-venv)`.

- [ ] **3. Install dependencies**

```bash
cd ~/HOA-Task-Manager
pip install -r requirements.txt
```

(`tzdata` is marked Windows-only in `requirements.txt` and is skipped on
PythonAnywhere's Linux — that is expected and correct.)

- [ ] **4. Run database migrations**

```bash
python manage.py migrate
```

This creates `db.sqlite3` in the project directory (persistent on
PythonAnywhere). These one-off admin commands run fine with the insecure
default `SECRET_KEY` — the real key is set for the live app in Part 2.

- [ ] **5. Collect static files**

```bash
python manage.py collectstatic --noinput
```

The compiled Tailwind CSS (`static/css/output.css`) is committed to the repo,
so it is already present — `collectstatic` copies it into `staticfiles/`.

- [ ] **6. Create your admin account**

```bash
python manage.py createsuperuser
```

Type your email as the username, your email, and a password at the prompts.
(Use your email as the username — the app logs in with email-as-username.)

---

## Part 2 — Web app configuration (dashboard)

Go to the **Web** tab.

- [ ] **7. Add a new web app**

- Click **Add a new web app**.
- Domain: accept `USERNAME.pythonanywhere.com`.
- Framework: choose **Manual configuration** (NOT "Django" — that scaffolds a
  new project; we have an existing one).
- Python version: **3.12**.

- [ ] **8. Set the virtualenv**

In the **Virtualenv** section of the Web tab, enter:

```
/home/USERNAME/.virtualenvs/hoa-venv
```

- [ ] **9. Set the source code and working directory**

In the **Code** section:

- **Source code:** `/home/USERNAME/HOA-Task-Manager`
- **Working directory:** `/home/USERNAME/HOA-Task-Manager`

- [ ] **10. Edit the WSGI configuration file**

In the **Code** section, click the WSGI file link (named
`/var/www/USERNAME_pythonanywhere_com_wsgi.py`). **Delete the entire contents**
and replace with exactly this (substitute `USERNAME` and the secret key):

```python
import os
import sys

# --- Project on the import path ---
path = "/home/USERNAME/HOA-Task-Manager"
if path not in sys.path:
    sys.path.insert(0, path)

# --- Environment (settings.py reads all of these) ---
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DEBUG"] = "False"
os.environ["DJANGO_ALLOWED_HOSTS"] = "USERNAME.pythonanywhere.com"
os.environ["DJANGO_CSRF_TRUSTED_ORIGINS"] = "https://USERNAME.pythonanywhere.com"
os.environ["DJANGO_SECRET_KEY"] = "PASTE-YOUR-GENERATED-SECRET-KEY-HERE"

# --- Django WSGI application ---
from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
```

To generate the secret key, run this in your Bash console (with the
`hoa-venv` virtualenv active) and paste the output into the WSGI file:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

The WSGI file lives outside the git repo, so the secret key stays out of
version control — that is the intended place for it on PythonAnywhere.

`DJANGO_DB_PATH` is not set: `settings.py` then defaults the database to
`<project>/db.sqlite3`, which is the persistent file created in step 4.

- [ ] **11. Reload the web app**

Click the big green **Reload** button at the top of the Web tab.

---

## Part 3 — Verify

- [ ] Visit `https://USERNAME.pythonanywhere.com/` — it should redirect to
  `/accounts/login/`.
- [ ] Log in with the superuser credentials from step 6 — you should land on
  the dashboard ("Welcome, your@email").
- [ ] Visit `/roster/` — the roster page with its empty state should render,
  fully styled (confirms static CSS is being served).
- [ ] Open Account → Change password if you want to rotate the password.

If the site is unstyled, static files are not being served — re-run
`collectstatic` (step 5) and Reload.

If you get a 500, check the **error log** linked in the Web tab (usually a
typo in the WSGI file — `USERNAME` not substituted, or a missing quote).

---

## Updating the app later

After pushing code to `main` on GitHub, in the PythonAnywhere Bash console:

```bash
cd ~/HOA-Task-Manager
workon hoa-venv
git pull
pip install -r requirements.txt   # only if dependencies changed
python manage.py migrate          # only if there are new migrations
python manage.py collectstatic --noinput   # only if static files changed
```

Then click **Reload** on the Web tab.

**When templates or `static/css/input.css` change**, the compiled CSS must be
rebuilt. Do this **locally** (PythonAnywhere's restricted outbound network
makes building there unreliable), then commit it:

```bash
./bin/tailwindcss -i static/css/input.css -o static/css/output.css --minify
git add static/css/output.css && git commit -m "build: rebuild Tailwind CSS"
git push
```

The next `git pull` on PythonAnywhere then brings the updated CSS.

---

## Things to know about the free tier

- **Monthly renewal:** PythonAnywhere emails you roughly monthly to confirm
  you still want the web app running. Click the link, or — if you miss it —
  log in and click the re-enable button on the Web tab. Files are never
  deleted; the app just pauses until you click.
- **CPU seconds:** free accounts get 100 CPU-seconds/day. Exceeding it
  *throttles* the app (slower) until midnight UTC — it does not stop. Ample
  for a single-user-to-small-team admin tool.
- **No scheduled tasks:** free accounts created after Jan 2026 do not get
  PythonAnywhere's scheduled-task feature. This is solved: Plan 2's
  recurring-instance generator now runs automatically via
  `RecurringGenerationMiddleware`, which triggers it lazily on the first web
  request of each day — no scheduled task needed.

---

## Returning to Fly later

The Fly setup is fully retained. To reactivate it:

1. Restore the `push` trigger in `.github/workflows/deploy-staging.yml`
   (the original trigger is in a comment at the top of that file).
2. The `FLY_API_TOKEN` GitHub secret and the `hoa-task-manager-staging` Fly
   app may still exist; recreate them per
   `docs/superpowers/plans/2026-05-05-hoa-foundation.md` Task 11 if not.
3. `flyctl deploy` — `Dockerfile`, `fly.toml`, and `entrypoint.sh` are
   unchanged and ready.
