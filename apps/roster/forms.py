from django import forms

from .models import RosterGroup, RosterPerson


class RosterPersonForm(forms.ModelForm):
    class Meta:
        model = RosterPerson
        fields = ["name", "email", "phone", "role_title", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "email": forms.EmailInput(attrs={"class": "input"}),
            "phone": forms.TextInput(attrs={"class": "input"}),
            "role_title": forms.TextInput(attrs={"class": "input"}),
            "notes": forms.Textarea(attrs={"class": "input", "rows": 4}),
        }


class RosterGroupForm(forms.ModelForm):
    class Meta:
        model = RosterGroup
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. Finance Committee",
            }),
            "description": forms.Textarea(attrs={
                "class": "input", "rows": 3,
                "placeholder": "Optional. What does this group do?",
            }),
        }
