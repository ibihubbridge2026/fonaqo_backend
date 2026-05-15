import logging
import uuid

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()
logger = logging.getLogger(__name__)


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "phone_number",
            "username",
            "first_name",
            "last_name",
            "is_agent",
            "is_client",
            "is_verified",
            "role",
            "wallet_balance",
            "avatar_url",
            "date_joined",
        )

    def get_role(self, obj):
        return "agent" if obj.is_agent else "client"

    def get_wallet_balance(self, obj):
        if hasattr(obj, 'wallet'):
            return float(obj.wallet.balance)
        return 0.0

    def get_avatar_url(self, obj):
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None


class RegisterSerializer(serializers.ModelSerializer):
    """Inscription unique : rôle client/agent + email optionnel."""

    role = serializers.ChoiceField(
        choices=["client", "agent"],
        write_only=True,
        default="client",
        required=False,
    )
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("email", "phone_number", "username", "password", "role")

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                "Ce numéro de téléphone est déjà utilisé."
            )
        return value

    def validate_username(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Le nom d'utilisateur est requis.")
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà utilisé.")
        return value

    def validate(self, attrs):
        phone = attrs.get("phone_number")
        username = attrs.get("username")
        password = attrs.get("password")
        if not all([phone, username, password]):
            raise serializers.ValidationError("Tous les champs obligatoires doivent être remplis.")
        if len(str(password)) < 8:
            raise serializers.ValidationError(
                {"password": "Le mot de passe doit contenir au moins 8 caractères."}
            )
        email = (attrs.get("email") or "").strip()
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                {"email": "Cet email est déjà utilisé."}
            )
        return attrs

    def create(self, validated_data):
        role = validated_data.pop("role", "client")
        email = (validated_data.pop("email", None) or "").strip()

        if not email:
            safe_phone = "".join(
                c for c in str(validated_data["phone_number"]) if c.isalnum()
            )
            email = f"fonaco_{safe_phone or uuid.uuid4().hex[:10]}@internal.fonaco.local"
            while User.objects.filter(email=email).exists():
                email = f"fonaco_{safe_phone}_{uuid.uuid4().hex[:6]}@internal.fonaco.local"

        validated_data["email"] = email

        # USERNAME_FIELD = phone_number : utiliser uniquement des arguments nommés pour éviter les conflits
        user = User.objects.create_user(
            phone_number=validated_data["phone_number"],  # USERNAME_FIELD
            email=validated_data["email"],
            password=validated_data["password"],
            username=validated_data["username"],  # REQUIRED_FIELDS
        )
        if role == "agent":
            user.is_agent = True
            user.is_client = False
        else:
            user.is_client = True
            user.is_agent = False
        user.save()
        logger.info("Inscription réussie user=%s role=%s", user.id, role)
        return user


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        phone_number = data.get("phone_number")
        password = data.get("password")

        if phone_number and password:
            from django.contrib.auth import authenticate

            user = authenticate(
                request=self.context.get("request"),
                username=phone_number,
                password=password,
            )

            if not user:
                raise serializers.ValidationError(
                    "Numéro de téléphone ou mot de passe incorrect."
                )

            if not user.is_active:
                raise serializers.ValidationError("Ce compte est désactivé.")

            data["user"] = user
            return data
        raise serializers.ValidationError(
            "Le numéro de téléphone et le mot de passe sont requis."
        )


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "profile_picture",
            "id_card_front",
            "id_card_back",
            "selfie_with_id",
            "witness_1_name",
            "witness_1_phone",
            "witness_2_name",
            "witness_2_phone",
        )
        read_only_fields = ("phone_number",)

    def validate_phone_number(self, value):
        if not value:
            raise serializers.ValidationError(
                "Le numéro de téléphone est obligatoire pour l'activation."
            )
        return value
