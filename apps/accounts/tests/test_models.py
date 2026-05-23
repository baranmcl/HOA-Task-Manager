import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import UserProfile
from apps.roster.models import RosterPerson


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


@pytest.mark.django_db
def test_userprofile_roster_person_round_trips():
    User = get_user_model()
    user = User.objects.create_user(
        username="carol@example.com",
        email="carol@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    person = RosterPerson.objects.create(name="Carol Davis", role_title="Secretary")
    user.profile.roster_person = person
    user.profile.save()
    user.profile.refresh_from_db()
    assert user.profile.roster_person == person


@pytest.mark.django_db
def test_userprofile_roster_person_set_null_on_person_delete():
    User = get_user_model()
    user = User.objects.create_user(
        username="dave@example.com",
        email="dave@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    person = RosterPerson.objects.create(name="Dave Diaz")
    user.profile.roster_person = person
    user.profile.save()
    person.delete()
    user.profile.refresh_from_db()
    assert user.profile.roster_person is None


@pytest.mark.django_db
def test_userprofile_roster_person_defaults_to_none():
    User = get_user_model()
    user = User.objects.create_user(
        username="eve@example.com",
        email="eve@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    assert user.profile.roster_person is None
