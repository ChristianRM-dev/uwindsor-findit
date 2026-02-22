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
