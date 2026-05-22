from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from ..models import ProjectCategory


def _categories_with_counts():
    """All categories, each annotated with how many projects reference it."""
    return ProjectCategory.objects.annotate(project_count=Count("projects"))


@login_required
def category_list(request):
    return render(request, "projects/category_list.html", {
        "categories": _categories_with_counts(),
    })
