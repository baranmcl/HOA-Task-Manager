import pytest
from django.core.management import call_command

from apps.projects.models import ProjectCategory


@pytest.mark.django_db
def test_seed_creates_seven_categories_including_misc():
    call_command("seed_categories")
    assert ProjectCategory.objects.count() == 7
    assert ProjectCategory.objects.filter(name="Misc", display_order=7).exists()


@pytest.mark.django_db
def test_seed_is_idempotent():
    call_command("seed_categories")
    call_command("seed_categories")
    assert ProjectCategory.objects.count() == 7
