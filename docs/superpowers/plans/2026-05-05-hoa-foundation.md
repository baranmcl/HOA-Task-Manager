# HOA Task Manager — Plan 1: Foundation & Auth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a deployable Django + HTMX + Tailwind skeleton with authentication and a working roster CRUD, deployed to a Fly.io staging environment with green CI.

**Architecture:** Django 5.x project managed with `uv`, served by gunicorn behind Fly.io. SQLite on a Fly persistent volume. Tailwind compiled at build time, HTMX loaded as a static asset. Two Django apps in this plan: `accounts` (auth + profile) and `roster` (people who can be assigned RACI later). A shared `templates/` directory with a sidebar layout. CI on GitHub Actions runs lint + tests; deploys to staging on green merges to `main`.

**Tech Stack:** Python 3.12, Django 5.0, `uv` for dependency management, `pytest-django`, `ruff`, `django-axes`, Tailwind CSS via standalone CLI binary, HTMX 1.9, gunicorn, Fly.io, GitHub Actions.

---

## File Structure

```
hoa-task-manager/
├── pyproject.toml              # uv-managed deps + tool config
├── uv.lock
├── manage.py
├── Dockerfile                  # Multi-stage: tailwind build + python runtime
├── fly.toml                    # Staging app config (no cron yet — added in Plan 2)
├── .github/workflows/ci.yml    # Lint + test on PRs and main
├── .github/workflows/deploy-staging.yml  # Deploy on green main
├── .dockerignore
├── conftest.py                 # pytest-django setup
├── pytest.ini                  # (or [tool.pytest.ini_options] in pyproject)
├── config/
│   ├── __init__.py
│   ├── settings.py             # All settings (single file — split later if it grows)
│   ├── urls.py                 # Root URL conf
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── __init__.py
│   ├── accounts/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py           # UserProfile (timezone setting)
│   │   ├── forms.py            # ProfileForm, custom AuthenticationForm
│   │   ├── views.py            # login/logout/profile/password_change
│   │   ├── urls.py
│   │   ├── signals.py          # Auto-create UserProfile on User create
│   │   ├── migrations/
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_models.py
│   │       ├── test_views.py
│   │       └── test_forms.py
│   └── roster/
│       ├── __init__.py
│       ├── apps.py
│       ├── models.py           # RosterPerson
│       ├── forms.py            # RosterPersonForm
│       ├── views.py            # list/detail/create/edit/archive
│       ├── urls.py
│       ├── migrations/
│       └── tests/
│           ├── __init__.py
│           ├── test_models.py
│           └── test_views.py
├── templates/
│   ├── base.html               # Sidebar layout, HTMX + Tailwind, message flashes
│   ├── _sidebar.html           # Nav partial
│   ├── _messages.html          # Flash messages partial
│   ├── registration/
│   │   ├── login.html
│   │   ├── password_change_form.html
│   │   └── password_change_done.html
│   ├── accounts/
│   │   └── profile.html
│   └── roster/
│       ├── list.html
│       ├── detail.html
│       ├── form.html
│       └── _row.html           # HTMX row partial
├── static/
│   ├── css/
│   │   ├── input.css           # Tailwind input
│   │   └── output.css          # Generated (gitignored)
│   ├── js/
│   │   └── htmx.min.js         # Vendored from htmx.org 1.9.x
│   └── img/
├── tailwind.config.js
└── .gitignore
```

**Decomposition rationale:**
- One Django app per bounded domain (`accounts`, `roster`). The spec lists `accounts`, `roster`, `projects`, `reports` — Plan 1 owns the first two.
- Templates live at the project root in `templates/` (not per-app) because the layout/sidebar is shared and small. Per-app template dirs encourage divergence.
- `config/` is the standard Django convention for the project package. Single `settings.py` is fine at this size; splitting into `base/dev/prod` is premature.
- `apps/` namespace keeps Django apps from polluting the project root.

---

