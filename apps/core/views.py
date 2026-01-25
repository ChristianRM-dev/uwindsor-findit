from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def home_view(request: HttpRequest) -> HttpResponse:
    return render(request, "core/home.html")


@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    return render(request, "core/dashboard.html")
