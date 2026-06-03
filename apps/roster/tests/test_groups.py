"""Tests for RosterGroup + GroupMembership: models, management views,
and the RACI group-expansion flow on the project detail page.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse

from apps.projects.models import (
    Project,
    ProjectCategory,
    RACIAssignment,
    RACIRole,
)
from apps.roster.models import GroupMembership, RosterGroup, RosterPerson


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="staff@example.com", email="staff@example.com",
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
def project(db, user, category):
    return Project.objects.create(
        title="Bike room renovation", category=category, created_by=user,
    )


@pytest.fixture
def finance_committee(db):
    return RosterGroup.objects.create(
        name="Finance Committee", description="Budget oversight.",
    )


@pytest.fixture
def mike(db):
    return RosterPerson.objects.create(name="Mike Smith")


@pytest.fixture
def laurel(db):
    return RosterPerson.objects.create(name="Laurel Baran")


# ---- Model tests --------------------------------------------------------

@pytest.mark.django_db
def test_create_roster_group():
    g = RosterGroup.objects.create(name="Pool Committee")
    assert g.name == "Pool Committee"
    assert g.description == ""
    assert g.member_count == 0


@pytest.mark.django_db
def test_roster_group_name_must_be_unique():
    RosterGroup.objects.create(name="Finance Committee")
    with pytest.raises(IntegrityError):
        RosterGroup.objects.create(name="Finance Committee")


@pytest.mark.django_db
def test_group_membership_creation(finance_committee, mike):
    m = GroupMembership.objects.create(group=finance_committee, person=mike)
    assert m.group == finance_committee
    assert m.person == mike
    assert finance_committee.member_count == 1


@pytest.mark.django_db
def test_group_membership_unique_per_pair(finance_committee, mike):
    GroupMembership.objects.create(group=finance_committee, person=mike)
    with pytest.raises(IntegrityError):
        GroupMembership.objects.create(group=finance_committee, person=mike)


@pytest.mark.django_db
def test_active_members_excludes_archived(finance_committee, mike, laurel):
    GroupMembership.objects.create(group=finance_committee, person=mike)
    GroupMembership.objects.create(group=finance_committee, person=laurel)
    laurel.archived = True
    laurel.save()
    actives = list(finance_committee.active_members())
    assert mike in actives
    assert laurel not in actives


@pytest.mark.django_db
def test_raci_assignment_has_source_group_field(project, mike, finance_committee):
    a = RACIAssignment.objects.create(
        project=project, person=mike, role=RACIRole.RESPONSIBLE,
        source_group=finance_committee,
    )
    assert a.source_group == finance_committee


# ---- Group management view tests ----------------------------------------

@pytest.mark.django_db
def test_group_list_requires_login(client):
    response = client.get(reverse("roster:group_list"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_group_list_renders(auth_client, finance_committee):
    response = auth_client.get(reverse("roster:group_list"))
    assert response.status_code == 200
    assert "Finance Committee" in response.content.decode()


@pytest.mark.django_db
def test_group_create(auth_client):
    response = auth_client.post(reverse("roster:group_create"), {
        "name": "Architecture Committee",
        "description": "Reviews exterior modifications.",
    })
    assert response.status_code == 302
    assert RosterGroup.objects.filter(name="Architecture Committee").exists()


@pytest.mark.django_db
def test_group_detail_shows_members_and_available_people(
    auth_client, finance_committee, mike, laurel,
):
    GroupMembership.objects.create(group=finance_committee, person=mike)
    response = auth_client.get(reverse("roster:group_detail",
                                       kwargs={"pk": finance_committee.pk}))
    content = response.content.decode()
    assert "Mike Smith" in content
    # Laurel is not a member yet so she's in the "add" dropdown.
    assert "Laurel Baran" in content


@pytest.mark.django_db
def test_group_member_add(auth_client, finance_committee, mike):
    response = auth_client.post(
        reverse("roster:group_member_add", kwargs={"pk": finance_committee.pk}),
        {"person": str(mike.pk)},
    )
    assert response.status_code == 302
    assert GroupMembership.objects.filter(
        group=finance_committee, person=mike,
    ).exists()


@pytest.mark.django_db
def test_group_member_add_idempotent(auth_client, finance_committee, mike):
    GroupMembership.objects.create(group=finance_committee, person=mike)
    auth_client.post(
        reverse("roster:group_member_add", kwargs={"pk": finance_committee.pk}),
        {"person": str(mike.pk)},
    )
    assert GroupMembership.objects.filter(
        group=finance_committee, person=mike,
    ).count() == 1


@pytest.mark.django_db
def test_group_member_add_rejects_archived_person(auth_client, finance_committee, mike):
    mike.archived = True
    mike.save()
    auth_client.post(
        reverse("roster:group_member_add", kwargs={"pk": finance_committee.pk}),
        {"person": str(mike.pk)},
    )
    assert not GroupMembership.objects.filter(
        group=finance_committee, person=mike,
    ).exists()


@pytest.mark.django_db
def test_group_member_remove(auth_client, finance_committee, mike):
    m = GroupMembership.objects.create(group=finance_committee, person=mike)
    response = auth_client.post(
        reverse("roster:group_member_remove", kwargs={"pk": m.pk}),
    )
    assert response.status_code == 302
    assert not GroupMembership.objects.filter(pk=m.pk).exists()


@pytest.mark.django_db
def test_group_delete_keeps_raci_assignments_but_clears_source_group(
    auth_client, project, finance_committee, mike,
):
    a = RACIAssignment.objects.create(
        project=project, person=mike, role=RACIRole.RESPONSIBLE,
        source_group=finance_committee,
    )
    auth_client.post(reverse("roster:group_delete",
                             kwargs={"pk": finance_committee.pk}))
    a.refresh_from_db()
    assert a.source_group is None
    assert RACIAssignment.objects.filter(pk=a.pk).exists()


# ---- RACI group-expansion view tests ------------------------------------

@pytest.mark.django_db
def test_raci_add_group_expands_to_individual_assignments(
    auth_client, project, finance_committee, mike, laurel,
):
    GroupMembership.objects.create(group=finance_committee, person=mike)
    GroupMembership.objects.create(group=finance_committee, person=laurel)
    response = auth_client.post(
        reverse("projects:raci_add_group", kwargs={"pk": project.pk}),
        {"group": str(finance_committee.pk), "role": RACIRole.CONSULTED},
    )
    assert response.status_code == 200
    assignments = project.raci_assignments.all()
    assert assignments.count() == 2
    assert {a.person.name for a in assignments} == {"Mike Smith", "Laurel Baran"}
    for a in assignments:
        assert a.role == RACIRole.CONSULTED
        assert a.source_group == finance_committee


@pytest.mark.django_db
def test_raci_add_group_skips_archived_members(
    auth_client, project, finance_committee, mike, laurel,
):
    GroupMembership.objects.create(group=finance_committee, person=mike)
    GroupMembership.objects.create(group=finance_committee, person=laurel)
    laurel.archived = True
    laurel.save()
    auth_client.post(
        reverse("projects:raci_add_group", kwargs={"pk": project.pk}),
        {"group": str(finance_committee.pk), "role": RACIRole.CONSULTED},
    )
    assert project.raci_assignments.count() == 1
    assert project.raci_assignments.first().person == mike


@pytest.mark.django_db
def test_raci_add_group_idempotent_on_existing_pairs(
    auth_client, project, finance_committee, mike,
):
    GroupMembership.objects.create(group=finance_committee, person=mike)
    # Pre-existing direct assignment with no source_group.
    RACIAssignment.objects.create(
        project=project, person=mike, role=RACIRole.CONSULTED,
    )
    auth_client.post(
        reverse("projects:raci_add_group", kwargs={"pk": project.pk}),
        {"group": str(finance_committee.pk), "role": RACIRole.CONSULTED},
    )
    # No duplicate created; the existing row's source_group stays NULL
    # because get_or_create matched on (project, person, role) without
    # changing the existing record.
    assignments = project.raci_assignments.all()
    assert assignments.count() == 1
    assert assignments.first().source_group is None


@pytest.mark.django_db
def test_raci_add_group_membership_changes_dont_affect_existing_assignments(
    auth_client, project, finance_committee, mike, laurel,
):
    """Expand-at-add-time: removing a member from the group LATER does
    not retroactively remove them from the project's RACI."""
    GroupMembership.objects.create(group=finance_committee, person=mike)
    GroupMembership.objects.create(group=finance_committee, person=laurel)
    auth_client.post(
        reverse("projects:raci_add_group", kwargs={"pk": project.pk}),
        {"group": str(finance_committee.pk), "role": RACIRole.CONSULTED},
    )
    # Now remove Laurel from the group.
    GroupMembership.objects.filter(
        group=finance_committee, person=laurel,
    ).delete()
    # Laurel's RACI assignment on the project STAYS.
    assert project.raci_assignments.filter(person=laurel).exists()


@pytest.mark.django_db
def test_raci_add_group_rejects_invalid_role(auth_client, project, finance_committee):
    response = auth_client.post(
        reverse("projects:raci_add_group", kwargs={"pk": project.pk}),
        {"group": str(finance_committee.pk), "role": "not-a-role"},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_raci_add_group_rejects_invalid_group_id(auth_client, project):
    response = auth_client.post(
        reverse("projects:raci_add_group", kwargs={"pk": project.pk}),
        {"group": "abc", "role": RACIRole.RESPONSIBLE},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_raci_row_shows_via_group_annotation(
    auth_client, project, finance_committee, mike,
):
    RACIAssignment.objects.create(
        project=project, person=mike, role=RACIRole.RESPONSIBLE,
        source_group=finance_committee,
    )
    response = auth_client.get(reverse("projects:detail", kwargs={"pk": project.pk}))
    content = response.content.decode()
    assert "via Finance Committee" in content


@pytest.mark.django_db
def test_raci_row_no_annotation_for_individually_added(
    auth_client, project, mike,
):
    RACIAssignment.objects.create(
        project=project, person=mike, role=RACIRole.RESPONSIBLE,
    )
    response = auth_client.get(reverse("projects:detail", kwargs={"pk": project.pk}))
    content = response.content.decode()
    assert "via " not in content


@pytest.mark.django_db
def test_roster_list_links_to_groups(auth_client):
    response = auth_client.get(reverse("roster:list"))
    content = response.content.decode()
    assert reverse("roster:group_list") in content
    assert "Groups" in content