## Task 1: Initialize repo skeleton with uv

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.dockerignore`

- [ ] **Step 1: Initialize uv project**

Run from repo root:
```bash
uv init --no-readme --python 3.12
```

This creates `pyproject.toml` and `.python-version`. Delete the auto-created `hello.py` if present.

- [ ] **Step 2: Pin core dependencies**

Edit `pyproject.toml` so the `[project]` block reads exactly:

```toml
[project]
name = "hoa-task-manager"
version = "0.1.0"
description = "Task and project tracker for HOA board work"
requires-python = ">=3.12"
dependencies = [
    "django>=5.0,<5.1",
    "django-axes>=6.4",
    "gunicorn>=21.2",
    "whitenoise>=6.6",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-django>=4.8",
    "ruff>=0.4",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "DJ"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
python_files = ["test_*.py"]
```

- [ ] **Step 3: Lock and install deps**

Run:
```bash
uv sync
```

Expected: creates `uv.lock` and `.venv/`. No errors.

- [ ] **Step 4: Write .gitignore**

Replace `.gitignore` contents with:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
.python-version

# Django
*.sqlite3
*.sqlite3-journal
/staticfiles/
media/

# Tailwind
static/css/output.css
node_modules/

# Tooling
.ruff_cache/
.pytest_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db

# Editor
.idea/
.vscode/
*.swp
```

- [ ] **Step 5: Write .dockerignore**

Create `.dockerignore`:

```
.venv
.git
.github
.pytest_cache
.ruff_cache
__pycache__
*.sqlite3
docs
node_modules
.env*
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .gitignore .dockerignore .python-version
git commit -m "chore: initialize uv project with Django dependencies"
```

---

## Task 2: Create Django project skeleton

**Files:**
- Create: `manage.py`
- Create: `config/__init__.py`
- Create: `config/settings.py`
- Create: `config/urls.py`
- Create: `config/wsgi.py`
- Create: `config/asgi.py`

- [ ] **Step 1: Generate Django project**

Run:
```bash
uv run django-admin startproject config .
```

This creates `manage.py` and `config/` with `settings.py`, `urls.py`, `wsgi.py`, `asgi.py`.

- [ ] **Step 2: Verify the dev server starts**

Run:
```bash
uv run python manage.py runserver
```

Expected: server starts on `http://127.0.0.1:8000/` and shows the Django welcome page. Stop it with Ctrl+C.

- [ ] **Step 3: Replace settings.py**

Overwrite `config/settings.py` with:

```python
"""Django settings for the HOA Task Manager."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-key-do-not-use-in-prod",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"
).split(",")

CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "apps.accounts",
    "apps.roster",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "accounts:login"

# Sessions: 14-day "remember me", secure cookies in prod
SESSION_COOKIE_AGE = 14 * 24 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"

# django-axes: 5 attempts, 15-min lockout
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.25  # hours
AXES_LOCKOUT_PARAMETERS = ["username"]
AXES_RESET_ON_SUCCESS = True

# Default user-facing timezone (per-user override stored on UserProfile)
DEFAULT_USER_TIMEZONE = "America/New_York"
```

- [ ] **Step 3a: Run it to confirm settings load**

```bash
uv run python manage.py check
```

Expected: `System check identified no issues (0 silenced).` Note: `apps.accounts` and `apps.roster` are referenced but not yet created — this WILL fail at this step. That's fine; we'll fix it in Task 3.

Actually — to keep this step truly green, comment out the two `apps.*` lines from `INSTALLED_APPS` for now and uncomment them in Task 3 Step 1. Mark them with `# TODO uncomment in Task 3`.

- [ ] **Step 4: Replace urls.py**

Overwrite `config/urls.py`:

```python
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import include, path


@login_required
def home(request):
    return render(request, "home.html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("roster/", include("apps.roster.urls", namespace="roster")),
    path("", home, name="home"),
]
```

Note: imports of `apps.accounts.urls` / `apps.roster.urls` will fail until Task 3 creates them. Acceptable interim state — confirmed in Task 3 Step 1.

- [ ] **Step 5: Commit**

```bash
git add manage.py config/
git commit -m "chore: scaffold Django project with secure-by-default settings"
```

---

## Task 3: Create the apps directory and stub the two apps

**Files:**
- Create: `apps/__init__.py`
- Create: `apps/accounts/__init__.py`
- Create: `apps/accounts/apps.py`
- Create: `apps/accounts/urls.py`
- Create: `apps/roster/__init__.py`
- Create: `apps/roster/apps.py`
- Create: `apps/roster/urls.py`

- [ ] **Step 1: Create directory structure**

Run:
```bash
mkdir -p apps/accounts/migrations apps/accounts/tests apps/roster/migrations apps/roster/tests
```

Then create empty `__init__.py` files:
```bash
uv run python -c "import pathlib; [pathlib.Path(p).touch() for p in ['apps/__init__.py','apps/accounts/__init__.py','apps/accounts/migrations/__init__.py','apps/accounts/tests/__init__.py','apps/roster/__init__.py','apps/roster/migrations/__init__.py','apps/roster/tests/__init__.py']]"
```

- [ ] **Step 2: Write apps/accounts/apps.py**

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"

    def ready(self):
        from . import signals  # noqa: F401
```

- [ ] **Step 3: Write apps/roster/apps.py**

```python
from django.apps import AppConfig


class RosterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.roster"
    label = "roster"
```

- [ ] **Step 4: Write empty signals.py for accounts**

Create `apps/accounts/signals.py` with an empty placeholder so `ready()` doesn't crash:

```python
"""Signals for the accounts app. Populated in later tasks."""
```

- [ ] **Step 5: Write empty urls.py for both apps**

Create `apps/accounts/urls.py`:

```python
from django.urls import path

app_name = "accounts"
urlpatterns: list = []
```

Create `apps/roster/urls.py`:

```python
from django.urls import path

app_name = "roster"
urlpatterns: list = []
```

- [ ] **Step 6: Re-enable apps in INSTALLED_APPS**

Re-uncomment the `apps.accounts` and `apps.roster` entries you commented out in Task 2 Step 3.

- [ ] **Step 7: Run Django check**

```bash
uv run python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 8: Run initial migrations**

```bash
uv run python manage.py migrate
```

Expected: applies all built-in migrations + axes; creates `db.sqlite3`.

- [ ] **Step 9: Commit**

```bash
git add apps/ config/settings.py
git commit -m "chore: stub accounts and roster Django apps"
```

---

## Task 4: Set up Tailwind via standalone CLI

**Files:**
- Create: `tailwind.config.js`
- Create: `static/css/input.css`
- Create: `bin/tailwindcss` (downloaded binary, gitignored)
- Modify: `pyproject.toml` (add scripts section if helpful)

- [ ] **Step 1: Download the Tailwind standalone binary**

We use the standalone CLI to avoid Node.js as a dev/build dependency.

```bash
mkdir -p bin
# macOS (Apple Silicon)
# curl -sLo bin/tailwindcss https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.4/tailwindcss-macos-arm64
# Linux x64 (used in Docker build)
curl -sLo bin/tailwindcss-linux-x64 https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.4/tailwindcss-linux-x64
chmod +x bin/tailwindcss-linux-x64
```

For local dev on Windows, download `tailwindcss-windows-x64.exe` from the same release and place it as `bin/tailwindcss.exe`. Add `bin/tailwindcss*` to `.gitignore`:

```bash
echo "bin/tailwindcss*" >> .gitignore
```

- [ ] **Step 2: Write tailwind.config.js**

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./apps/**/*.py",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        serif: ["Georgia", "Cambria", "Times New Roman", "serif"],
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 3: Write static/css/input.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer components {
  .btn { @apply inline-flex items-center px-3 py-2 rounded-md text-sm font-medium; }
  .btn-primary { @apply btn bg-blue-600 text-white hover:bg-blue-700; }
  .btn-secondary { @apply btn bg-gray-200 text-gray-900 hover:bg-gray-300; }
  .btn-danger { @apply btn bg-red-600 text-white hover:bg-red-700; }
  .input { @apply block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm; }
  .label { @apply block text-sm font-medium text-gray-700 mb-1; }
  .pill { @apply inline-flex items-center px-2 py-0.5 rounded text-xs font-medium; }
}
```

- [ ] **Step 4: Build CSS once**

On Windows:
```bash
./bin/tailwindcss.exe -i static/css/input.css -o static/css/output.css
```

On Linux/macOS in Docker build:
```bash
./bin/tailwindcss-linux-x64 -i static/css/input.css -o static/css/output.css
```

Expected: creates `static/css/output.css` (~10–30KB). The file is gitignored.

- [ ] **Step 5: Vendor HTMX**

```bash
mkdir -p static/js
curl -sLo static/js/htmx.min.js https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js
```

Verify the file is a few dozen KB and starts with `htmx`. Do not gitignore it — vendoring guarantees reproducible builds without a CDN dependency.

- [ ] **Step 6: Commit**

```bash
git add tailwind.config.js static/css/input.css static/js/htmx.min.js .gitignore
git commit -m "chore: add Tailwind config and vendor HTMX"
```

---

## Task 5: Write the base template and home page

**Files:**
- Create: `templates/base.html`
- Create: `templates/_sidebar.html`
- Create: `templates/_messages.html`
- Create: `templates/home.html`

- [ ] **Step 1: Write templates/base.html**

```html
{% load static %}<!DOCTYPE html>
<html lang="en" class="h-full bg-gray-50">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}HOA Task Manager{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/output.css' %}">
  <script src="{% static 'js/htmx.min.js' %}" defer></script>
  {% block extra_head %}{% endblock %}
</head>
<body class="h-full">
  {% if user.is_authenticated %}
    <div class="flex min-h-full">
      {% include "_sidebar.html" %}
      <main class="flex-1 px-6 py-6">
        {% include "_messages.html" %}
        {% block content %}{% endblock %}
      </main>
    </div>
  {% else %}
    <main class="min-h-full flex items-center justify-center px-6 py-12">
      {% include "_messages.html" %}
      {% block unauth_content %}{% endblock %}
    </main>
  {% endif %}
</body>
</html>
```

- [ ] **Step 2: Write templates/_sidebar.html**

```html
{% load static %}
<aside class="w-56 shrink-0 bg-white border-r border-gray-200 px-4 py-6 hidden md:block">
  <div class="text-lg font-semibold text-gray-900 mb-6">HOA Tasks</div>
  <nav class="space-y-1 text-sm">
    <a href="{% url 'home' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Dashboard</a>
    <a href="{% url 'roster:list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Roster</a>
    <a href="{% url 'accounts:profile' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Account</a>
    <form method="post" action="{% url 'accounts:logout' %}" class="pt-4">
      {% csrf_token %}
      <button type="submit" class="w-full text-left px-3 py-2 rounded hover:bg-gray-100">Log out</button>
    </form>
  </nav>
</aside>
```

(Projects/Recurring/Reports nav links are added in Plan 2 and Plan 3.)

- [ ] **Step 3: Write templates/_messages.html**

```html
{% if messages %}
<div class="mb-4 space-y-2">
  {% for message in messages %}
    <div class="rounded px-3 py-2 text-sm
      {% if message.tags == 'error' %}bg-red-50 text-red-800 border border-red-200
      {% elif message.tags == 'success' %}bg-green-50 text-green-800 border border-green-200
      {% else %}bg-blue-50 text-blue-800 border border-blue-200{% endif %}">
      {{ message }}
    </div>
  {% endfor %}
</div>
{% endif %}
```

- [ ] **Step 4: Write templates/home.html**

Placeholder — Plan 2 replaces this with the real dashboard.

```html
{% extends "base.html" %}
{% block title %}Dashboard — HOA Task Manager{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-2">Dashboard</h1>
<p class="text-gray-600">Welcome, {{ user.email|default:user.username }}.</p>
<p class="text-gray-600 mt-4">Project tracking lands in Plan 2.</p>
{% endblock %}
```

- [ ] **Step 5: Manually verify**

```bash
uv run python manage.py runserver
```

Open `http://127.0.0.1:8000/`. You should be redirected to `/accounts/login/`. That URL doesn't exist yet — you'll see a `NoReverseMatch` or 404. That's expected; we wire up auth in Task 6.

- [ ] **Step 6: Commit**

```bash
git add templates/
git commit -m "feat: add base layout with sidebar and message flashes"
```

---

## Task 6: Implement accounts app — UserProfile model with TDD

**Files:**
- Create: `apps/accounts/models.py`
- Modify: `apps/accounts/signals.py`
- Create: `apps/accounts/tests/test_models.py`
- Modify: `apps/accounts/admin.py`

- [ ] **Step 1: Write the failing test**

Create `apps/accounts/tests/test_models.py`:

```python
import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import UserProfile


@pytest.mark.django_db
def test_userprofile_auto_created_on_user_create():
    User = get_user_model()
    user = User.objects.create_user(
        username="alice@example.com",
        email="alice@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    assert UserProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_userprofile_default_timezone():
    User = get_user_model()
    user = User.objects.create_user(
        username="bob@example.com",
        email="bob@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    assert user.profile.timezone == "America/New_York"


@pytest.mark.django_db
def test_userprofile_can_change_timezone():
    User = get_user_model()
    user = User.objects.create_user(
        username="carol@example.com",
        email="carol@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    user.profile.timezone = "America/Los_Angeles"
    user.profile.save()
    user.profile.refresh_from_db()
    assert user.profile.timezone == "America/Los_Angeles"
```

- [ ] **Step 2: Run the tests and confirm they fail**

```bash
uv run pytest apps/accounts/tests/test_models.py -v
```

Expected: `ModuleNotFoundError` for `apps.accounts.models` UserProfile (or empty models module — same effect: ImportError).

- [ ] **Step 3: Write the model**

Create/replace `apps/accounts/models.py`:

```python
from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    timezone = models.CharField(max_length=64, default="America/New_York")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile<{self.user.username}>"
```

- [ ] **Step 4: Wire up the signal**

Replace `apps/accounts/signals.py`:

```python
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
```

- [ ] **Step 5: Generate and run the migration**

```bash
uv run python manage.py makemigrations accounts
uv run python manage.py migrate
```

Expected: creates `apps/accounts/migrations/0001_initial.py` and applies it.

- [ ] **Step 6: Run the tests**

```bash
uv run pytest apps/accounts/tests/test_models.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Register in admin**

Create `apps/accounts/admin.py`:

```python
from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "timezone", "updated_at")
    search_fields = ("user__username", "user__email")
```

- [ ] **Step 8: Commit**

```bash
git add apps/accounts/
git commit -m "feat(accounts): UserProfile with auto-creation signal and tz default"
```

---

## Task 7: Accounts views — login, logout, profile, password change

**Files:**
- Create: `apps/accounts/forms.py`
- Create: `apps/accounts/views.py`
- Replace: `apps/accounts/urls.py`
- Create: `templates/accounts/profile.html`
- Create: `templates/registration/login.html`
- Create: `templates/registration/password_change_form.html`
- Create: `templates/registration/password_change_done.html`
- Create: `apps/accounts/tests/test_views.py`

- [ ] **Step 1: Write the failing view tests**

Create `apps/accounts/tests/test_views.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        password="Sufficiently-Long-Pw-1",
    )


