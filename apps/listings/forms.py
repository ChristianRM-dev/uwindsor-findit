from __future__ import annotations

from django import forms
from django.utils import timezone

from apps.listings.models import CampusLocation, Category, Item, ItemImage


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


def _status_choices_for_item_type(item_type: str):
    if item_type == Item.ItemType.FOUND:
        return [
            (Item.Status.FOUND, "Found"),
            (Item.Status.CLAIMED, "Claimed"),
            (Item.Status.RETURNED, "Returned"),
        ]

    return [
        (Item.Status.LOST, "Lost"),
        (Item.Status.CLAIMED, "Claimed"),
        (Item.Status.RETURNED, "Returned"),
    ]


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
    item_type = Item.ItemType.LOST

    def __init__(self, *args, **kwargs):
        self.item_type = kwargs.pop("item_type", self.item_type)
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["location"].queryset = CampusLocation.objects.filter(is_active=True)
        self.fields["event_date"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["event_date"].help_text = "Approximate date is fine."
        self.fields["event_date"].widget.attrs["max"] = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        self.fields["title"].label = (
            "What did you find?" if self.item_type == Item.ItemType.FOUND else "What did you lose?"
        )
        self.fields["category"].label = "Category"
        self.fields["event_date"].label = (
            "When did you find it?" if self.item_type == Item.ItemType.FOUND else "When did you lose it?"
        )
        self.fields["location"].label = (
            "Where did you find it?" if self.item_type == Item.ItemType.FOUND else "Where did you lose it?"
        )
        self.fields["description"].label = "Detailed Description"
        self.fields["photos"].label = "Upload Photos (Optional)"

    def clean_event_date(self):
        event_date = self.cleaned_data.get("event_date")
        if event_date and event_date > timezone.now():
            action = "found" if self.item_type == Item.ItemType.FOUND else "lost"
            raise forms.ValidationError(f"Date {action} cannot be in the future.")
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


class ReportFoundItemForm(ReportLostItemForm):
    item_type = Item.ItemType.FOUND


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
                "placeholder": "Enter your UWindsor email",
            }
        ),
    )
    student_id = forms.CharField(
        required=True,
        max_length=50,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your student ID",
            }
        ),
    )
    relationship_to_item = forms.ChoiceField(
        required=True,
        choices=RELATIONSHIP_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    lost_date = forms.DateTimeField(
        required=True,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                "class": "form-control",
                "type": "datetime-local",
            }
        ),
    )
    detailed_description = forms.CharField(
        required=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Describe the item's unique identifiers, contents, stickers, marks, or anything only the real owner would know.",
            }
        ),
    )
    where_lost_location = forms.ModelChoiceField(
        required=True,
        queryset=CampusLocation.objects.none(),
        empty_label="Select location",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    lost_location_details = forms.CharField(
        required=True,
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Second-floor study lounge beside the printers",
            }
        ),
    )
    student_card_image = forms.ImageField(
        required=True,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": ".jpg,.jpeg,.png,image/jpeg,image/png",
            }
        ),
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
        self.fields["lost_date"].label = "When did you lose it?"
        self.fields["lost_date"].help_text = "Approximate date and time is okay."
        self.fields["lost_date"].widget.attrs["max"] = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        self.fields["lost_location_details"].label = "Exact place where you lost it"
        self.fields["student_card_image"].label = "Student card image"
        self.fields["proof_files"].label = "Ownership proof files"
        if user and getattr(user, "is_authenticated", False):
            self.fields["full_name"].initial = (
                f"{user.first_name} {user.last_name}".strip() or user.get_username()
            )
            self.fields["email"].initial = user.email

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email.endswith("@uwindsor.ca"):
            raise forms.ValidationError("Please use a valid UWindsor email address.")
        return email

    def clean_student_id(self):
        student_id = (self.cleaned_data.get("student_id") or "").strip()
        if not student_id.isdigit() or len(student_id) != 9:
            raise forms.ValidationError("Student ID must be a 9-digit number.")
        return student_id

    def clean_detailed_description(self):
        description = (self.cleaned_data.get("detailed_description") or "").strip()
        if len(description) < 20:
            raise forms.ValidationError("Please provide more detail so the finder can verify ownership.")
        return description

    def clean_lost_location_details(self):
        return (self.cleaned_data.get("lost_location_details") or "").strip()

    def clean_lost_date(self):
        lost_date = self.cleaned_data.get("lost_date")
        if lost_date and lost_date > timezone.now():
            raise forms.ValidationError("Lost date cannot be in the future.")
        return lost_date

    def clean_student_card_image(self):
        file_obj = self.cleaned_data.get("student_card_image")
        if not file_obj:
            raise forms.ValidationError("Please upload your student card image.")

        file_ext = ""
        if file_obj.name and "." in file_obj.name:
            file_ext = f".{file_obj.name.rsplit('.', 1)[-1].lower()}"

        if file_ext not in {".jpg", ".jpeg", ".png"}:
            raise forms.ValidationError("Student card image must be a JPG or PNG file.")
        if file_obj.content_type not in {"image/jpeg", "image/png"}:
            raise forms.ValidationError("Student card image must be a JPG or PNG file.")
        if file_obj.size > self.max_file_size:
            raise forms.ValidationError("Student card image must be 10MB or smaller.")

        return file_obj

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


