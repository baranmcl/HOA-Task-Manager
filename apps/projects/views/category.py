from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import ProjectCategoryForm
from ..models import ProjectCategory


def _categories_with_counts():
    """All categories, each annotated with how many projects reference it."""
    return ProjectCategory.objects.annotate(project_count=Count("projects"))


@login_required
def category_list(request):
    return render(request, "projects/category_list.html", {
        "categories": _categories_with_counts(),
        "add_form": ProjectCategoryForm(),
    })


@login_required
def category_add(request):
    if request.method != "POST":
        return redirect("projects:category_list")
    form = ProjectCategoryForm(request.POST)
    if form.is_valid():
        category = form.save(commit=False)
        max_order = ProjectCategory.objects.aggregate(m=Max("display_order"))["m"] or 0
        category.display_order = max_order + 1
        category.save()
        messages.success(request, f"Added category “{category.name}”.")
        return redirect("projects:category_list")
    # Invalid: re-render the page with the bound form so errors appear inline.
    return render(request, "projects/category_list.html", {
        "categories": _categories_with_counts(),
        "add_form": form,
    })


@login_required
def category_rename(request, pk):
    if request.method != "POST":
        return redirect("projects:category_list")
    category = get_object_or_404(ProjectCategory, pk=pk)
    new_name = request.POST.get("name", "").strip()
    if not new_name:
        messages.error(request, "Category name cannot be blank.")
    elif ProjectCategory.objects.exclude(pk=pk).filter(name=new_name).exists():
        messages.error(request, f"A category named “{new_name}” already exists.")
    else:
        category.name = new_name
        category.save()
        messages.success(request, "Category renamed.")
    return redirect("projects:category_list")
