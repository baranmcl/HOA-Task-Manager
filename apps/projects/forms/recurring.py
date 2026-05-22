from django import forms

from ..models import Project

_INPUT = {"class": "input"}
_TEXTAREA = {"class": "input", "rows": 4}


class RecurringTemplateForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "description", "category", "priority",
                  "recurrence_rule", "next_due_date", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs=_INPUT),
            "description": forms.Textarea(attrs=_TEXTAREA),
            "category": forms.Select(attrs=_INPUT),
            "priority": forms.Select(attrs=_INPUT),
            "recurrence_rule": forms.Select(attrs=_INPUT),
            "next_due_date": forms.DateInput(attrs={**_INPUT, "type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("recurrence_rule"):
            self.add_error("recurrence_rule", "Required for recurring templates.")
        if not cleaned.get("next_due_date"):
            self.add_error("next_due_date", "Required for recurring templates.")
        return cleaned
