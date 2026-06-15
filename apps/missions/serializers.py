from rest_framework import serializers
from django.contrib.gis.geos import Point
from .models import Mission, MissionProof, MissionTimelineEvent, AgentStatistics
from django.contrib.auth import get_user_model

User = get_user_model()


class MissionProofSerializer(serializers.ModelSerializer):
    """Serializer pour les preuves de mission"""
    uploaded_by = serializers.StringRelatedField(read_only=True)
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = MissionProof
        fields = [
            'id', 'mission', 'uploaded_by', 'image', 'image_url',
            'caption', 'is_primary', 'created_at',
            'location_lat', 'location_lng'
        ]
        read_only_fields = ['uploaded_by', 'created_at']
    
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class MissionProofCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer des preuves de mission"""
    
    class Meta:
        model = MissionProof
        fields = [
            'mission', 'image', 'caption', 'is_primary',
            'location_lat', 'location_lng'
        ]
    
    def validate_mission(self, value):
        user = self.context['request'].user
        if not user.is_agent:
            raise serializers.ValidationError("Seuls les agents peuvent ajouter des preuves")
        if value.agent != user:
            raise serializers.ValidationError("Vous ne pouvez ajouter des preuves qu'à vos missions assignées")
        return value
    
    def validate(self, data):
        if data.get('is_primary'):
            # Vérifier qu'il n'y a pas déjà une photo primaire
            mission = data.get('mission')
            existing_primary = MissionProof.objects.filter(
                mission=mission, is_primary=True
            ).exists()
            
            if existing_primary:
                raise serializers.ValidationError(
                    "Il y a déjà une photo primaire pour cette mission"
                )
        return data


class MissionTimelineEventSerializer(serializers.ModelSerializer):
    """Serializer pour les événements de timeline"""
    performed_by = serializers.StringRelatedField(read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    
    class Meta:
        model = MissionTimelineEvent
        fields = [
            'id', 'mission', 'event_type', 'event_type_display',
            'occurred_at', 'performed_by', 'notes',
            'location_lat', 'location_lng', 'metadata'
        ]
        read_only_fields = ['occurred_at', 'performed_by']


class MissionTimelineEventCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer des événements de timeline"""
    
    class Meta:
        model = MissionTimelineEvent
        fields = [
            'mission', 'event_type', 'notes',
            'location_lat', 'location_lng', 'metadata'
        ]
    
    def validate_mission(self, value):
        user = self.context['request'].user
        if value.client == user or value.agent == user:
            return value
        raise serializers.ValidationError("Vous ne pouvez ajouter des événements qu'à vos missions")


class AgentStatisticsSerializer(serializers.ModelSerializer):
    """Serializer pour les statistiques d'agent"""
    agent_name = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()

    class Meta:
        model = AgentStatistics
        fields = [
            'id', 'agent', 'agent_name',
            'total_missions', 'completed_missions', 'cancelled_missions',
            'total_earnings', 'average_rating', 'current_streak',
            'success_rate', 'updated_at',
        ]
        read_only_fields = ['agent', 'updated_at']

    def get_agent_name(self, obj):
        if obj.agent:
            return f"{obj.agent.first_name} {obj.agent.last_name}".strip() or obj.agent.username
        return "Agent Inconnu"

    def get_success_rate(self, obj):
        if obj.total_missions > 0:
            return round(obj.completed_missions / obj.total_missions * 100, 2)
        return 0.0


class AgentDashboardStatsSerializer(serializers.Serializer):
    """Serializer pour les stats du dashboard agent"""
    # Stats aujourd'hui
    today_missions = serializers.IntegerField()
    today_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # Stats cette semaine
    week_missions = serializers.IntegerField()
    week_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # Stats ce mois
    month_missions = serializers.IntegerField()
    month_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # Stats globales
    total_missions = serializers.IntegerField()
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Missions en cours
    active_missions = serializers.IntegerField()
    pending_missions = serializers.IntegerField()
    
    # Niveau et streak
    level = serializers.CharField()
    current_streak = serializers.IntegerField()


