from django import forms
from apps.accounts.models import User, UserRole

class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com', 'autocomplete': 'email'})
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••', 'autocomplete': 'current-password'})
    )


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Choose password'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Repeat password'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'role', 'timezone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'username'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'timezone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'UTC'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'timezone', 'work_start_time', 'work_end_time']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'timezone': forms.TextInput(attrs={'class': 'form-control'}),
            'work_start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'work_end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }
