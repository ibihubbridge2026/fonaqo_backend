"""Authentification par téléphone, email ou username."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


class PhoneEmailBackend(ModelBackend):
    """Permet la connexion avec numéro, email ou username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = (
            username
            or kwargs.get(User.USERNAME_FIELD)
            or kwargs.get('phone_number')
            or kwargs.get('email')
        )
        if not identifier or not password:
            return None

        user = User.objects.filter(
            Q(phone_number=identifier)
            | Q(email__iexact=identifier)
            | Q(username__iexact=identifier),
        ).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
