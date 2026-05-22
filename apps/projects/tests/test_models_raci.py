import pytest
from django.db import IntegrityError

from apps.projects.models import RACIAssignment, RACIRole


@pytest.mark.django_db
def test_assign_responsible(project, person):
    a = RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    assert a.role == "responsible"


@pytest.mark.django_db
def test_same_person_multiple_roles_allowed(project, person):
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.ACCOUNTABLE)
    assert RACIAssignment.objects.filter(project=project, person=person).count() == 2


@pytest.mark.django_db
def test_duplicate_role_for_same_person_blocked(project, person):
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    with pytest.raises(IntegrityError):
        RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)


@pytest.mark.django_db
def test_multiple_people_same_role(project, person, db):
    from apps.roster.models import RosterPerson
    other = RosterPerson.objects.create(name="Jane Doe")
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.CONSULTED)
    RACIAssignment.objects.create(project=project, person=other, role=RACIRole.CONSULTED)
    assert RACIAssignment.objects.filter(project=project, role=RACIRole.CONSULTED).count() == 2
