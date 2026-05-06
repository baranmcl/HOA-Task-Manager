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
