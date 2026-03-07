from __future__ import annotations

from django import forms
from django.utils import timezone

from apps.listings.models import CampusLocation, Category, Item


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    def clean(self, data, initial=None):
        if not data:
            return []

        if not isinstance(data, (list, tuple)):
            data = [data]

        cleaned_files = []
        errors = []

        for uploaded_file in data:
            try:
                cleaned_files.append(super().clean(uploaded_file, initial))
            except forms.ValidationError as exc:
                errors.extend(exc.error_list)

        if errors:
            raise forms.ValidationError(errors)

        return cleaned_files


class ReportLostItemForm(forms.ModelForm):
    photos = MultiFileField(
        required=False,
        widget=MultiFileInput(attrs={"class": "form-control", "accept": ".jpg,.jpeg,.png,image/jpeg,image/png"}),
    )

    class Meta:
        model = Item
        fields = ["title", "category", "event_date", "location", "description"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Black Patagonia backpack",
                    "maxlength": "200",
                }
            ),
            "category": forms.Select(attrs={"class": "form-select"}),
            "event_date": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "location": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Describe your item in detail.",
                    "maxlength": "500",
                }
            ),
        }

    max_files = 5
    max_file_size = 5 * 1024 * 1024
    allowed_content_types = {"image/jpeg", "image/png"}
    allowed_extensions = {".jpg", ".jpeg", ".png"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["location"].queryset = CampusLocation.objects.filter(is_active=True)
        self.fields["event_date"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["event_date"].help_text = "Approximate date is fine."
        self.fields["event_date"].widget.attrs["max"] = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        self.fields["title"].label = "What did you lose?"
        self.fields["category"].label = "Category"
        self.fields["event_date"].label = "When did you lose it?"
        self.fields["location"].label = "Where did you lose it?"
        self.fields["description"].label = "Detailed Description"
        self.fields["photos"].label = "Upload Photos (Optional)"

    def clean_event_date(self):
        event_date = self.cleaned_data.get("event_date")
        if event_date and event_date > timezone.now():
            raise forms.ValidationError("Date lost cannot be in the future.")
        return event_date

    def clean_description(self):
        description = (self.cleaned_data.get("description") or "").strip()
        if not description:
            raise forms.ValidationError("Description is required.")
        if len(description) > 500:
            raise forms.ValidationError("Description must be at most 500 characters.")
        return description

    def clean(self):
        cleaned = super().clean()
        files = cleaned.get("photos") or []
        if not isinstance(files, (list, tuple)):
            files = [files]

        if len(files) > self.max_files:
            self.add_error("photos", f"You can upload up to {self.max_files} photos.")
            return cleaned

        for image in files:
            file_ext = ""
            if image.name and "." in image.name:
                file_ext = f".{image.name.rsplit('.', 1)[-1].lower()}"

            if file_ext not in self.allowed_extensions:
                self.add_error("photos", f"{image.name}: only JPG/PNG files are allowed.")
                continue

            if image.content_type not in self.allowed_content_types:
                self.add_error("photos", f"{image.name}: unsupported image type.")
                continue

            if image.size > self.max_file_size:
                self.add_error("photos", f"{image.name}: file size must be <= 5MB.")

        return cleaned


class ClaimCreateForm(forms.Form):
    RELATIONSHIP_CHOICES = (
        ("Owner", "Owner"),
        ("Friend / Family", "Friend / Family"),
        ("Other", "Other"),
    )

    max_files = 3
    max_file_size = 10 * 1024 * 1024
    allowed_content_types = {"image/jpeg", "image/png", "application/pdf"}
    allowed_extensions = {".jpg", ".jpeg", ".png", ".pdf"}

    full_name = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your full name",
            }
        ),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your email",
            }
        ),
    )
    relationship_to_item = forms.ChoiceField(
        required=True,
        choices=RELATIONSHIP_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    detailed_description = forms.CharField(
        required=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Describe unique identifiers (marks, contents, serial number, case color, etc.).",
            }
        ),
    )
    where_lost_location = forms.ModelChoiceField(
        required=True,
        queryset=CampusLocation.objects.none(),
        empty_label="Select location",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    proof_files = MultiFileField(
        required=False,
        widget=MultiFileInput(
            attrs={
                "class": "form-control",
                "accept": ".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf",
            }
        ),
    )
    consent = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["where_lost_location"].queryset = CampusLocation.objects.filter(is_active=True)
        self.fields["where_lost_location"].label = "Where did you lose it?"
        if user and getattr(user, "is_authenticated", False):
            self.fields["full_name"].initial = (
                f"{user.first_name} {user.last_name}".strip() or user.get_username()
            )
            self.fields["email"].initial = user.email

    def clean_proof_files(self):
        files = self.cleaned_data.get("proof_files") or []
        if not isinstance(files, (list, tuple)):
            files = [files]

        if len(files) == 0:
            raise forms.ValidationError("Please upload at least one proof document or photo.")

        if len(files) > self.max_files:
            raise forms.ValidationError("Upload 1-3 files.")

        for file_obj in files:
            file_ext = ""
            if file_obj.name and "." in file_obj.name:
                file_ext = f".{file_obj.name.rsplit('.', 1)[-1].lower()}"

            if file_ext not in self.allowed_extensions:
                raise forms.ValidationError("File too large / unsupported format.")

            if file_obj.content_type not in self.allowed_content_types:
                raise forms.ValidationError("File too large / unsupported format.")

            if file_obj.size > self.max_file_size:
                raise forms.ValidationError("File too large / unsupported format.")

        return list(files)
