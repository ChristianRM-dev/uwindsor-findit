from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@uwindsor.ca"}),
        help_text="Only @uwindsor.ca emails are allowed.",
    )

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("email",)

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()

        if not email.endswith("@uwindsor.ca"):
            raise forms.ValidationError("Please use your @uwindsor.ca email address.")

        User = get_user_model()
        # Since we will set username=email, prevent duplicates
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]

        # Minimal approach: store email in both fields so default auth works.
        user.email = email
        user.username = email  # enables login with email as username
        user.is_active = True

        if commit:
            user.save()
        return user
