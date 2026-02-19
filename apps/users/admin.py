from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("email", "username", "student_id", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "username", "student_id")

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("FindIt profile", {"fields": ("student_id", "phone_number", "role")}),
    )
