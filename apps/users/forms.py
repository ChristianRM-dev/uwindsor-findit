from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@uwindsor.ca"}),
        help_text="Only @uwindsor.ca emails are allowed.",
    )
    first_name = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"}),
    )
    last_name = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"}),
    )
    student_id = forms.CharField(
        required=True,
        max_length=9,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "9-digit student ID"}),
    )
    phone_number = forms.CharField(
        required=True,
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Phone number"}),
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
        fields = ("email", "first_name", "last_name", "student_id", "phone_number")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()

        if not email.endswith("@uwindsor.ca"):
            raise forms.ValidationError("Please use your @uwindsor.ca email address.")

        User = get_user_model()
        # Since we will set username=email, prevent duplicates
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")

        return email

    def clean_first_name(self):
        first_name = (self.cleaned_data.get("first_name") or "").strip()
        if not first_name:
            raise forms.ValidationError("First name is required.")
        return first_name

    def clean_last_name(self):
        last_name = (self.cleaned_data.get("last_name") or "").strip()
        if not last_name:
            raise forms.ValidationError("Last name is required.")
        return last_name

    def clean_student_id(self):
        student_id = (self.cleaned_data.get("student_id") or "").strip()
        if not student_id.isdigit() or len(student_id) != 9:
            raise forms.ValidationError("Student ID must be exactly 9 digits.")

        User = get_user_model()
        if User.objects.filter(student_id=student_id).exists():
            raise forms.ValidationError("This student ID is already in use.")

        return student_id

    def clean_phone_number(self):
        phone_number = (self.cleaned_data.get("phone_number") or "").strip()
        allowed_chars = set("0123456789-+() ")
        if not phone_number:
            raise forms.ValidationError("Phone number is required.")
        if any(char not in allowed_chars for char in phone_number):
            raise forms.ValidationError("Phone number can only contain digits, spaces, and - + ( ).")
        return phone_number

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]

        # Minimal approach: store email in both fields so default auth works.
        user.email = email
        user.username = email  # enables login with email as username
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.student_id = self.cleaned_data["student_id"]
        user.phone_number = self.cleaned_data["phone_number"]

        if commit:
            user.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"}),
    )
    last_name = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"}),
    )
    student_id = forms.CharField(
        required=False,
        max_length=9,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "9-digit student ID"}),
    )
    phone_number = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Phone number"}),
    )

    class Meta:
        model = get_user_model()
        fields = ("first_name", "last_name", "student_id", "phone_number")

    def clean_student_id(self):
        student_id = (self.cleaned_data.get("student_id") or "").strip()
        if not student_id:
            return ""

        if not student_id.isdigit() or len(student_id) != 9:
            raise forms.ValidationError("Student ID must be exactly 9 digits.")

        User = get_user_model()
        if User.objects.exclude(pk=self.instance.pk).filter(student_id=student_id).exists():
            raise forms.ValidationError("This student ID is already in use.")

        return student_id

    def clean_phone_number(self):
        phone_number = (self.cleaned_data.get("phone_number") or "").strip()
        if not phone_number:
            return ""

        allowed_chars = set("0123456789-+() ")
        if any(char not in allowed_chars for char in phone_number):
            raise forms.ValidationError("Phone number can only contain digits, spaces, and - + ( ).")

        return phone_number
