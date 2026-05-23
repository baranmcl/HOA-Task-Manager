"""Tests for BackupMiddleware."""
import datetime as dt

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from apps.accounts import middleware as mw_module
from apps.accounts.middleware import BackupMiddleware
from apps.accounts.models import BackupLog


@pytest.fixture
def set_r2(settings):
    settings.R2_ENDPOINT_URL = "https://x.r2.cloudflarestorage.com"
    settings.R2_ACCESS_KEY_ID = "k"
    settings.R2_SECRET_ACCESS_KEY = "s"
    settings.R2_BUCKET = "hoa-test"


def _call_middleware(monkeypatch):
    """Run the middleware once, stubbing call_command to capture invocations."""
    calls = []
    monkeypatch.setattr(
        mw_module, "call_command",
        lambda name, *a, **k: calls.append(name),
    )

    def get_response(request):
        return HttpResponse()

    middleware = BackupMiddleware(get_response)
    request = RequestFactory().get("/")
    middleware(request)
    return calls


@pytest.mark.django_db(transaction=True)
def test_first_call_of_day_runs_backup(set_r2, monkeypatch):
    calls = _call_middleware(monkeypatch)
    assert calls == ["backup_database"]
    assert BackupLog.objects.filter(run_date=dt.date.today()).exists()


@pytest.mark.django_db(transaction=True)
def test_second_call_same_day_does_not_run(set_r2, monkeypatch):
    BackupLog.objects.create(run_date=dt.date.today())
    calls = _call_middleware(monkeypatch)
    assert calls == []
