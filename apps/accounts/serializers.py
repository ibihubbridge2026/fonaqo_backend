import logging
import uuid

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import AgentProfile

User = get_user_model()
logger = logging.getLogger(__name__)


class AgentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentProfile
        fields = ('kyc_status', 'id_card_photo', 'selfie_photo', 'updated_at')
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    agent_profile = serializers.SerializerMethodField()
    kyc_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "phone_number",
            "username",
            "first_name",
            "last_name",
            "city",
            "address",
            "service_domain",
            "is_agent",
            "is_client",
            "is_verified",
            "role",
            "wallet_balance",
            "avatar_url",
            "agent_profile",
            "kyc_status",
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

    def get_agent_profile(self, obj):
        if not obj.is_agent:
            return None
        profile, _ = AgentProfile.objects.get_or_create(user=obj)
        return AgentProfileSerializer(profile, context=self.context).data

    def get_kyc_status(self, obj):
        if not obj.is_agent:
            return None
        profile, _ = AgentProfile.objects.get_or_create(user=obj)
        return profile.kyc_status


class RegisterSerializer(serializers.ModelSerializer):
    """Inscription unique : rôle client/agent + email optionnel. Username auto-généré."""

    role = serializers.ChoiceField(
        choices=["client", "agent"],
        write_only=True,
        default="client",
        required=False,
        error_messages={
            'invalid_choice': 'Le rôle doit être "client" ou "agent".'
        }
    )
    email = serializers.EmailField(
        write_only=True,
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'Adresse email invalide.',
            'required': 'Ce champ est obligatoire.'
        }
    )
    username = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'Le nom d\'utilisateur est obligatoire.',
            'blank': 'Le nom d\'utilisateur ne peut pas être vide.',
        },
    )
    first_name = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        error_messages={
            'required': 'Ce champ est obligatoire.',
            'blank': 'Ce champ ne peut pas être vide.'
        }
    )
    last_name = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        error_messages={
            'required': 'Ce champ est obligatoire.',
            'blank': 'Ce champ ne peut pas être vide.'
        }
    )
    phone_number = serializers.CharField(
        error_messages={
            'required': 'Le numéro de téléphone est obligatoire.',
            'blank': 'Le numéro de téléphone ne peut pas être vide.'
        }
    )
    password = serializers.CharField(
        write_only=True,
        error_messages={
            'required': 'Le mot de passe est obligatoire.',
            'blank': 'Le mot de passe ne peut pas être vide.'
        }
    )

    class Meta:
        model = User
        fields = ("email", "phone_number", "username", "password", "role", "first_name", "last_name")
        error_messages = {
            'required': 'Ce champ est obligatoire.',
        }

    def validate_username(self, value):
        username = (value or '').strip()
        if not username:
            raise serializers.ValidationError(
                'Le nom d\'utilisateur est obligatoire.'
            )
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError(
                'Ce nom d\'utilisateur est déjà utilisé.'
            )
        return username

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                "Ce numéro de téléphone est déjà utilisé."
            )
        return value

    def validate(self, attrs):
        phone = attrs.get("phone_number")
        password = attrs.get("password")
        if not all([phone, password]):
            raise serializers.ValidationError("Le numéro de téléphone et le mot de passe sont obligatoires.")
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
        first_name = validated_data.pop("first_name", "") or ""
        last_name = validated_data.pop("last_name", "") or ""

        phone = str(validated_data["phone_number"])
        safe_phone = "".join(c for c in phone if c.isalnum())

        # Auto-génération de l'email si absent
        if not email:
            email = f"fonaqo_{safe_phone or uuid.uuid4().hex[:10]}@internal.fonaqo.local"
            while User.objects.filter(email=email).exists():
                email = f"fonaqo_{safe_phone}_{uuid.uuid4().hex[:6]}@internal.fonaqo.local"

        username = (validated_data.pop("username", None) or "").strip()

        user = User.objects.create_user(
            phone_number=validated_data["phone_number"],
            email=email,
            password=validated_data["password"],
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        if role == "agent":
            user.is_agent = True
            user.is_client = False
        else:
            user.is_client = True
            user.is_agent = False
        user.save()
        if role == "agent":
            AgentProfile.objects.get_or_create(user=user)
        logger.info("Inscription réussie user=%s role=%s", user.id, role)
        return user


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=20,
        error_messages={
            'required': 'Le numéro de téléphone est obligatoire.',
            'blank': 'Le numéro de téléphone ne peut pas être vide.',
            'max_length': 'Le numéro de téléphone est trop long.'
        }
    )
    password = serializers.CharField(
        write_only=True,
        error_messages={
            'required': 'Le mot de passe est obligatoire.',
            'blank': 'Le mot de passe ne peut pas être vide.'
        }
    )

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
    first_name = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'required': 'Le prénom est obligatoire.',
            'blank': 'Le prénom ne peut pas être vide.'
        }
    )
    last_name = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'required': 'Le nom est obligatoire.',
            'blank': 'Le nom ne peut pas être vide.'
        }
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': 'Adresse email invalide.',
            'required': 'L\'email est obligatoire.'
        }
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "profile_picture",
            "city",
            "address",
            "service_domain",
            "id_card_front",
            "id_card_back",
            "selfie_with_id",
            "witness_1_name",
            "witness_1_phone",
            "witness_2_name",
            "witness_2_phone",
        )
        read_only_fields = ("phone_number",)
        error_messages = {
            'required': 'Ce champ est obligatoire.',
        }

    def validate_phone_number(self, value):
        if not value:
            raise serializers.ValidationError(
                "Le numéro de téléphone est obligatoire pour l'activation."
            )
        return value
