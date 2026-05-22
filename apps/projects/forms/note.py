from django import forms

from ..models import UpdateNote


class UpdateNoteForm(forms.ModelForm):
    class Meta:
        model = UpdateNote
        fields = ["body"]

    def clean_body(self):
        body = self.cleaned_data.get("body", "")
        if not body.strip():
            raise forms.ValidationError("Note body cannot be empty.")
        return body
