from django import forms

from ..models import ProjectCategory


class ProjectCategoryForm(forms.ModelForm):
    class Meta:
        model = ProjectCategory
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "Category name"}),
        }
