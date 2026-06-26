import logging
import uuid

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers

from .models import AgentProfile, ClientProfile, Influencer
from .badges import compute_agent_badge

User = get_user_model()
logger = logging.getLogger(__name__)


class AgentProfileSerializer(serializers.ModelSerializer):
    badge = serializers.SerializerMethodField()
    completed_missions = serializers.SerializerMethodField()
    pro_badge = serializers.SerializerMethodField()

    class Meta:
        model = AgentProfile
        fields = (
            'kyc_status', 'id_card_photo', 'selfie_photo', 'bio',
            'agent_code', 'is_internal',
            'badge_status', 'badge_photo', 'badge_requested_at', 'badge_approved_at',
            'badge', 'pro_badge', 'completed_missions', 'updated_at',
        )
        read_only_fields = (
            'kyc_status', 'id_card_photo', 'selfie_photo',
            'agent_code', 'is_internal',
            'badge_status', 'badge_photo', 'badge_requested_at', 'badge_approved_at',
            'badge', 'pro_badge', 'completed_missions', 'updated_at',
        )

    def get_pro_badge(self, obj):
        from apps.core.choices import AgentBadgeStatus
        return {
            'status': obj.badge_status,
            'can_request': obj.badge_status in (
                AgentBadgeStatus.NONE, AgentBadgeStatus.REJECTED,
            ),
            'can_download': obj.badge_status == AgentBadgeStatus.APPROVED,
        }

    def get_completed_missions(self, obj):
        from apps.core.choices import MissionStatus
        from apps.missions.models import Mission
        return Mission.objects.filter(
            agent=obj.user, status=MissionStatus.COMPLETED,
        ).count()

    def get_badge(self, obj):
        return compute_agent_badge(self.get_completed_missions(obj))


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
            "expertises",
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
        required=False,
        allow_blank=True,
        error_messages={
            'blank': 'Le nom d\'utilisateur ne peut pas être vide.',
        },
    )
    promo_code = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text='Déprécié — parrainage via deep link /join/CODE uniquement.',
    )
    referral_code_cache = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text='Code influenceur capturé via deep link (fonaco.app/join/CODE)',
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
        fields = ("email", "phone_number", "username", "password", "role", "first_name", "last_name", "promo_code", "referral_code_cache")
        error_messages = {
            'required': 'Ce champ est obligatoire.',
        }

    def validate_username(self, value):
        username = (value or '').strip()
        role = self.initial_data.get('role', 'client')
        if role == 'agent':
            if not username:
                raise serializers.ValidationError(
                    'Le nom d\'utilisateur est obligatoire pour les agents.'
                )
            if User.objects.filter(username__iexact=username).exists():
                raise serializers.ValidationError(
                    'Ce nom d\'utilisateur est déjà utilisé.'
                )
        return username

    def validate_promo_code(self, value):
        code = (value or '').strip()
        # Code inconnu : n'empêche pas l'inscription (aucun influenceur en base dev).
        return code

    def validate_referral_code_cache(self, value):
        code = (value or '').strip()
        return code

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                "Ce numéro de téléphone est déjà utilisé."
            )
        return value

    def validate(self, attrs):
        phone = attrs.get("phone_number")
        password = attrs.get("password")
        role = attrs.get("role", self.initial_data.get("role", "client"))
        if not all([phone, password]):
            raise serializers.ValidationError("Le numéro de téléphone et le mot de passe sont obligatoires.")
        if len(str(password)) < 8:
            raise serializers.ValidationError(
                {"password": "Le mot de passe doit contenir au moins 8 caractères."}
            )
        email = (attrs.get("email") or "").strip()
        if role == "agent" and not email:
            raise serializers.ValidationError(
                {"email": "L'adresse email est obligatoire pour les agents."}
            )
        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                {"email": "Cet e-mail est déjà associé à un compte."}
            )
        return attrs

    def _resolve_influencer(self, promo_code: str, referral_cache: str):
        code = (promo_code or referral_cache or '').strip()
        if not code:
            return None
        return Influencer.objects.filter(
            Q(code_promo__iexact=code) | Q(referral_slug__iexact=code)
        ).first()

    def create(self, validated_data):
        role = validated_data.pop("role", "client")
        promo_code = (validated_data.pop("promo_code", None) or "").strip()
        referral_cache = (validated_data.pop("referral_code_cache", None) or "").strip()
        email = (validated_data.pop("email", None) or "").strip()
        first_name = validated_data.pop("first_name", "") or ""
        last_name = validated_data.pop("last_name", "") or ""

        phone = str(validated_data["phone_number"])
        safe_phone = "".join(c for c in phone if c.isalnum())

        if not email:
            email = f"fonaqo_{safe_phone or uuid.uuid4().hex[:10]}@internal.fonaqo.local"
            while User.objects.filter(email=email).exists():
                email = f"fonaqo_{safe_phone}_{uuid.uuid4().hex[:6]}@internal.fonaqo.local"

        username = (validated_data.pop("username", None) or "").strip()
        if role == "client" and not username:
            base = f"client_{safe_phone or uuid.uuid4().hex[:8]}"
            username = base
            suffix = 1
            while User.objects.filter(username__iexact=username).exists():
                username = f"{base}_{suffix}"
                suffix += 1

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
        else:
            profile, _ = ClientProfile.objects.get_or_create(user=user)
            if referral_cache:
                profile.referral_code_cache = referral_cache
            influencer = self._resolve_influencer(promo_code, referral_cache)
            if influencer:
                from django.utils import timezone
                profile.influencer = influencer
                profile.influencer_linked_at = timezone.now()
                profile.save(update_fields=[
                    'influencer', 'influencer_linked_at',
                    'referral_code_cache', 'updated_at',
                ])
            elif referral_cache:
                profile.save(update_fields=['referral_code_cache', 'updated_at'])
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
                raise serializers.ValidationError({
                    'code': 'ACCOUNT_SUSPENDED',
                    'detail': (
                        'Votre compte a été suspendu. Contactez le support FONACO '
                        'pour faire appel.'
                    ),
                })

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
    profile_picture = serializers.ImageField(
        required=False,
        allow_null=True,
        help_text='⚠️ Attention : Cette photo sera utilisée comme photo de profil officielle partout sur l\'application ainsi que sur votre badge physique. Veuillez choisir une photo claire et professionnelle.'
    )
    bio = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "username",
            "phone_number",
            "email",
            "profile_picture",
            "city",
            "address",
            "service_domain",
            "expertises",
            "id_card_front",
            "id_card_back",
            "selfie_with_id",
            "witness_1_name",
            "witness_1_phone",
            "witness_2_name",
            "witness_2_phone",
            "bio",
        )
        read_only_fields = ("phone_number",)
        error_messages = {
            'required': 'Ce champ est obligatoire.',
        }

    def validate_email(self, value):
        email = (value or '').strip()
        if not email:
            return None
        if (
            User.objects.filter(email__iexact=email)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "Cet e-mail est déjà associé à un compte."
            )
        return email

    def validate_username(self, value):
        if value is None:
            return value
        username = (value or '').strip()
        if not username:
            raise serializers.ValidationError("Le nom d'utilisateur est obligatoire.")
        if (
            User.objects.filter(username__iexact=username)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà pris.")
        return username

    def update(self, instance, validated_data):
        if validated_data.get('email') in (None, ''):
            validated_data.pop('email', None)
        bio = self.initial_data.get('bio')
        validated_data.pop('bio', None)
        user = super().update(instance, validated_data)
        if bio is not None and user.is_agent:
            from .models import AgentProfile
            profile, _ = AgentProfile.objects.get_or_create(user=user)
            profile.bio = str(bio).strip()
            profile.save(update_fields=['bio', 'updated_at'])
        return user
