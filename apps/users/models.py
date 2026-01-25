from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model.
    Extend this later with profile fields (e.g. phone, avatar, etc.).
    """
    pass
