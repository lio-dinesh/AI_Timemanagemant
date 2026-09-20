from django import forms
from apps.tasks.models import Task, TaskStatus

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['project', 'assigned_to', 'title', 'description', 'status', 'priority', 'progress', 'estimated_seconds', 'deadline', 'category']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Task Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'progress': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'estimated_seconds': forms.NumberInput(attrs={'class': 'form-control', 'step': 300}),
            'deadline': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'category': forms.TextInput(attrs={'class': 'form-control'}),
        }
