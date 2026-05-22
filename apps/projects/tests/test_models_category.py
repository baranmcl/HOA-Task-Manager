import pytest

from apps.projects.models import ProjectCategory, Tag


@pytest.mark.django_db
def test_create_category():
    c = ProjectCategory.objects.create(name="Capital", display_order=1)
    assert c.name == "Capital"
    assert str(c) == "Capital"


@pytest.mark.django_db
def test_category_name_unique():
    ProjectCategory.objects.create(name="Capital", display_order=1)
    with pytest.raises(Exception):  # noqa: B017
        ProjectCategory.objects.create(name="Capital", display_order=2)


@pytest.mark.django_db
def test_category_default_ordering():
    ProjectCategory.objects.create(name="Beta", display_order=2)
    ProjectCategory.objects.create(name="Alpha", display_order=1)
    names = list(ProjectCategory.objects.values_list("name", flat=True))
    assert names == ["Alpha", "Beta"]


@pytest.mark.django_db
def test_create_tag_slugifies_name():
    t = Tag.objects.create(name="Sprinkler Repair")
    assert t.slug == "sprinkler-repair"
    assert str(t) == "Sprinkler Repair"


@pytest.mark.django_db
def test_tag_get_or_create_normalizes_case():
    t1 = Tag.get_or_create_from_input("Concrete")
    t2 = Tag.get_or_create_from_input("concrete")
    assert t1.pk == t2.pk
