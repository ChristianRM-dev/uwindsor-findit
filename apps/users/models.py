from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    student_id = models.CharField(max_length=9, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)

    class Role(models.TextChoices):
        USER = "USER", "User"
        ADMIN = "ADMIN", "Admin"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.USER)

    def __str__(self) -> str:
        return self.email