class ClaimReviewForm(forms.Form):
    DECISION_APPROVE = "approve"
    DECISION_REJECT = "reject"
    DECISION_CHOICES = (
        (DECISION_APPROVE, "Approve"),
        (DECISION_REJECT, "Reject"),
    )

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.HiddenInput(),
    )
    reviewer_notes = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Add any notes for the claimant. Required when rejecting.",
            }
        ),
    )

    def clean_reviewer_notes(self):
        return (self.cleaned_data.get("reviewer_notes") or "").strip()

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("decision") == self.DECISION_REJECT
            and not cleaned.get("reviewer_notes")
        ):
            self.add_error("reviewer_notes", "Please provide a reason when rejecting a claim.")

        return cleaned


class ItemEditForm(forms.ModelForm):
    status = forms.ChoiceField(
        required=True,
        choices=[],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    photos = MultiFileField(
        required=False,
        widget=MultiFileInput(
            attrs={
                "class": "form-control",
                "accept": ".jpg,.jpeg,.png,image/jpeg,image/png",
            }
        ),
    )
    remove_images = forms.ModelMultipleChoiceField(
        required=False,
        queryset=ItemImage.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Item
        fields = ["title", "category", "status", "event_date", "location", "description"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Black Patagonia backpack",
                    "maxlength": "200",
                }
            ),
            "category": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "event_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
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
        self.fields["status"].choices = _status_choices_for_item_type(self.instance.item_type)
        self.fields["title"].label = "Item title"
        self.fields["category"].label = "Category"
        self.fields["status"].label = "Status"
        self.fields["event_date"].label = (
            "When was it found?" if self.instance.item_type == Item.ItemType.FOUND else "When was it lost?"
        )
        self.fields["location"].label = "Location"
        self.fields["description"].label = "Detailed Description"
        self.fields["photos"].label = "Add More Photos (Optional)"
        self.fields["remove_images"].label = "Remove Current Photos"
        self.fields["remove_images"].queryset = (
            self.instance.images.all() if self.instance and self.instance.pk else ItemImage.objects.none()
        )

        if self.instance and self.instance.event_date:
            local_dt = timezone.localtime(self.instance.event_date)
            self.initial["event_date"] = local_dt.strftime("%Y-%m-%dT%H:%M")

    def clean_event_date(self):
        event_date = self.cleaned_data.get("event_date")
        if event_date and event_date > timezone.now():
            action = "found" if self.instance.item_type == Item.ItemType.FOUND else "lost"
            raise forms.ValidationError(f"Date {action} cannot be in the future.")
        return event_date

    def clean_description(self):
        description = (self.cleaned_data.get("description") or "").strip()
        if not description:
            raise forms.ValidationError("Description is required.")
        if len(description) > 500:
            raise forms.ValidationError("Description must be at most 500 characters.")
        return description

    def clean_status(self):
        status = self.cleaned_data.get("status")
        allowed_statuses = {choice[0] for choice in _status_choices_for_item_type(self.instance.item_type)}
        if status not in allowed_statuses:
            raise forms.ValidationError("Select a valid status for this item.")
        return status

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

        remove_images = cleaned.get("remove_images")
        remove_count = remove_images.count() if remove_images is not None else 0
        current_image_count = self.instance.images.count() if self.instance.pk else 0
        total_after_save = current_image_count - remove_count + len(files)

        if total_after_save > self.max_files:
            self.add_error(
                "photos",
                f"You can keep up to {self.max_files} photos total. Remove some current photos before adding more.",
            )

        return cleaned
