import zoneinfo

from django import forms
from django.contrib.auth import get_user_model

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


class InviteUserForm(forms.Form):
    """Form for staff to invite a new user by email.

    The new user is created with set_unusable_password() — they activate
    the account by clicking a token-signed link in their invite email
    (the same /reset/<uidb64>/<token>/ URL Django uses for password reset).
    """

    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": "input", "autocomplete": "off"}),
        help_text="The invitee will sign in with this email and receive the activation link here.",
    )
    first_name = forms.CharField(
        label="First name",
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={"class": "input"}),
    )
    last_name = forms.CharField(
        label="Last name",
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={"class": "input"}),
    )
    roster_person = forms.ModelChoiceField(
        label="Link to roster person (optional)",
        queryset=RosterPerson.active.all(),
        required=False,
        widget=forms.Select(attrs={"class": "input"}),
        empty_label="— not linked —",
        help_text="Lets activity feeds show this user's name as their roster identity.",
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "A user with this email already exists. "
                "If they've lost access, send them a password-reset link instead."
            )
        return email
