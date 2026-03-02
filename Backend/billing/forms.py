from django import forms
from .models import BusinessLicenseDemandNotice, DemandNoticeStatus


class StaffBusinessNoticeVerifyForm(forms.ModelForm):
    class Meta:
        model = BusinessLicenseDemandNotice
        fields = ("status", "amount_due", "due_date", "reject_reason")
        widgets = {
            "status": forms.Select(attrs={"class": "form-input"}),
            "amount_due": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "reject_reason": forms.Textarea(attrs={"class": "form-input", "rows": 4}),
        }

    def clean(self):
        data = super().clean()
        if data.get("status") == DemandNoticeStatus.REJECTED and not data.get("reject_reason"):
            raise forms.ValidationError("Reject reason is required when rejecting.")
        return data