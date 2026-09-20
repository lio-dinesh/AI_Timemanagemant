from django import forms
from apps.projects.models import Project, ProjectStatus

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'status', 'priority', 'start_date', 'deadline']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Project Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Project Description'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'deadline': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }
