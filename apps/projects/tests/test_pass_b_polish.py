"""Tests for the Pass B polish round: calendar category/status filters,
clear-filters affordance, color-coded checklist borders, legend
visibility, and the new Help page.
"""
import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import (
    ChecklistItem,
    Project,
    ProjectCategory,
    ProjectStatus,
)
from apps.projects.views.calendar import (
    CHECKLIST_BORDER_PALETTE,
    project_border_class,
)
from apps.roster.models import RosterPerson

# ---- Calendar category + status filters ----------------------------------

@pytest.mark.django_db
def test_calendar_category_filter_scopes_projects(auth_client, user):
    landscaping = ProjectCategory.objects.create(name="Landscaping", display_order=1)
    pool = ProjectCategory.objects.create(name="Pool", display_order=2)
    Project.objects.create(
        title="Landscape", category=landscaping, created_by=user,
        projected_completion_date=dt.date(2026, 5, 15),
    )
    Project.objects.create(
        title="Pool fix", category=pool, created_by=user,
        projected_completion_date=dt.date(2026, 5, 15),
    )
    response = auth_client.get(
        reverse("projects:calendar_at", args=[2026, 5]) + f"?category={landscaping.pk}",
    )
    content = response.content.decode()
    assert "Landscape" in content
    assert "Pool fix" not in content


@pytest.mark.django_db
def test_calendar_status_filter_scopes_projects(auth_client, user, category):
    Project.objects.create(
        title="Active one", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=dt.date(2026, 5, 15),
    )
    Project.objects.create(
        title="Delayed one", category=category, created_by=user,
        status=ProjectStatus.DELAYED, delay_reason="vendor backed out",
        projected_completion_date=dt.date(2026, 5, 15),
    )
    response = auth_client.get(
        reverse("projects:calendar_at", args=[2026, 5]) + "?status=delayed",
    )
    content = response.content.decode()
    assert "Delayed one" in content
    assert "Active one" not in content


@pytest.mark.django_db
def test_calendar_category_filter_also_scopes_checklist_items(auth_client, user):
    landscaping = ProjectCategory.objects.create(name="Landscaping", display_order=1)
    pool = ProjectCategory.objects.create(name="Pool", display_order=2)
    p1 = Project.objects.create(
        title="Landscape", category=landscaping, created_by=user,
    )
    p2 = Project.objects.create(title="Pool fix", category=pool, created_by=user)
    ChecklistItem.objects.create(
        project=p1, text="Mow lawn", due_date=dt.date(2026, 5, 10), order=0,
    )
    ChecklistItem.objects.create(
        project=p2, text="Drain pool", due_date=dt.date(2026, 5, 10), order=0,
    )
    response = auth_client.get(
        reverse("projects:calendar_at", args=[2026, 5]) + f"?category={landscaping.pk}",
    )
    content = response.content.decode()
    assert "Mow lawn" in content
    assert "Drain pool" not in content


# ---- Clear filters on calendar ------------------------------------------

@pytest.mark.django_db
def test_calendar_clear_filters_link_hidden_when_no_filters(auth_client):
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    assert response.context["any_filter_active"] is False
    assert "Clear filters" not in response.content.decode()


@pytest.mark.django_db
def test_calendar_clear_filters_link_shown_when_category_set(auth_client):
    category = ProjectCategory.objects.create(name="X", display_order=1)
    response = auth_client.get(
        reverse("projects:calendar_at", args=[2026, 5]) + f"?category={category.pk}",
    )
    assert response.context["any_filter_active"] is True
    assert "Clear filters" in response.content.decode()


@pytest.mark.django_db
def test_calendar_clear_filters_link_shown_when_person_set(auth_client):
    mike = RosterPerson.objects.create(name="Mike")
    response = auth_client.get(
        reverse("projects:calendar_at", args=[2026, 5]) + f"?person={mike.pk}",
    )
    assert response.context["any_filter_active"] is True
    assert "Clear filters" in response.content.decode()