class MissionProofBulkCreateSerializer(serializers.Serializer):
    """Serializer pour créer plusieurs preuves en une fois"""
    mission_id = serializers.IntegerField()
    proofs = serializers.ListField(
        child=serializers.DictField(),
        help_text="Liste des preuves à créer. Chaque preuve doit contenir: image, caption, location_lat, location_lng"
    )
    
    def validate_proofs(self, value):
        if not value:
            raise serializers.ValidationError("Au moins une preuve est requise")
        
        for i, proof in enumerate(value):
            if 'image' not in proof:
                raise serializers.ValidationError(
                    f"L'image est requise pour la preuve {i+1}"
                )
        return value


class MissionDetailSerializer(serializers.ModelSerializer):
    """Serializer retournant latitude/longitude plats (compatible Flutter)."""
    client_name = serializers.SerializerMethodField()
    agent_name = serializers.SerializerMethodField()
    agent_phone = serializers.SerializerMethodField()
    agent_email = serializers.SerializerMethodField()
    client_email = serializers.SerializerMethodField()
    agent_rating = serializers.SerializerMethodField()
    agent_latitude = serializers.SerializerMethodField()
    agent_longitude = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    escrow_status = serializers.SerializerMethodField()
    tags = serializers.SlugRelatedField(many=True, read_only=True, slug_field='name')
    category = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Mission
        fields = [
            'id', 'title', 'description', 'client_name', 'client_email',
            'agent_name', 'agent_phone', 'agent_email', 'agent_rating',
            'agent_latitude', 'agent_longitude',
            'avatar_url', 'escrow_status', 'tags', 'category',
            'latitude', 'longitude', 'address', 'price', 'service_fee',
            'purchase_amount', 'service_amount', 'is_urgent', 'is_confidential',
            'is_vocal_description', 'description_audio',
            'target_agent_username', 'status', 'requires_procuration',
            'qr_code_token', 'client_rating', 'client_comment',
            'created_at', 'updated_at',
        ]

    def get_client_name(self, obj):
        if obj.client:
            return obj.client.username or obj.client.email
        return None

    def get_category(self, obj):
        first_tag = obj.tags.first()
        return first_tag.name if first_tag else None

    def get_agent_name(self, obj):
        if obj.agent:
            name = f"{obj.agent.first_name} {obj.agent.last_name}".strip()
            return name or obj.agent.username or obj.agent.email
        return None

    def get_agent_phone(self, obj):
        return obj.agent.phone_number if obj.agent else None

    def get_agent_email(self, obj):
        return obj.agent.email if obj.agent else None

    def get_client_email(self, obj):
        return obj.client.email if obj.client else None

    def get_agent_rating(self, obj):
        if obj.agent and obj.client_rating:
            return obj.client_rating
        return None

    def get_agent_latitude(self, obj):
        return obj.agent.latitude if obj.agent else None

    def get_agent_longitude(self, obj):
        return obj.agent.longitude if obj.agent else None

    def get_avatar_url(self, obj):
        if obj.agent and obj.agent.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.agent.profile_picture.url)
            return obj.agent.profile_picture.url
        return None

    def get_escrow_status(self, obj):
        if hasattr(obj, 'escrow'):
            return obj.escrow.status
        return None

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None


