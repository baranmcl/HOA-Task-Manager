import zoneinfo

from django import forms

from apps.roster.models import RosterPerson

from .models import UserProfile


def _timezone_choices():
    return [(tz, tz) for tz in sorted(zoneinfo.available_timezones())]


class ProfileForm(forms.ModelForm):
    timezone = forms.ChoiceField(
        choices=_timezone_choices,
        widget=forms.Select(attrs={"class": "input"}),
    )
    roster_person = forms.ModelChoiceField(
        queryset=RosterPerson.active.all(),
        required=False,
        widget=forms.Select(attrs={"class": "input"}),
        label="Linked roster person",
        help_text="Used to default the dashboard to your own tasks.",
        empty_label="— not linked —",
    )

    class Meta:
        model = UserProfile
        fields = ["timezone", "roster_person"]