@pytest.mark.django_db
def test_calendar_clear_filters_link_hidden_when_person_all(auth_client):
    """?person=all is the 'no filter' sentinel, not an active filter."""
    response = auth_client.get(
        reverse("projects:calendar_at", args=[2026, 5]) + "?person=all",
    )
    assert response.context["any_filter_active"] is False


# ---- Color-coded checklist borders ---------------------------------------

def test_project_border_class_is_deterministic():
    """Same project pk → same color class, every time."""
    assert project_border_class(1) == project_border_class(1)
    assert project_border_class(7) == project_border_class(7)


def test_project_border_class_distributes_across_palette():
    """Each palette slot is reachable by some project pk."""
    seen = {project_border_class(i) for i in range(50)}
    assert seen == set(CHECKLIST_BORDER_PALETTE)


@pytest.mark.django_db
def test_checklist_item_renders_with_border_color(auth_client, user, category):
    project = Project.objects.create(
        title="Bike Reno", category=category, created_by=user,
    )
    ChecklistItem.objects.create(
        project=project, text="Survey", due_date=dt.date(2026, 5, 15), order=0,
    )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    content = response.content.decode()
    expected_class = project_border_class(project.pk)
    assert expected_class in content


@pytest.mark.django_db
def test_two_items_same_project_share_border_color(auth_client, user, category):
    project = Project.objects.create(
        title="Bike Reno", category=category, created_by=user,
    )
    ChecklistItem.objects.create(
        project=project, text="Step 1", due_date=dt.date(2026, 5, 10), order=0,
    )
    ChecklistItem.objects.create(
        project=project, text="Step 2", due_date=dt.date(2026, 5, 20), order=1,
    )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    items = []
    for week in response.context["weeks"]:
        for cell in week:
            items.extend(cell["checklist_items"])
    relevant = [i for i in items if i.project_id == project.pk]
    assert len(relevant) == 2
    assert relevant[0].border_class == relevant[1].border_class


@pytest.mark.django_db
def test_two_items_different_projects_get_different_pk_colors(
    auth_client, user, category,
):
    """Different project pks generally yield different colors, modulo
    the palette cycle. With pk=1 and pk=2 the colors must differ."""
    p1 = Project.objects.create(
        title="One", category=category, created_by=user,
    )
    p2 = Project.objects.create(
        title="Two", category=category, created_by=user,
    )
    ChecklistItem.objects.create(
        project=p1, text="A", due_date=dt.date(2026, 5, 10), order=0,
    )
    ChecklistItem.objects.create(
        project=p2, text="B", due_date=dt.date(2026, 5, 10), order=0,
    )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    items = []
    for week in response.context["weeks"]:
        for cell in week:
            items.extend(cell["checklist_items"])
    if p1.pk % len(CHECKLIST_BORDER_PALETTE) != p2.pk % len(CHECKLIST_BORDER_PALETTE):
        colors = {i.border_class for i in items}
        assert len(colors) >= 2


# ---- Legend visibility ---------------------------------------------------

@pytest.mark.django_db
def test_calendar_legend_present(auth_client):
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    content = response.content.decode()
    assert "Legend" in content
    assert "what the colors mean" in content


# ---- Help page -----------------------------------------------------------

@pytest.mark.django_db
def test_help_page_requires_login(client):
    response = client.get(reverse("help"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_help_page_renders_for_authed_user(auth_client):
    response = auth_client.get(reverse("help"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Help &amp; how-to" in content or "Help & how-to" in content


@pytest.mark.django_db
def test_help_page_has_all_main_sections(auth_client):
    """Each major section anchor should be in the page so the in-page
    'Jump to' links work."""
    response = auth_client.get(reverse("help"))
    content = response.content.decode()
    for anchor in [
        "getting-started", "workflows", "raci", "groups",
        "views", "invites", "faq",
    ]:
        assert f'id="{anchor}"' in content


@pytest.mark.django_db
def test_sidebar_includes_help_link(auth_client):
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    assert ">Help<" in content
    assert reverse("help") in content
