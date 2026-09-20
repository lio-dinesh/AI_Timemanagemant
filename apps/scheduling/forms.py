from django import forms
from apps.scheduling.models import ScheduleEvent, ScheduleEventType

class ScheduleEventForm(forms.ModelForm):
    class Meta:
        model = ScheduleEvent
        fields = ['title', 'description', 'event_type', 'task', 'start_at', 'end_at', 'reminder_minutes', 'location', 'meeting_url']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event / Meeting Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'event_type': forms.Select(attrs={'class': 'form-select'}),
            'task': forms.Select(attrs={'class': 'form-select'}),
            'start_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'reminder_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'meeting_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://meet.google.com/...'}),
        }
