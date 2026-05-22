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
