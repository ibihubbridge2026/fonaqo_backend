from rest_framework import serializers
from fcm_django.models import FCMDevice

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