"""Pytest fixtures for apps.accounts tests."""
import importlib

import pytest


@pytest.fixture
def settings_module_reload():
    """Re-import config.settings under the current process environment.

    Settings.py reads env vars at module import time, so testing the
    conditional branches (e.g. EMAIL_BACKEND selection based on DEBUG +
    RESEND_API_KEY) requires forcing a fresh import after the env has
    been patched. Returns the reloaded module so the test can assert
    on its top-level attributes.
    """
    def _reload():
        import config.settings
        return importlib.reload(config.settings)
    return _reload
