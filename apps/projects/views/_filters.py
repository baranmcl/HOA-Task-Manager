"""Shared person-filter helper used by the dashboard and the calendar.

Resolves the `?person=` query parameter against the authenticated user's
linked roster_person profile, returning a tuple the view can hand directly
to its queryset and template context.
"""


def resolve_person_filter(request):
    """Returns (person_id_or_None, show_unlinked_banner, selected_value).

    - person_id_or_None: the RosterPerson pk to filter on, or None for "show all".
    - show_unlinked_banner: always False. The dashboard/calendar default to
      "all people" regardless of whether the user has linked their roster
      person, so there's no useful nudge to surface. Kept in the return
      tuple so callers don't need to change their unpacking shape.
    - selected_value: the value to render in the dropdown — "all", a numeric
      pk as a string. Defaults to "all" when nothing is explicitly chosen.
    """
    raw = request.GET.get("person")

    if raw and raw.isdigit():
        return int(raw), False, raw
    # Everything else — "all", missing, empty, or invalid — falls through to
    # the "show everyone" default.
    return None, False, "all"
