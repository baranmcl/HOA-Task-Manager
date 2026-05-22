from django.contrib.auth.decorators import login_required
from django.db.models import Case, Count, IntegerField, Q, When
from django.shortcuts import render

from apps.roster.models import RosterPerson

from ..models import Project, ProjectCategory, ProjectStatus

SORT_CHOICES = {
    "updated": "-updated_at",
    "title": "title",
}


@login_required
def list_view(request):
    qs = Project.instances.select_related("category").prefetch_related(
        "raci_assignments__person",
    ).annotate(
        note_count=Count("notes", distinct=True),
        attachment_count=Count("attachments", distinct=True),
    )

    show_completed = request.GET.get("show_completed") == "1"
    if not show_completed:
        qs = qs.exclude(status=ProjectStatus.COMPLETED)

    status = request.GET.get("status")
    if status in dict(ProjectStatus.choices):
        qs = qs.filter(status=status)

    cat_id = request.GET.get("category")
    if cat_id and cat_id.isdigit():
        qs = qs.filter(category_id=int(cat_id))

    person_id = request.GET.get("person")
    if person_id and person_id.isdigit():
        qs = qs.filter(raci_assignments__person_id=int(person_id)).distinct()

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    sort_key = request.GET.get("sort", "updated")
    if sort_key == "priority":
        qs = qs.annotate(
            _priority_order=Case(
                When(priority="high", then=0),
                When(priority="medium", then=1),
                default=2,
                output_field=IntegerField(),
            )
        ).order_by("_priority_order", "title")
    elif sort_key == "due":
        # Django sqlite: place NULLs last via a synthetic boolean column
        qs = qs.extra(  # noqa: S608
            select={"_no_due": "projected_completion_date IS NULL"}
        ).order_by("_no_due", "projected_completion_date")
    else:
        order_field = SORT_CHOICES.get(sort_key, "-updated_at")
        qs = qs.order_by(order_field)

    return render(request, "projects/list.html", {
        "projects": qs,
        "categories": ProjectCategory.objects.all(),
        "people": RosterPerson.active.all(),
        "selected_status": status or "",
        "selected_category": cat_id or "",
        "selected_person": person_id or "",
        "selected_sort": sort_key,
        "show_completed": show_completed,
        "q": q,
        "status_choices": ProjectStatus.choices,
    })
