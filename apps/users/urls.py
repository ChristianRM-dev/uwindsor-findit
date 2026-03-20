from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from . import views

app_name = "users"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),

    path("password-recovery/", views.password_recovery_view, name="password_recovery"),

    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="users/password_recovery.html",
            email_template_name="users/emails/password_reset_email.txt",
            subject_template_name="users/emails/password_reset_subject.txt",
            success_url=reverse_lazy("users:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="users/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="users/password_reset_confirm.html",
            success_url=reverse_lazy("users:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="users/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),

    path("verify-email/<str:token>/", views.verify_email_view, name="verify_email"),
    path(
        "resend-verification-email/",
        views.resend_verification_email_view,
        name="resend_verification_email",
    ),
    path("verify-email-sent/", views.verify_email_sent_view, name="verify_email_sent"),
]
