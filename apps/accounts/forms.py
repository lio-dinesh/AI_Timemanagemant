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
    first_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com', 'autocomplete': 'email'})
    )
    username = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username (optional - auto-generated from email)'})
    )
    role = forms.ChoiceField(
        choices=UserRole.choices,
        initial=UserRole.EMPLOYEE,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    timezone = forms.CharField(
        required=False,
        initial='UTC',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'UTC'})
    )
    password = forms.CharField(
        min_length=6,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Choose password (min 6 characters)'})
    )
    confirm_password = forms.CharField(
        min_length=6,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'role', 'timezone']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists. Please sign in instead.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        email = self.cleaned_data.get('email', '').strip().lower()
        if not username and email:
            username = email.split('@')[0]
        # Clean username: replace invalid characters with underscores
        import re
        username = re.sub(r'[^\w.@+-]', '_', username)
        # Ensure username uniqueness
        base_username = username
        counter = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        return username

    def clean_timezone(self):
        tz = self.cleaned_data.get('timezone', '').strip()
        return tz or 'UTC'

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
