from django import forms

from ..models import Project, ProjectStatus, Tag

_INPUT = {"class": "input"}
_TEXTAREA = {"class": "input", "rows": 4}


class ProjectForm(forms.ModelForm):
    FINANCIAL_FIELD_NAMES = (
        "budget_amount", "actual_cost", "vendor_name", "vendor_bid_amount",
    )

    tags_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={**_INPUT, "placeholder": "concrete, sprinklers"}),
        help_text="Comma-separated tags. Created automatically.",
    )

    class Meta:
        model = Project
        fields = [
            "title", "description", "category", "status", "delay_reason",
            "priority", "projected_completion_date",
            "budget_amount", "actual_cost", "vendor_name", "vendor_bid_amount",
        ]
        widgets = {
            "title": forms.TextInput(attrs=_INPUT),
            "description": forms.Textarea(attrs=_TEXTAREA),
            "category": forms.Select(attrs=_INPUT),
            "status": forms.Select(attrs=_INPUT),
            "delay_reason": forms.Textarea(attrs={**_TEXTAREA, "rows": 2}),
            "priority": forms.Select(attrs=_INPUT),
            "projected_completion_date": forms.DateInput(attrs={**_INPUT, "type": "date"}),
            "budget_amount": forms.NumberInput(attrs={**_INPUT, "step": "0.01"}),
            "actual_cost": forms.NumberInput(attrs={**_INPUT, "step": "0.01"}),
            "vendor_name": forms.TextInput(attrs=_INPUT),
            "vendor_bid_amount": forms.NumberInput(attrs={**_INPUT, "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            existing = ", ".join(self.instance.tags.values_list("name", flat=True))
            self.fields["tags_text"].initial = existing

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == ProjectStatus.DELAYED:
            if not cleaned.get("delay_reason", "").strip():
                self.add_error("delay_reason", "A reason is required when status is Delayed.")
        return cleaned

    def save_m2m_with_tags(self, project: Project):
        raw = self.cleaned_data.get("tags_text", "")
        names = [n.strip() for n in raw.split(",") if n.strip()]
        tags = [Tag.get_or_create_from_input(n) for n in names]
        project.tags.set(tags)
