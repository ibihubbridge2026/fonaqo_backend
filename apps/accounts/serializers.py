from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'phone_number', 'username', 'is_agent', 'is_client', 'is_verified')

class RegisterSerializer(serializers.ModelSerializer):
    # On oblige Flutter à envoyer le rôle
    role = serializers.ChoiceField(choices=['client', 'agent'], write_only=True)

    class Meta:
        model = User
        fields = ('email', 'phone_number', 'password', 'role')

    def create(self, validated_data):
        role = validated_data.pop('role')
        user = User.objects.create_user(**validated_data)
        
        if role == 'agent':
            user.is_agent = True
            user.is_client = False # Un agent peut aussi être client si tu veux, mais souvent on sépare au début
        else:
            user.is_client = True
            user.is_agent = False
            
        user.save()
        return user

class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('phone_number', 'id_card_front', 'id_card_back', 'selfie_with_id', 
                  'witness_1_name', 'witness_1_phone', 'witness_2_name', 'witness_2_phone')

    def validate_phone_number(self, value):
        if not value:
            raise serializers.ValidationError("Le numéro de téléphone est obligatoire pour l'activation.")
        return value        