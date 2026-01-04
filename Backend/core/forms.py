from django import forms
from .models import Complaint


class StaffComplaintUpdateForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ("status", "priority_level")
        widgets = {
            "status": forms.Select(attrs={"class": "form-input"}),
            "priority_level": forms.Select(attrs={"class": "form-input"}),
        }


class AdminComplaintUpdateForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ("status", "priority_level", "category", "title", "description")
        widgets = {
            "status": forms.Select(attrs={"class": "form-input"}),
            "priority_level": forms.Select(attrs={"class": "form-input"}),
            "category": forms.Select(attrs={"class": "form-input"}),
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 5}),
        }
