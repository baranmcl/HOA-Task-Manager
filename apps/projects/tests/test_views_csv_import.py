import io

import pytest
from django.urls import reverse

from apps.projects.models import ActivityLog, Project, RACIAssignment, RACIRole
from apps.roster.models import RosterPerson


def _upload(text):
    f = io.BytesIO(text.encode("utf-8"))
    f.name = "import.csv"
    return f


@pytest.mark.django_db
def test_import_form_requires_login(client):
    response = client.get(reverse("projects:import_form"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_import_form_renders(auth_client):
    response = auth_client.get(reverse("projects:import_form"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Import projects" in content
    assert "Download template" in content


@pytest.mark.django_db
def test_import_template_download(auth_client):
    response = auth_client.get(reverse("projects:import_template"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    body = response.content.decode()
    assert "title" in body.lower()
    assert "category" in body.lower()
    assert body.count("\n") >= 2


@pytest.mark.django_db
def test_import_preview_shows_valid_and_rejected(auth_client, category):
    csv_text = (
        "title,category\n"
        f"Good row,{category.name}\n"
        "Bad row,Unknown Category\n"
    )
    response = auth_client.post(
        reverse("projects:import_form"),
        {"file": _upload(csv_text)},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Good row" in content
    assert "Bad row" in content
    assert "Unknown category" in content


@pytest.mark.django_db
def test_import_confirm_creates_projects(auth_client, user, category):
    csv_text = f"title,category\nFoo,{category.name}\nBar,{category.name}\n"
    auth_client.post(
        reverse("projects:import_form"),
        {"file": _upload(csv_text)},
    )
    response = auth_client.post(reverse("projects:import_confirm"))
    assert response.status_code == 302
    assert Project.objects.filter(title="Foo").count() == 1
    assert Project.objects.filter(title="Bar").count() == 1
    assert ActivityLog.objects.filter(
        actor=user, verb="imported via CSV",
    ).count() == 2


@pytest.mark.django_db
def test_import_confirm_creates_raci_when_responsible_set(auth_client, category):
    jane = RosterPerson.objects.create(name="Jane Doe")
    csv_text = (
        "title,category,responsible\n"
        f"Foo,{category.name},Jane Doe\n"
    )
    auth_client.post(
        reverse("projects:import_form"),
        {"file": _upload(csv_text)},
    )
    auth_client.post(reverse("projects:import_confirm"))
    project = Project.objects.get(title="Foo")
    raci = RACIAssignment.objects.get(project=project)
    assert raci.person == jane
    assert raci.role == RACIRole.RESPONSIBLE


@pytest.mark.django_db
def test_import_confirm_without_preview_redirects(auth_client):
    response = auth_client.post(reverse("projects:import_confirm"))
    assert response.status_code == 302
    assert response.url == reverse("projects:import_form")


@pytest.mark.django_db
def test_import_empty_file_shows_error(auth_client):
    response = auth_client.post(
        reverse("projects:import_form"),
        {"file": _upload("")},
    )
    assert response.status_code == 200
    assert "header" in response.content.decode().lower()


@pytest.mark.django_db
def test_import_no_file_shows_error(auth_client):
    response = auth_client.post(reverse("projects:import_form"), {})
    assert response.status_code == 200
    assert "file" in response.content.decode().lower()


@pytest.mark.django_db
def test_sidebar_includes_import_link(auth_client):
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    assert "Import projects" in content
    assert reverse("projects:import_form") in content


@pytest.mark.django_db
def test_import_only_valid_rows_get_created_on_confirm(auth_client, category):
    csv_text = (
        "title,category\n"
        f"Good,{category.name}\n"
        "Bad,Nope\n"
    )
    auth_client.post(
        reverse("projects:import_form"),
        {"file": _upload(csv_text)},
    )
    auth_client.post(reverse("projects:import_confirm"))
    assert Project.objects.filter(title="Good").exists()
    assert not Project.objects.filter(title="Bad").exists()
