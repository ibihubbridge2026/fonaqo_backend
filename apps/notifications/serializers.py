from rest_framework import serializers
from fcm_django.models import FCMDevice
from .models import InAppNotification

class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = ('registration_id', 'name', 'type')

    def create(self, validated_data):
        # On lie l'appareil à l'utilisateur connecté
        user = self.context['request'].user
        # On évite les doublons de tokens
        device, created = FCMDevice.objects.get_or_create(
            registration_id=validated_data['registration_id'],
            defaults={
                'user': user,
                'type': validated_data.get('type', 'android'),
                'name': validated_data.get('name', f"Device of {user.phone_number}")
            }
        )
        if not created:
            device.user = user
            device.save()
        return device


class InAppNotificationSerializer(serializers.ModelSerializer):
    """Serializer pour les notifications in-app."""
    
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = InAppNotification
        fields = (
            'id',
            'title',
            'body',
            'action',
            'target_id',
            'is_read',
            'created_at',
            'time_ago',
        )
        read_only_fields = fields
    
    def get_time_ago(self, obj):
        """Calcule le temps relatif depuis la création."""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff < timedelta(minutes=1):
            return "maintenant"
        elif diff < timedelta(hours=1):
            return f"{diff.seconds // 60} min"
        elif diff < timedelta(days=1):
            return f"{diff.seconds // 3600}h"
        elif diff < timedelta(days=7):
            return f"{diff.days}j"
        else:
            return obj.created_at.strftime("%d/%m/%Y")