class MissionCreateSerializer(serializers.Serializer):
    """Crée une mission depuis le payload Flutter (lat/lng → Point)."""
    title = serializers.CharField(
        max_length=255,
        error_messages={
            'required': 'Le titre de la mission est obligatoire.',
            'blank': 'Le titre ne peut pas être vide.',
            'max_length': 'Le titre est trop long (max 255 caractères).'
        }
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'blank': 'La description ne peut pas être vide.'
        }
    )
    address = serializers.CharField(
        max_length=500,
        error_messages={
            'required': 'L\'adresse est obligatoire.',
            'blank': 'L\'adresse ne peut pas être vide.',
            'max_length': 'L\'adresse est trop longue (max 500 caractères).'
        }
    )
    latitude = serializers.FloatField(
        error_messages={
            'required': 'La latitude est obligatoire.',
            'invalid': 'La latitude doit être un nombre valide.'
        }
    )
    longitude = serializers.FloatField(
        error_messages={
            'required': 'La longitude est obligatoire.',
            'invalid': 'La longitude doit être un nombre valide.'
        }
    )
    price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        error_messages={
            'required': 'Le prix est obligatoire.',
            'invalid': 'Le prix doit être un nombre valide.',
            'max_digits': 'Le prix est trop élevé.',
            'max_decimal_places': 'Le prix ne peut avoir que 2 décimales.'
        }
    )
    service_fee = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        required=False,
        error_messages={
            'invalid': 'Les frais de service doivent être un nombre valide.',
            'max_digits': 'Les frais de service sont trop élevés.',
            'max_decimal_places': 'Les frais de service ne peuvent avoir que 2 décimales.'
        }
    )
    requires_procuration = serializers.BooleanField(
        default=False,
        required=False,
        error_messages={
            'invalid': 'La valeur de procuration doit être vrai ou faux.'
        }
    )
    target_agent_username = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            'max_length': 'Le nom d\'utilisateur de l\'agent est trop long (max 150 caractères).'
        }
    )
    is_urgent = serializers.BooleanField(
        default=False,
        required=False,
        error_messages={'invalid': 'La valeur urgent doit être vrai ou faux.'}
    )
    is_confidential = serializers.BooleanField(
        default=False,
        required=False,
        error_messages={'invalid': 'La valeur agent interne doit être vrai ou faux.'}
    )
    is_vocal_description = serializers.BooleanField(
        default=False,
        required=False,
    )
    description_audio = serializers.FileField(required=False, allow_null=True)
    purchase_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        required=False,
        error_messages={
            'invalid': 'Le montant des achats doit être un nombre valide.',
            'max_digits': 'Le montant des achats est trop élevé.',
            'max_decimal_places': 'Le montant des achats ne peut avoir que 2 décimales.'
        }
    )
    service_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        required=False,
        error_messages={
            'invalid': 'Le montant de la prestation doit être un nombre valide.',
            'max_digits': 'Le montant de la prestation est trop élevé.',
            'max_decimal_places': 'Le montant de la prestation ne peut avoir que 2 décimales.'
        }
    )
    recurrence = serializers.CharField(
        max_length=20,
        required=False,
        default='once',
        allow_blank=True,
    )
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )
    category_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    def validate(self, attrs):
        category_id = attrs.pop('category_id', None)
        if category_id and not attrs.get('tag_ids'):
            attrs['tag_ids'] = [category_id]

        is_vocal = attrs.get('is_vocal_description', False)
        request = self.context.get('request')
        audio = attrs.get('description_audio') or (
            request.FILES.get('description_audio') if request else None
        )
        if is_vocal:
            if not audio:
                raise serializers.ValidationError(
                    {'description_audio': 'Un fichier audio est requis en mode vocal.'}
                )
            attrs['description'] = attrs.get('description') or 'Description vocale'
            attrs['description_audio'] = audio
        elif not (attrs.get('description') or '').strip():
            raise serializers.ValidationError(
                {'description': 'La description est obligatoire en mode texte.'}
            )
        return attrs

    def validate_target_agent_username(self, value):
        if not value:
            return value
        try:
            agent = User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                f"Aucun utilisateur trouvé avec le nom d'utilisateur '{value}'."
            )
        if not getattr(agent, 'is_agent', False):
            raise serializers.ValidationError(
                f"L'utilisateur '{value}' n'est pas un agent enregistré."
            )
        return value

    def create(self, validated_data):
        from .models import Tag

        lat = validated_data.pop('latitude')
        lng = validated_data.pop('longitude')
        tag_ids = validated_data.pop('tag_ids', [])
        validated_data.pop('recurrence', None)
        description_audio = validated_data.pop('description_audio', None)
        validated_data['location'] = Point(lng, lat, srid=4326)
        validated_data['client'] = self.context['request'].user
        mission = Mission.objects.create(**validated_data)
        if description_audio:
            mission.description_audio = description_audio
            mission.is_vocal_description = True
            mission.save(update_fields=['description_audio', 'is_vocal_description'])
        if tag_ids:
            tags = Tag.objects.filter(id__in=tag_ids)
            mission.tags.set(tags)
        return mission
