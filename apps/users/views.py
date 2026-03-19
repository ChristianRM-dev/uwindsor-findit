from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from django.core.signing import BadSignature, SignatureExpired
from django.contrib.auth import get_user_model
from django.urls import reverse

from .forms import ProfileUpdateForm, RegisterForm
from .services.registration import create_user_from_register_form, handle_post_registration
from .services.email_verification import unsign_verification_token
from .services.login_security import (
    clear_failed_login,
    format_lockout_message,
    get_lockout_remaining_seconds,
    record_failed_login,
)


@require_http_methods(["GET", "POST"])
def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    form = RegisterForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = create_user_from_register_form(form)
            raw_password = form.cleaned_data.get("password1")

            result = handle_post_registration(request, user, raw_password)

            if result["verification_required"]:
                messages.info(
                    request,
                    "We sent a verification email. Please confirm to activate your account.",
                )
                return redirect("users:verify_email_sent")

            authed = result["authed_user"]
            login(request, authed or user)
            messages.success(request, "Account created successfully.")
            return redirect("core:dashboard")

        messages.error(request, "Please correct the errors below.")

    return render(request, "users/register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        identifier = (request.POST.get("username") or "").strip().lower()
        remaining_lockout = get_lockout_remaining_seconds(request=request, identifier=identifier)
        if remaining_lockout:
            messages.error(request, format_lockout_message(remaining_lockout))
            return render(request, "users/login.html", {"form": form})

        if form.is_valid():
            user = form.get_user()
            clear_failed_login(request=request, identifier=identifier)
            login(request, user)
            messages.success(request, "Welcome back!")
            return redirect("core:dashboard")

        User = get_user_model()
        inactive_user = (
            User.objects.filter(username__iexact=identifier).first()
            or User.objects.filter(email__iexact=identifier).first()
        )
        raw_password = request.POST.get("password") or ""

        if inactive_user and not inactive_user.is_active and inactive_user.check_password(raw_password):
            messages.error(request, "Your account is not active. Please verify your email first.")
            return render(request, "users/login.html", {"form": form})

        remaining_after_failure = record_failed_login(request=request, identifier=identifier)
        if remaining_after_failure:
            messages.error(request, format_lockout_message(remaining_after_failure))
        else:
            messages.error(request, "Invalid credentials. Please try again.")

    return render(request, "users/login.html", {"form": form})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("core:home")


@require_http_methods(["GET"])
def password_recovery_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    return render(request, "users/password_recovery.html")


@require_http_methods(["GET"])
def verify_email_sent_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    return render(request, "users/verify_email_sent.html")


@require_http_methods(["GET"])
def verify_email_view(request: HttpRequest, token: str) -> HttpResponse:
    try:
        user_id = unsign_verification_token(token)
    except SignatureExpired:
        messages.error(request, "Verification link expired. Please request a new link.")
        return redirect("users:login")
    except (BadSignature, ValueError):
        messages.error(request, "Invalid verification link.")
        return redirect("users:login")

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect("users:login")

    if user.is_active:
        messages.info(request, "Email already verified. You can login.")
        return redirect("users:login")

    user.is_active = True
    user.save(update_fields=["is_active"])
    messages.success(request, "Email verified successfully. You can now login.")
    return redirect("users:login")


@login_required
@require_http_methods(["GET", "POST"])
def profile_view(request: HttpRequest) -> HttpResponse:
    form = ProfileUpdateForm(request.POST or None, instance=request.user)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("users:profile")

        messages.error(request, "Please correct the errors below.")

    context = {
        "form": form,
        "email_address": request.user.email,
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": "My Profile", "url": None, "active": True},
        ],
    }
    return render(request, "users/profile.html", context)
