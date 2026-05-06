import zoneinfo

from django import forms

from .models import UserProfile


def _timezone_choices():
    return [(tz, tz) for tz in sorted(zoneinfo.available_timezones())]


class ProfileForm(forms.ModelForm):
    timezone = forms.ChoiceField(
        choices=_timezone_choices,
        widget=forms.Select(attrs={"class": "input"}),
    )

    class Meta:
        model = UserProfile
        fields = ["timezone"]