@pytest.mark.django_db
def test_login_get_renders(client):
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 200
    assert b"Sign in" in response.content


@pytest.mark.django_db
def test_login_post_redirects_to_home(client, user):
    response = client.post(
        reverse("accounts:login"),
        {"username": "user@example.com", "password": "Sufficiently-Long-Pw-1"},
    )
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_logout_redirects_to_login(client, user):
    client.force_login(user)
    response = client.post(reverse("accounts:logout"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_profile_requires_login(client):
    response = client.get(reverse("accounts:profile"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_profile_get_authenticated(client, user):
    client.force_login(user)
    response = client.get(reverse("accounts:profile"))
    assert response.status_code == 200
    assert b"America/New_York" in response.content


@pytest.mark.django_db
def test_profile_update_timezone(client, user):
    client.force_login(user)
    response = client.post(
        reverse("accounts:profile"),
        {"timezone": "America/Los_Angeles"},
    )
    assert response.status_code == 302
    user.profile.refresh_from_db()
    assert user.profile.timezone == "America/Los_Angeles"
```

- [ ] **Step 2: Run tests and confirm they fail**

```bash
uv run pytest apps/accounts/tests/test_views.py -v
```

Expected: all 6 fail with `NoReverseMatch` for `accounts:login` etc.

- [ ] **Step 3: Write the form**

Create `apps/accounts/forms.py`:

```python
import zoneinfo

from django import forms

from .models import UserProfile


def _timezone_choices():
    return [(tz, tz) for tz in sorted(zoneinfo.available_timezones())]


class ProfileForm(forms.ModelForm):
    timezone = forms.ChoiceField(choices=_timezone_choices)

    class Meta:
        model = UserProfile
        fields = ["timezone"]
```

- [ ] **Step 4: Write the views**

Create `apps/accounts/views.py`:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileForm


@login_required
def profile(request):
    profile_obj = request.user.profile
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=profile_obj)
    return render(request, "accounts/profile.html", {"form": form, "profile": profile_obj})
```

- [ ] **Step 5: Wire up URLs**

Replace `apps/accounts/urls.py`:

```python
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(
        template_name="registration/login.html",
        redirect_authenticated_user=True,
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("password/change/", auth_views.PasswordChangeView.as_view(
        success_url=reverse_lazy("accounts:password_change_done"),
    ), name="password_change"),
    path("password/change/done/", auth_views.PasswordChangeDoneView.as_view(),
         name="password_change_done"),
]
```

- [ ] **Step 6: Write login template**

Create `templates/registration/login.html`:

```html
{% extends "base.html" %}
{% block title %}Sign in — HOA Task Manager{% endblock %}
{% block unauth_content %}
<div class="w-full max-w-sm bg-white rounded-lg shadow p-6">
  <h1 class="text-xl font-semibold text-gray-900 mb-4">Sign in</h1>
  {% if form.errors %}
    <div class="mb-4 rounded bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-800">
      Username or password was incorrect.
    </div>
  {% endif %}
  <form method="post" class="space-y-4">
    {% csrf_token %}
    <div>
      <label for="id_username" class="label">Email</label>
      <input type="text" name="username" id="id_username" required autofocus class="input">
    </div>
    <div>
      <label for="id_password" class="label">Password</label>
      <input type="password" name="password" id="id_password" required class="input">
    </div>
    <button type="submit" class="btn-primary w-full justify-center">Sign in</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 7: Write profile template**

Create `templates/accounts/profile.html`:

```html
{% extends "base.html" %}
{% block title %}Account — HOA Task Manager{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-6">Account</h1>

<div class="bg-white rounded-lg shadow p-6 max-w-md">
  <dl class="space-y-2 text-sm mb-6">
    <div class="flex"><dt class="w-32 text-gray-500">Email</dt><dd class="text-gray-900">{{ user.email|default:user.username }}</dd></div>
    <div class="flex"><dt class="w-32 text-gray-500">Timezone</dt><dd class="text-gray-900">{{ profile.timezone }}</dd></div>
  </dl>

  <form method="post" class="space-y-4">
    {% csrf_token %}
    <div>
      <label for="id_timezone" class="label">Change timezone</label>
      {{ form.timezone }}
    </div>
    <button type="submit" class="btn-primary">Save</button>
  </form>

  <hr class="my-6">
  <a href="{% url 'accounts:password_change' %}" class="btn-secondary">Change password</a>
</div>
{% endblock %}
```

- [ ] **Step 8: Write password change templates**

Create `templates/registration/password_change_form.html`:

```html
{% extends "base.html" %}
{% block title %}Change password — HOA Task Manager{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-6">Change password</h1>
<div class="bg-white rounded-lg shadow p-6 max-w-md">
  <form method="post" class="space-y-4">
    {% csrf_token %}
    {% for field in form %}
      <div>
        <label class="label" for="{{ field.id_for_label }}">{{ field.label }}</label>
        {{ field }}
        {% if field.errors %}<p class="text-sm text-red-700 mt-1">{{ field.errors|join:", " }}</p>{% endif %}
      </div>
    {% endfor %}
    <div class="flex gap-2">
      <button type="submit" class="btn-primary">Change password</button>
      <a href="{% url 'accounts:profile' %}" class="btn-secondary">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

Create `templates/registration/password_change_done.html`:

```html
{% extends "base.html" %}
{% block title %}Password changed — HOA Task Manager{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-2">Password changed</h1>
<p class="text-gray-600 mb-4">Your password has been updated.</p>
<a href="{% url 'accounts:profile' %}" class="btn-primary">Back to account</a>
{% endblock %}
```

- [ ] **Step 9: Apply Tailwind classes to default form widgets**

Edit `apps/accounts/forms.py` so widgets render with the `input` class. Replace the `ProfileForm`:

```python
class ProfileForm(forms.ModelForm):
    timezone = forms.ChoiceField(
        choices=_timezone_choices,
        widget=forms.Select(attrs={"class": "input"}),
    )

    class Meta:
        model = UserProfile
        fields = ["timezone"]
```

For the password change form (a built-in Django form), wrap it via a custom view subclass — but for v1 simplicity the default rendering is acceptable. Move on.

- [ ] **Step 10: Run all accounts tests**

```bash
uv run pytest apps/accounts -v
```

Expected: 9 passed (3 model + 6 view).

- [ ] **Step 11: Rebuild Tailwind**

```bash
./bin/tailwindcss.exe -i static/css/input.css -o static/css/output.css
```

Manually verify in browser: log in, change timezone, change password.

- [ ] **Step 12: Commit**

```bash
git add apps/accounts/ templates/
git commit -m "feat(accounts): login/logout, profile with timezone, password change"
```

---

## Task 8: Roster app — RosterPerson model with TDD

**Files:**
- Create: `apps/roster/models.py`
- Create: `apps/roster/admin.py`
- Create: `apps/roster/tests/test_models.py`

- [ ] **Step 1: Write the failing model tests**

Create `apps/roster/tests/test_models.py`:

```python
import pytest

from apps.roster.models import RosterPerson


@pytest.mark.django_db
def test_create_roster_person_with_required_fields():
    person = RosterPerson.objects.create(name="Mike Smith")
    assert person.name == "Mike Smith"
    assert person.archived is False
    assert person.email == ""
    assert person.phone == ""
    assert person.role_title == ""


@pytest.mark.django_db
def test_roster_person_str():
    p = RosterPerson.objects.create(name="Mike Smith", role_title="Treasurer")
    assert str(p) == "Mike Smith"


@pytest.mark.django_db
def test_archive_roster_person():
    p = RosterPerson.objects.create(name="Mike Smith")
    p.archived = True
    p.save()
    p.refresh_from_db()
    assert p.archived is True


@pytest.mark.django_db
def test_active_manager_excludes_archived():
    RosterPerson.objects.create(name="Active Person")
    RosterPerson.objects.create(name="Archived Person", archived=True)
    assert RosterPerson.active.count() == 1
    assert RosterPerson.objects.count() == 2
```

- [ ] **Step 2: Run tests and confirm they fail**

```bash
uv run pytest apps/roster/tests/test_models.py -v
```

Expected: 4 failures, ImportError on `RosterPerson`.

- [ ] **Step 3: Write the model**

Create `apps/roster/models.py`:

```python
from django.db import models


class ActiveRosterManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(archived=False)


class RosterPerson(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    role_title = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveRosterManager()

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["archived", "name"]),
        ]

    def __str__(self):
        return self.name
```

- [ ] **Step 4: Make and apply migration**

```bash
uv run python manage.py makemigrations roster
uv run python manage.py migrate
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest apps/roster/tests/test_models.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Register in admin**

Create `apps/roster/admin.py`:

```python
from django.contrib import admin

from .models import RosterPerson


@admin.register(RosterPerson)
class RosterPersonAdmin(admin.ModelAdmin):
    list_display = ("name", "role_title", "email", "archived", "updated_at")
    list_filter = ("archived",)
    search_fields = ("name", "email", "role_title")
```

- [ ] **Step 7: Commit**

```bash
git add apps/roster/
git commit -m "feat(roster): RosterPerson model with archive flag and active manager"
```

---

## Task 9: Roster views and templates

**Files:**
- Create: `apps/roster/forms.py`
- Create: `apps/roster/views.py`
- Replace: `apps/roster/urls.py`
- Create: `templates/roster/list.html`
- Create: `templates/roster/detail.html`
- Create: `templates/roster/form.html`
- Create: `templates/roster/_row.html`
- Create: `apps/roster/tests/test_views.py`

- [ ] **Step 1: Write the failing view tests**

Create `apps/roster/tests/test_views.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.roster.models import RosterPerson


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        password="Sufficiently-Long-Pw-1",
    )


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_list_requires_login(client):
    response = client.get(reverse("roster:list"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_list_renders_active_only_by_default(auth_client):
    RosterPerson.objects.create(name="Active Alice")
    RosterPerson.objects.create(name="Archived Bob", archived=True)
    response = auth_client.get(reverse("roster:list"))
    assert response.status_code == 200
    assert b"Active Alice" in response.content
    assert b"Archived Bob" not in response.content


@pytest.mark.django_db
def test_list_show_archived(auth_client):
    RosterPerson.objects.create(name="Archived Bob", archived=True)
    response = auth_client.get(reverse("roster:list") + "?show_archived=1")
    assert response.status_code == 200
    assert b"Archived Bob" in response.content


@pytest.mark.django_db
def test_create_person(auth_client):
    response = auth_client.post(reverse("roster:create"), {
        "name": "New Person",
        "email": "new@example.com",
        "phone": "",
        "role_title": "Member",
        "notes": "",
    })
    assert response.status_code == 302
    assert RosterPerson.objects.filter(name="New Person").exists()


@pytest.mark.django_db
def test_detail_renders(auth_client):
    p = RosterPerson.objects.create(name="Detail Person")
    response = auth_client.get(reverse("roster:detail", args=[p.pk]))
    assert response.status_code == 200
    assert b"Detail Person" in response.content


@pytest.mark.django_db
def test_edit_person(auth_client):
    p = RosterPerson.objects.create(name="Old Name")
    response = auth_client.post(reverse("roster:edit", args=[p.pk]), {
        "name": "New Name",
        "email": "",
        "phone": "",
        "role_title": "",
        "notes": "",
    })
    assert response.status_code == 302
    p.refresh_from_db()
    assert p.name == "New Name"


@pytest.mark.django_db
def test_archive_person(auth_client):
    p = RosterPerson.objects.create(name="To Archive")
    response = auth_client.post(reverse("roster:archive", args=[p.pk]))
    assert response.status_code == 302
    p.refresh_from_db()
    assert p.archived is True


@pytest.mark.django_db
def test_unarchive_person(auth_client):
    p = RosterPerson.objects.create(name="To Unarchive", archived=True)
    response = auth_client.post(reverse("roster:unarchive", args=[p.pk]))
    assert response.status_code == 302
    p.refresh_from_db()
    assert p.archived is False
```

- [ ] **Step 2: Run tests and confirm they fail**

```bash
uv run pytest apps/roster/tests/test_views.py -v
```

Expected: 8 failures with `NoReverseMatch`.

- [ ] **Step 3: Write the form**

Create `apps/roster/forms.py`:

```python
from django import forms

from .models import RosterPerson


class RosterPersonForm(forms.ModelForm):
    class Meta:
        model = RosterPerson
        fields = ["name", "email", "phone", "role_title", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "email": forms.EmailInput(attrs={"class": "input"}),
            "phone": forms.TextInput(attrs={"class": "input"}),
            "role_title": forms.TextInput(attrs={"class": "input"}),
            "notes": forms.Textarea(attrs={"class": "input", "rows": 4}),
        }
```

- [ ] **Step 4: Write the views**

Create `apps/roster/views.py`:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RosterPersonForm
from .models import RosterPerson


@login_required
def list_view(request):
    show_archived = request.GET.get("show_archived") == "1"
    qs = RosterPerson.objects.all() if show_archived else RosterPerson.active.all()
    return render(request, "roster/list.html", {
        "people": qs,
        "show_archived": show_archived,
    })


@login_required
def detail(request, pk):
    person = get_object_or_404(RosterPerson, pk=pk)
    return render(request, "roster/detail.html", {"person": person})


@login_required
def create(request):
    if request.method == "POST":
        form = RosterPersonForm(request.POST)
        if form.is_valid():
            person = form.save()
            messages.success(request, f"Added {person.name}.")
            return redirect("roster:detail", pk=person.pk)
    else:
        form = RosterPersonForm()
    return render(request, "roster/form.html", {"form": form, "person": None})


@login_required
def edit(request, pk):
    person = get_object_or_404(RosterPerson, pk=pk)
    if request.method == "POST":
        form = RosterPersonForm(request.POST, instance=person)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved.")
            return redirect("roster:detail", pk=person.pk)
    else:
        form = RosterPersonForm(instance=person)
    return render(request, "roster/form.html", {"form": form, "person": person})


@login_required
def archive(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    person = get_object_or_404(RosterPerson, pk=pk)
    person.archived = True
    person.save()
    messages.success(request, f"Archived {person.name}.")
    return redirect("roster:list")


@login_required
def unarchive(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    person = get_object_or_404(RosterPerson, pk=pk)
    person.archived = False
    person.save()
    messages.success(request, f"Restored {person.name}.")
    return redirect("roster:detail", pk=person.pk)
```

- [ ] **Step 5: Wire up URLs**

Replace `apps/roster/urls.py`:

```python
from django.urls import path

from . import views

app_name = "roster"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("new/", views.create, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/archive/", views.archive, name="archive"),
    path("<int:pk>/unarchive/", views.unarchive, name="unarchive"),
]
```

- [ ] **Step 6: Write list template**

Create `templates/roster/list.html`:

```html
{% extends "base.html" %}
{% block title %}Roster — HOA Task Manager{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6">
  <h1 class="text-2xl font-semibold text-gray-900">Roster</h1>
  <a href="{% url 'roster:create' %}" class="btn-primary">+ New person</a>
</div>

<div class="mb-4 flex gap-4 text-sm">
  {% if show_archived %}
    <a href="{% url 'roster:list' %}" class="text-blue-600 hover:underline">Hide archived</a>
  {% else %}
    <a href="{% url 'roster:list' %}?show_archived=1" class="text-blue-600 hover:underline">Show archived</a>
  {% endif %}
</div>

{% if people %}
<div class="bg-white rounded-lg shadow overflow-hidden">
  <table class="min-w-full divide-y divide-gray-200">
    <thead class="bg-gray-50 text-xs uppercase text-gray-500">
      <tr>
        <th class="px-4 py-3 text-left">Name</th>
        <th class="px-4 py-3 text-left">Role</th>
        <th class="px-4 py-3 text-left">Email</th>
        <th class="px-4 py-3 text-left">Phone</th>
        <th class="px-4 py-3"></th>
      </tr>
    </thead>
    <tbody class="divide-y divide-gray-100">
      {% for person in people %}{% include "roster/_row.html" %}{% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<div class="bg-white rounded-lg shadow p-8 text-center">
  <p class="text-gray-500 mb-4">No people in the roster yet.</p>
  <a href="{% url 'roster:create' %}" class="btn-primary">Add your first person</a>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 7: Write row partial**

Create `templates/roster/_row.html`:

```html
<tr>
  <td class="px-4 py-3">
    <a href="{% url 'roster:detail' person.pk %}" class="text-blue-700 hover:underline font-medium">{{ person.name }}</a>
    {% if person.archived %}<span class="ml-2 pill bg-gray-200 text-gray-700">archived</span>{% endif %}
  </td>
  <td class="px-4 py-3 text-sm text-gray-700">{{ person.role_title|default:"—" }}</td>
  <td class="px-4 py-3 text-sm text-gray-700">{{ person.email|default:"—" }}</td>
  <td class="px-4 py-3 text-sm text-gray-700">{{ person.phone|default:"—" }}</td>
  <td class="px-4 py-3 text-right text-sm">
    <a href="{% url 'roster:edit' person.pk %}" class="text-gray-600 hover:text-gray-900">Edit</a>
  </td>
</tr>
```

- [ ] **Step 8: Write detail template**

Create `templates/roster/detail.html`:

```html
{% extends "base.html" %}
{% block title %}{{ person.name }} — HOA Task Manager{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6">
  <div>
    <h1 class="text-2xl font-semibold text-gray-900">{{ person.name }}</h1>
    {% if person.archived %}<span class="pill bg-gray-200 text-gray-700 mt-1">archived</span>{% endif %}
  </div>
  <div class="flex gap-2">
    <a href="{% url 'roster:edit' person.pk %}" class="btn-secondary">Edit</a>
    {% if person.archived %}
      <form method="post" action="{% url 'roster:unarchive' person.pk %}" class="inline">
        {% csrf_token %}<button type="submit" class="btn-secondary">Restore</button>
      </form>
    {% else %}
      <form method="post" action="{% url 'roster:archive' person.pk %}" class="inline"
            onsubmit="return confirm('Archive {{ person.name|escapejs }}? Their existing assignments stay intact.');">
        {% csrf_token %}<button type="submit" class="btn-secondary">Archive</button>
      </form>
    {% endif %}
  </div>
</div>

<div class="bg-white rounded-lg shadow p-6 max-w-2xl">
  <dl class="grid grid-cols-3 gap-y-3 text-sm">
    <dt class="text-gray-500">Role</dt><dd class="col-span-2 text-gray-900">{{ person.role_title|default:"—" }}</dd>
    <dt class="text-gray-500">Email</dt><dd class="col-span-2 text-gray-900">{{ person.email|default:"—" }}</dd>
    <dt class="text-gray-500">Phone</dt><dd class="col-span-2 text-gray-900">{{ person.phone|default:"—" }}</dd>
    <dt class="text-gray-500">Notes</dt><dd class="col-span-2 text-gray-900 whitespace-pre-wrap">{{ person.notes|default:"—" }}</dd>
  </dl>
</div>

<div class="mt-6 max-w-2xl text-sm text-gray-500">
  Project assignments will appear here once the projects app is added (Plan 2).
</div>
{% endblock %}
```

- [ ] **Step 9: Write form template**

Create `templates/roster/form.html`:

```html
{% extends "base.html" %}
{% block title %}{% if person %}Edit {{ person.name }}{% else %}New person{% endif %} — HOA Task Manager{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-6">
  {% if person %}Edit {{ person.name }}{% else %}New person{% endif %}
</h1>

<form method="post" class="bg-white rounded-lg shadow p-6 max-w-xl space-y-4">
  {% csrf_token %}
  {% for field in form %}
    <div>
      <label class="label" for="{{ field.id_for_label }}">{{ field.label }}{% if field.field.required %} *{% endif %}</label>
      {{ field }}
      {% if field.errors %}<p class="text-sm text-red-700 mt-1">{{ field.errors|join:", " }}</p>{% endif %}
    </div>
  {% endfor %}
  <div class="flex gap-2 pt-2">
    <button type="submit" class="btn-primary">Save</button>
    <a href="{% if person %}{% url 'roster:detail' person.pk %}{% else %}{% url 'roster:list' %}{% endif %}"
       class="btn-secondary">Cancel</a>
  </div>
</form>
{% endblock %}
```

- [ ] **Step 10: Run all roster tests**

```bash
uv run pytest apps/roster -v
```

Expected: 12 passed (4 model + 8 view).

- [ ] **Step 11: Manually smoke test**

Rebuild Tailwind, run server, log in, add a person, edit, archive, restore. Confirm everything works visually.

- [ ] **Step 12: Commit**

```bash
git add apps/roster/ templates/roster/
git commit -m "feat(roster): CRUD with archive/restore and empty state"
```

---

## Task 10: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --frozen

      - name: Lint with ruff
        run: uv run ruff check .

      - name: Run migrations check
        run: uv run python manage.py makemigrations --check --dry-run

      - name: Run tests
        run: uv run pytest -v
        env:
          DJANGO_SECRET_KEY: ci-only-key-not-secret
          DJANGO_DEBUG: "False"
          DJANGO_ALLOWED_HOSTS: "*"
```

- [ ] **Step 2: Push and verify**

Push the branch and open a PR. Confirm the CI workflow runs and passes.

- [ ] **Step 3: Commit (already pushed)**

The workflow file itself is committed in this push:

```bash
git add .github/workflows/ci.yml
git commit -m "ci: lint and test on PRs and main"
```

---

## Task 11: Dockerfile and Fly staging deploy

**Files:**
- Create: `Dockerfile`
- Create: `fly.toml`
- Create: `.github/workflows/deploy-staging.yml`

- [ ] **Step 1: Write the Dockerfile**

Multi-stage: stage 1 downloads Tailwind and builds CSS, stage 2 is the runtime image.

Create `Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7

# --- Stage 1: build CSS ---
FROM debian:bookworm-slim AS css
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN curl -sLo /usr/local/bin/tailwindcss \
    https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.4/tailwindcss-linux-x64 \
    && chmod +x /usr/local/bin/tailwindcss
COPY tailwind.config.js ./
COPY templates/ ./templates/
COPY apps/ ./apps/
COPY static/css/input.css ./static/css/input.css
RUN tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify

# --- Stage 2: python runtime ---
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 UV_COMPILE_BYTECODE=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-0 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install python deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy app source
COPY manage.py ./
COPY config/ ./config/
COPY apps/ ./apps/
COPY templates/ ./templates/
COPY static/ ./static/
COPY --from=css /app/static/css/output.css ./static/css/output.css

# Collect static at build time
RUN DJANGO_SECRET_KEY=build-only DJANGO_DEBUG=False DJANGO_ALLOWED_HOSTS=* \
    uv run python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["uv", "run", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
```

- [ ] **Step 2: Test the Docker build locally**

```bash
docker build -t hoa-test .
docker run --rm -p 8000:8000 \
  -e DJANGO_SECRET_KEY=test-only \
  -e DJANGO_DEBUG=False \
  -e DJANGO_ALLOWED_HOSTS="*" \
  hoa-test
```

Expected: gunicorn starts, app responds on `localhost:8000` (you'll get redirected to login). Stop with Ctrl+C.

- [ ] **Step 3: Create the Fly staging app**

This is a one-time manual step the deploying engineer runs. Document it in this task.

```bash
fly auth login
fly apps create hoa-task-manager-staging
fly volumes create data --region iad --size 1 --app hoa-task-manager-staging
```

- [ ] **Step 4: Write fly.toml**

Create `fly.toml`:

```toml
app = "hoa-task-manager-staging"
primary_region = "iad"

[build]

[env]
  DJANGO_DEBUG = "False"
  DJANGO_ALLOWED_HOSTS = "hoa-task-manager-staging.fly.dev"
  DJANGO_CSRF_TRUSTED_ORIGINS = "https://hoa-task-manager-staging.fly.dev"
  DJANGO_DB_PATH = "/data/db.sqlite3"

[mounts]
  source = "data"
  destination = "/data"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0
  processes = ["app"]

  [http_service.concurrency]
    type = "requests"
    soft_limit = 50
    hard_limit = 100

  [[http_service.checks]]
    interval = "30s"
    timeout = "5s"
    grace_period = "10s"
    method = "GET"
    path = "/accounts/login/"

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"

[deploy]
  release_command = "uv run python manage.py migrate --noinput"
```

- [ ] **Step 5: Set the secret**

```bash
fly secrets set DJANGO_SECRET_KEY="$(uv run python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" \
  --app hoa-task-manager-staging
```

- [ ] **Step 6: First manual deploy**

```bash
fly deploy --app hoa-task-manager-staging
```

Expected: deploy succeeds. Visit `https://hoa-task-manager-staging.fly.dev/`.

- [ ] **Step 7: Create the first user via SSH**

```bash
fly ssh console --app hoa-task-manager-staging -C "uv run python manage.py createsuperuser"
```

Sign in at `/accounts/login/` with that user. Confirm roster CRUD works in production.

- [ ] **Step 8: Write the auto-deploy workflow**

Create `.github/workflows/deploy-staging.yml`:

```yaml
name: Deploy to staging

on:
  push:
    branches: [main]

jobs:
  deploy:
    name: Deploy
    runs-on: ubuntu-latest
    needs: []
    concurrency:
      group: deploy-staging
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only --app hoa-task-manager-staging
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

- [ ] **Step 9: Add the FLY_API_TOKEN secret on GitHub**

```bash
fly tokens create deploy --app hoa-task-manager-staging
```

In GitHub repo settings → Secrets and variables → Actions, add a secret named `FLY_API_TOKEN` with the token output.

- [ ] **Step 10: Commit**

```bash
git add Dockerfile fly.toml .github/workflows/deploy-staging.yml
git commit -m "deploy: Dockerfile and Fly staging with auto-deploy on main"
```

- [ ] **Step 11: Push and verify the auto-deploy**

```bash
git push origin main
```

Watch the GitHub Actions tab. The deploy workflow should run after the CI workflow passes (or in parallel — it's fine to keep it independent at this size; Plan 3 hardens this).

---

## Self-Review

Before handing off, walk through this checklist:

**Spec coverage (sections 1, 2, 3 partial, 7, 9, 10 partial):**
- Single user with multi-user readiness — single User table, RosterPerson is the multi-user-ready model ✓
- Stack: Django 5, Tailwind, HTMX, SQLite, Fly.io ✓ (R2/litestream deferred to Plan 3)
- Auth: Django built-in, email-as-username, django-axes throttling ✓
- Sessions: 14-day, Secure+HttpOnly+SameSite=Strict in prod ✓
- HTTPS via Fly ✓
- No password recovery email — manual `changepassword` documented ✓ (mention in profile docs in Plan 3)
- Project structure: `config/`, `apps/accounts`, `apps/roster`, `templates/`, `static/` ✓
- Free-tier sizing: shared-cpu-1x 256MB ✓
- Tests: pytest-django, no DB mocking ✓

**Placeholder scan:** No `TBD`, `implement later`, or "similar to Task N" references. Each step has the actual code or command needed.

**Type consistency:**
- `RosterPerson` field names (`name`, `email`, `phone`, `role_title`, `notes`, `archived`) match the spec table.
- `UserProfile.timezone` — used in Plan 1 for the profile setting; Plan 2 will read it for date display.
- URL namespace `accounts:` matches `accounts:login`, `accounts:logout`, `accounts:profile`, `accounts:password_change` everywhere.
- URL namespace `roster:` matches `roster:list`, `roster:create`, `roster:detail`, `roster:edit`, `roster:archive`, `roster:unarchive` everywhere.

**Plan 1 deliberate deferrals (handed off to Plan 2 / 3):**
- Cron / `generate_recurring_instances` → Plan 2
- R2 / file uploads → Plan 2 (attachments) or Plan 3 (move there if you'd rather)
- litestream backups → Plan 3
- Production Fly app + tagged-release promotion → Plan 3

If anything in this list surprises the executing engineer, surface it before starting Task 1.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-05-hoa-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
