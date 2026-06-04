import datetime as dt

from django.contrib.auth.decorators import login_required
from django.db.models import Case, Count, IntegerField, Q, When
from django.shortcuts import render

from apps.roster.models import RosterPerson

from ..models import Project, ProjectCategory, ProjectStatus, RACIRole, Tag

SORT_CHOICES = {
    "updated": "-updated_at",
    "title": "title",
}


@login_required
def list_view(request):
    today = dt.date.today()
    qs = Project.instances.select_related("category").prefetch_related(
        "raci_assignments__person",
        "tags",
    ).annotate(
        note_count=Count("notes", distinct=True),
        attachment_count=Count("attachments", distinct=True),
    )

    # Dashboard-tile shortcut filters. Each implies a specific
    # combination of date + status filters; setting them takes precedence
    # over the explicit show_completed/status query params for clarity.
    overdue_only = request.GET.get("overdue") == "1"
    upcoming_only = request.GET.get("upcoming") == "1"
    completed_this_month = request.GET.get("completed_this_month") == "1"

    show_completed = request.GET.get("show_completed") == "1" or completed_this_month
    if not show_completed:
        qs = qs.exclude(status=ProjectStatus.COMPLETED)

    status = request.GET.get("status")
    if status in dict(ProjectStatus.choices):
        qs = qs.filter(status=status)

    if overdue_only:
        qs = qs.exclude(status=ProjectStatus.COMPLETED).filter(
            projected_completion_date__lt=today,
            projected_completion_date__isnull=False,
        )
    if upcoming_only:
        horizon = today + dt.timedelta(days=14)
        qs = qs.exclude(status=ProjectStatus.COMPLETED).filter(
            projected_completion_date__gte=today,
            projected_completion_date__lte=horizon,
        )
    if completed_this_month:
        first_of_month = today.replace(day=1)
        qs = qs.filter(
            status=ProjectStatus.COMPLETED,
            actual_completion_date__gte=first_of_month,
            actual_completion_date__lte=today,
        )

    cat_id = request.GET.get("category")
    if cat_id and cat_id.isdigit():
        qs = qs.filter(category_id=int(cat_id))

    person_id = request.GET.get("person")
    role = request.GET.get("role", "")
    role_valid = role in dict(RACIRole.choices)
    if person_id and person_id.isdigit() and role_valid:
        qs = qs.filter(
            raci_assignments__person_id=int(person_id),
            raci_assignments__role=role,
        ).distinct()
    elif person_id and person_id.isdigit():
        qs = qs.filter(raci_assignments__person_id=int(person_id)).distinct()
    elif role_valid:
        qs = qs.filter(raci_assignments__role=role).distinct()

    tag_slug = request.GET.get("tag", "").strip()
    if tag_slug:
        qs = qs.filter(tags__slug=tag_slug).distinct()

    due_raw = request.GET.get("due", "").strip()
    due_filter = None
    if due_raw:
        try:
            due_filter = dt.date.fromisoformat(due_raw)
            qs = qs.filter(projected_completion_date=due_filter)
        except ValueError:
            due_filter = None  # invalid — silently ignore

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

    # True when any non-default filter is active — drives the visibility
    # of the "Clear filters" link on the list page.
    any_filter_active = bool(
        q or status or cat_id or person_id or role or tag_slug or due_filter
        or show_completed or sort_key != "updated"
        or overdue_only or upcoming_only or completed_this_month
    )

    # Banner text shown when one of the dashboard tile shortcuts is in
    # play — gives the user context for the filtered view they landed on.
    shortcut_label = ""
    if overdue_only:
        shortcut_label = "Overdue projects"
    elif upcoming_only:
        shortcut_label = "Upcoming projects (next 14 days)"
    elif completed_this_month:
        shortcut_label = "Done this month"

    return render(request, "projects/list.html", {
        "projects": qs,
        "categories": ProjectCategory.objects.all(),
        "people": RosterPerson.active.all(),
        "tags": Tag.objects.all(),
        "selected_status": status or "",
        "selected_category": cat_id or "",
        "selected_person": person_id or "",
        "selected_role": role if role_valid else "",
        "selected_tag": tag_slug,
        "selected_sort": sort_key,
        "show_completed": show_completed,
        "q": q,
        "due_filter": due_filter,
        "overdue_only": overdue_only,
        "upcoming_only": upcoming_only,
        "completed_this_month": completed_this_month,
        "shortcut_label": shortcut_label,
        "any_filter_active": any_filter_active,
        "status_choices": ProjectStatus.choices,
        "role_choices": RACIRole.choices,
    })
