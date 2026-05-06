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
