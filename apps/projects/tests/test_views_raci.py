import pytest
from django.urls import reverse

from apps.projects.models import RACIAssignment, RACIRole


@pytest.mark.django_db
def test_add_raci(auth_client, project, person):
    response = auth_client.post(
        reverse("projects:raci_add", args=[project.pk]),
        {"person": person.pk, "role": RACIRole.RESPONSIBLE},
    )
    assert response.status_code == 200
    assert RACIAssignment.objects.filter(project=project, person=person).exists()


@pytest.mark.django_db
def test_add_duplicate_role_rejected(auth_client, project, person):
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    response = auth_client.post(
        reverse("projects:raci_add", args=[project.pk]),
        {"person": person.pk, "role": RACIRole.RESPONSIBLE},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_remove_raci(auth_client, project, person):
    a = RACIAssignment.objects.create(project=project, person=person, role=RACIRole.CONSULTED)
    response = auth_client.post(reverse("projects:raci_remove", args=[a.pk]))
    assert response.status_code == 200
    assert not RACIAssignment.objects.filter(pk=a.pk).exists()


@pytest.mark.django_db
def test_person_in_one_role_can_be_added_to_another(auth_client, project, person):
    """Bug fix: the data model permits the same person in multiple roles on
    the same project. Adding (person, Responsible) then (person, Consulted)
    should succeed; only an exact (project, person, role) duplicate is rejected.
    """
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    response = auth_client.post(
        reverse("projects:raci_add", args=[project.pk]),
        {"person": person.pk, "role": RACIRole.CONSULTED},
    )
    assert response.status_code == 200
    assert RACIAssignment.objects.filter(
        project=project, person=person, role=RACIRole.CONSULTED,
    ).exists()


@pytest.mark.django_db
def test_detail_page_dropdown_lists_already_assigned_person(auth_client, project, person):
    """A person already in one RACI role still appears in the 'Select person...'
    dropdown so they can be assigned to additional roles.
    """
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    assert person in list(response.context["available_people"])


@pytest.mark.django_db
def test_raci_section_role_select_has_explicit_width(auth_client, project):
    """Regression guard: the role select must carry a width-override class
    so it does not claim the entire flex row, collapsing the person select
    to zero width. See fix-raci-dropdown-layout branch.
    """
    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    html = response.content.decode()
    assert 'name="role" class="input w-40 shrink-0"' in html
