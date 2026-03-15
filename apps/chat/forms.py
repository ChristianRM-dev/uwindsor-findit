from django import forms


class ContactOwnerForm(forms.Form):
    message = forms.CharField(
        min_length=10,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "class": "form-control",
                "placeholder": (
                    "Hi, I think this might be my item. I can share a few details to verify ownership."
                ),
            }
        ),
    )


class MessageReplyForm(forms.Form):
    message = forms.CharField(
        min_length=1,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "form-control",
                "placeholder": "Write your reply...",
            }
        ),
    )
