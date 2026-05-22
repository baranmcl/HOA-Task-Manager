from django import forms

from ..models import BoardApproval

_INPUT = {"class": "input"}


class BoardApprovalForm(forms.ModelForm):
    class Meta:
        model = BoardApproval
        fields = ["motion_text", "vote_date", "votes_for", "votes_against",
                  "votes_abstain", "minutes_reference"]
        widgets = {
            "motion_text": forms.Textarea(attrs={**_INPUT, "rows": 3}),
            "vote_date": forms.DateInput(attrs={**_INPUT, "type": "date"}),
            "votes_for": forms.NumberInput(attrs=_INPUT),
            "votes_against": forms.NumberInput(attrs=_INPUT),
            "votes_abstain": forms.NumberInput(attrs=_INPUT),
            "minutes_reference": forms.TextInput(attrs=_INPUT),
        }
