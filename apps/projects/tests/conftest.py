import pytest
from django.contrib.auth import get_user_model

from apps.projects.models import ProjectCategory
from apps.roster.models import RosterPerson


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        password="Sufficiently-Long-Pw-1",
    )


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def category(db):
    return ProjectCategory.objects.create(name="Capital", display_order=1)


@pytest.fixture
def person(db):
    return RosterPerson.objects.create(name="Mike Smith", role_title="Treasurer")


@pytest.fixture
def project(db, user, category):
    from apps.projects.models import Project
    return Project.objects.create(
        title="Sprinkler upgrade",
        category=category,
        created_by=user,
    )
