"""Tests for the Resend / django-anymail email wiring."""
from django.conf import settings
from django.core import mail
from django.test import override_settings


def test_default_from_email_is_configured():
    """A From: address must be set or every email send will fail."""
    assert settings.DEFAULT_FROM_EMAIL
    assert "@" in settings.DEFAULT_FROM_EMAIL


def test_default_from_email_is_on_cicahoa_domain():
    """The From: address must match the domain verified at Resend, or
    the API will reject the send with a 403."""
    assert settings.DEFAULT_FROM_EMAIL.endswith("@cicahoa.com")


def test_anymail_resend_api_key_setting_present():
    """The settings shape must include ANYMAIL['RESEND_API_KEY'] even if
    empty — django-anymail reads it via this dict, not via env directly."""
    assert "RESEND_API_KEY" in settings.ANYMAIL


def test_anymail_is_in_installed_apps():
    """Required for django-anymail's management commands + signal hooks."""
    assert "anymail" in settings.INSTALLED_APPS


def test_send_mail_routes_through_test_outbox():
    """End-to-end sanity check: send_mail() reaches the active backend.
    Django's test runner overrides EMAIL_BACKEND to locmem, which captures
    sends in mail.outbox — proving the dispatch chain is hooked up. The
    real Resend backend gets exercised manually after deploy."""
    with override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ):
        mail.outbox = []
        mail.send_mail(
            subject="ci-test",
            message="body",
            from_email=None,  # falls back to DEFAULT_FROM_EMAIL
            recipient_list=["someone@example.com"],
        )
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "ci-test"
        assert mail.outbox[0].from_email == settings.DEFAULT_FROM_EMAIL
        assert mail.outbox[0].to == ["someone@example.com"]


def test_prod_with_api_key_selects_resend_backend(monkeypatch, settings_module_reload):
    """When DEBUG=False and RESEND_API_KEY is set, anymail's Resend backend
    is the configured EMAIL_BACKEND. This is the production path."""
    monkeypatch.setenv("DJANGO_DEBUG", "False")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key_not_real")
    reloaded = settings_module_reload()
    assert reloaded.EMAIL_BACKEND == "anymail.backends.resend.EmailBackend"


def test_prod_without_api_key_falls_back_to_console(monkeypatch, settings_module_reload):
    """Defense in depth: if the API key is ever lost or unset, the app
    shouldn't crash on send_mail() — it logs the would-be message to
    stdout via the console backend instead."""
    monkeypatch.setenv("DJANGO_DEBUG", "False")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    reloaded = settings_module_reload()
    assert reloaded.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"


def test_dev_uses_console_backend_regardless(monkeypatch, settings_module_reload):
    """In DEBUG=True, we always use console — even if an API key is set —
    so local dev never accidentally sends real email."""
    monkeypatch.setenv("DJANGO_DEBUG", "True")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key_not_real")
    reloaded = settings_module_reload()
    assert reloaded.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"
