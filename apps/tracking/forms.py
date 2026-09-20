from django import forms
from apps.tracking.models import ProductivityCategory

class ManualTimeEntryForm(forms.Form):
    task_id = forms.IntegerField(required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    activity_type = forms.CharField(initial="General Work", widget=forms.TextInput(attrs={'class': 'form-control'}))
    start_time = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}))
    end_time = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}))
    productivity_category = forms.ChoiceField(
        choices=ProductivityCategory.choices,
        initial=ProductivityCategory.PRODUCTIVE,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    idle_seconds = forms.IntegerField(initial=0, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))
