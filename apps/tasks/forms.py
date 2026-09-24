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
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional details about the task...'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'progress': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'estimated_seconds': forms.NumberInput(attrs={'class': 'form-control', 'step': 300}),
            'deadline': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. General, Development, Meeting'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'assigned_to' in self.fields:
            self.fields['assigned_to'].required = False
            self.fields['assigned_to'].empty_label = "Assign to Me (Default)"
        if 'status' in self.fields:
            self.fields['status'].required = False
            self.fields['status'].initial = TaskStatus.TODO
        if 'priority' in self.fields:
            self.fields['priority'].required = False
            self.fields['priority'].initial = 5
        if 'progress' in self.fields:
            self.fields['progress'].required = False
            self.fields['progress'].initial = 0
        if 'estimated_seconds' in self.fields:
            self.fields['estimated_seconds'].required = False
            self.fields['estimated_seconds'].initial = 3600
        if 'category' in self.fields:
            self.fields['category'].required = False
            self.fields['category'].initial = 'General'
        if 'project' in self.fields:
            self.fields['project'].required = False
            self.fields['project'].empty_label = "No Project (Standalone)"

