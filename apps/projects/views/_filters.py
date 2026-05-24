"""Shared person-filter helper used by the dashboard and the calendar.

Resolves the `?person=` query parameter against the authenticated user's
linked roster_person profile, returning a tuple the view can hand directly
to its queryset and template context.
"""


def resolve_person_filter(request):
    """Returns (person_id_or_None, show_unlinked_banner, selected_value).

    - person_id_or_None: the RosterPerson pk to filter on, or None for "show all".
    - show_unlinked_banner: True only when the user has no roster_person link
      AND did not explicitly choose `?person=all` or `?person=<id>` themselves.
    - selected_value: the value to render in the dropdown — "all", a numeric
      pk as a string, or "" if no explicit choice was made.
    """
    raw = request.GET.get("person")
    linked = getattr(request.user.profile, "roster_person", None)

    if raw == "all":
        return None, False, "all"
    if raw and raw.isdigit():
        return int(raw), False, raw
    # No explicit choice — auto-default to linked person if available.
    if linked is not None:
        return linked.pk, False, str(linked.pk)
    return None, True, ""
