from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import RegisterForm


@require_http_methods(["GET", "POST"])
def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    form = RegisterForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.save()

            # Auto-login after successful registration
            # We authenticate using username=email because we set username=email in the form.
            raw_password = form.cleaned_data.get("password1")
            authed = authenticate(request, username=user.username, password=raw_password)
            if authed is not None:
                login(request, authed)
                messages.success(request, "Account created successfully.")
                return redirect("core:dashboard")

            # Fallback: if authentication fails for some reason
            login(request, user)
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
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, "Welcome back!")
            return redirect("core:dashboard")

        messages.error(request, "Invalid credentials. Please try again.")

    return render(request, "users/login.html", {"form": form})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("core:home")
