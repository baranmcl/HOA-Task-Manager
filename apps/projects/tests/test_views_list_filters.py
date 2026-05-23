import pytest
from django.urls import reverse

from apps.projects.models import Project, RACIAssignment, RACIRole
from apps.roster.models import RosterPerson


@pytest.fixture
def mike(db):
    return RosterPerson.objects.create(name="Mike Smith")


@pytest.fixture
def laurel(db):
    return RosterPerson.objects.create(name="Laurel Baran")


@pytest.fixture
def two_projects_with_overlapping_raci(db, user, category, mike, laurel):
    """P1: Mike is Responsible. P2: Mike is Consulted, Laurel is Responsible."""
    p1 = Project.objects.create(title="P1", category=category, created_by=user)
    RACIAssignment.objects.create(project=p1, person=mike, role=RACIRole.RESPONSIBLE)
    p2 = Project.objects.create(title="P2", category=category, created_by=user)
    RACIAssignment.objects.create(project=p2, person=mike, role=RACIRole.CONSULTED)
    RACIAssignment.objects.create(project=p2, person=laurel, role=RACIRole.RESPONSIBLE)
    return p1, p2


@pytest.mark.django_db
def test_role_filter_alone(auth_client, two_projects_with_overlapping_raci):
    p1, p2 = two_projects_with_overlapping_raci
    response = auth_client.get(reverse("projects:list") + "?role=responsible")
    titles = [p.title for p in response.context["projects"]]
    assert "P1" in titles
    assert "P2" in titles  # P2 has Laurel as Responsible, so it qualifies


@pytest.mark.django_db
def test_role_filter_excludes_other_roles(auth_client, two_projects_with_overlapping_raci):
    """Filtering by role=accountable matches no project here."""
    response = auth_client.get(reverse("projects:list") + "?role=accountable")
    titles = [p.title for p in response.context["projects"]]
    assert titles == []


@pytest.mark.django_db
def test_combined_person_and_role_uses_single_join(
    auth_client, two_projects_with_overlapping_raci, mike,
):
    """Critical regression case: Mike Responsible must NOT match P2 (where
    Mike is Consulted, not Responsible). Two separate .filter() calls would
    incorrectly include P2 because Mike has SOME row on P2 and SOME row with
    role=Responsible (Laurel's). One combined .filter() correctly excludes P2.
    """
    response = auth_client.get(
        reverse("projects:list") + f"?person={mike.pk}&role=responsible"
    )
    titles = [p.title for p in response.context["projects"]]
    assert titles == ["P1"]


@pytest.mark.django_db
def test_invalid_role_falls_back_to_no_role_filter(
    auth_client, two_projects_with_overlapping_raci,
):
    response = auth_client.get(reverse("projects:list") + "?role=bogus")
    titles = [p.title for p in response.context["projects"]]
    assert set(titles) == {"P1", "P2"}


@pytest.mark.django_db
def test_list_renders_tag_pills_for_each_tag(auth_client, user, category):
    from apps.projects.models import Tag
    p = Project.objects.create(title="Tagged", category=category, created_by=user)
    p.tags.add(Tag.get_or_create_from_input("concrete"))
    p.tags.add(Tag.get_or_create_from_input("sprinklers"))
    response = auth_client.get(reverse("projects:list"))
    content = response.content.decode()
    assert "#concrete" in content
    assert "#sprinklers" in content


@pytest.mark.django_db
def test_tag_filter_returns_only_matching(auth_client, user, category):
    from apps.projects.models import Tag
    concrete = Tag.get_or_create_from_input("concrete")
    Tag.get_or_create_from_input("sprinklers")
    p1 = Project.objects.create(title="Has concrete", category=category, created_by=user)
    p1.tags.add(concrete)
    Project.objects.create(title="No tags", category=category, created_by=user)
    response = auth_client.get(reverse("projects:list") + f"?tag={concrete.slug}")
    titles = [p.title for p in response.context["projects"]]
    assert titles == ["Has concrete"]


@pytest.mark.django_db
def test_tag_filter_unknown_slug_returns_empty(auth_client, user, category):
    Project.objects.create(title="Anything", category=category, created_by=user)
    response = auth_client.get(reverse("projects:list") + "?tag=does-not-exist")
    titles = [p.title for p in response.context["projects"]]
    assert titles == []


@pytest.mark.django_db
def test_tag_filter_composes_with_status(auth_client, user, category):
    from apps.projects.models import Tag
    audit = Tag.get_or_create_from_input("audit")
    p1 = Project.objects.create(
        title="Audit, in progress", category=category, created_by=user,
        status="in_progress",
    )
    p1.tags.add(audit)
    p2 = Project.objects.create(
        title="Audit, not started", category=category, created_by=user,
        status="not_started",
    )
    p2.tags.add(audit)
    response = auth_client.get(
        reverse("projects:list") + f"?tag={audit.slug}&status=in_progress"
    )
    titles = [p.title for p in response.context["projects"]]
    assert titles == ["Audit, in progress"]
