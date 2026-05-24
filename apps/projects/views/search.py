"""Full-text-ish search across projects, descriptions, and notes."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..models import Project, UpdateNote


@login_required
def search_view(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return render(request, "projects/search.html", {"q": "", "results": []})

    # Step 1 — projects whose title matches.
    title_hits = list(
        Project.instances.select_related("category")
        .filter(title__icontains=q)
        .order_by("-updated_at"),
    )
    title_ids = {p.pk for p in title_hits}

    # Step 2 — projects whose description matches (excluding title hits).
    desc_hits = list(
        Project.instances.select_related("category")
        .filter(description__icontains=q)
        .exclude(pk__in=title_ids)
        .order_by("-updated_at"),
    )
    desc_ids = {p.pk for p in desc_hits}

    # Step 3 — notes whose body matches (excluding projects already returned).
    note_hits = list(
        UpdateNote.objects.select_related("project__category")
        .filter(body__icontains=q)
        .exclude(project_id__in=title_ids | desc_ids)
        .order_by("-updated_at"),
    )
    # Group note hits by project, preserving newest-note-first ordering.
    notes_by_project: dict[int, list[UpdateNote]] = {}
    for n in note_hits:
        notes_by_project.setdefault(n.project_id, []).append(n)

    results = []
    for p in title_hits:
        results.append({"project": p, "match_reason": "title", "matched_notes": []})
    for p in desc_hits:
        results.append({"project": p, "match_reason": "description", "matched_notes": []})
    for _project_id, notes in notes_by_project.items():
        results.append({
            "project": notes[0].project,
            "match_reason": "notes",
            "matched_notes": notes,
        })

    return render(request, "projects/search.html", {"q": q, "results": results})
