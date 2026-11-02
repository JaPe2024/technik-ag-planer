from django import forms

from apps.scheduling.forms import SegmentedRadio

from .models import NotificationSettings


class SettingsForm(forms.ModelForm):
    class Meta:
        model = NotificationSettings
        fields = [
            "crew",
            "changes",
            "reminders",
            "inquiries",
            "board",
            "chats",
            "reminder_mode",
            "reminder_time",
            "reminder_hours",
        ]
        widgets = {
            "reminder_mode": SegmentedRadio,
            "reminder_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "reminder_hours": forms.NumberInput(attrs={"min": 1, "max": 48}),
        }

    def __init__(self, *args, show_inquiries=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not show_inquiries:  # nur für Owner, Admins und Lehrkräfte
            del self.fields["inquiries"]

    def clean_reminder_hours(self):
        hours = self.cleaned_data["reminder_hours"]
        if not 1 <= hours <= 48:
            raise forms.ValidationError("Bitte 1 bis 48 Stunden.")
        return hours
