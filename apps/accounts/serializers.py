from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'phone_number', 'username', 'is_agent', 'is_client', 'is_verified')

class RegisterSerializer(serializers.ModelSerializer):
    # Rôle optionnel avec valeur par défaut 'client'
    role = serializers.ChoiceField(choices=['client', 'agent'], write_only=True, default='client', required=False)
    username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # Email optionnel pour l'inscription
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ('email', 'phone_number', 'password', 'role', 'username')

    def create(self, validated_data):
        try:
            print(f"DEBUG SERIALIZER: Données reçues = {validated_data}")
            
            # Récupérer le rôle avec valeur par défaut 'client'
            role = validated_data.pop('role', 'client')
            print(f"DEBUG SERIALIZER: Rôle extrait = {role}")
            
            # Vérifier si le numéro de téléphone existe déjà
            phone_number = validated_data.get('phone_number')
            print(f"DEBUG SERIALIZER: Vérification téléphone = {phone_number}")
            
            if User.objects.filter(phone_number=phone_number).exists():
                print(f"DEBUG SERIALIZER: Téléphone déjà utilisé = {phone_number}")
                raise serializers.ValidationError({
                    'phone_number': 'Ce numéro de téléphone est déjà utilisé.'
                })
            
            # Créer l'utilisateur
            print(f"DEBUG SERIALIZER: Création utilisateur avec données = {validated_data}")
            
            # Gérer l'email optionnel
            user_data = validated_data.copy()
            if 'email' not in user_data or not user_data['email']:
                print("DEBUG SERIALIZER: Email vide, suppression des données email")
                user_data.pop('email', None)
            
            user = User.objects.create_user(**user_data)
            print(f"DEBUG SERIALIZER: Utilisateur créé = {user.id}")
            
            # Définir le rôle
            if role == 'agent':
                user.is_agent = True
                user.is_client = False
                print("DEBUG SERIALIZER: Rôle AGENT défini")
            else:
                user.is_client = True
                user.is_agent = False
                print("DEBUG SERIALIZER: Rôle CLIENT défini")
                
            user.save()
            print(f"DEBUG SERIALIZER: Utilisateur sauvegardé avec succès")
            return user
        except Exception as e:
            # Logger l'erreur pour le debug
            print(f"DEBUG SERIALIZER: ERREUR = {e}")
            import traceback
            print(f"DEBUG SERIALIZER: TRACEBACK = {traceback.format_exc()}")
            raise serializers.ValidationError({
                'non_field_errors': f'Erreur lors de l\'inscription: {str(e)}'
            })

class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        phone_number = data.get('phone_number')
        password = data.get('password')

        if phone_number and password:
            from django.contrib.auth import authenticate
            user = authenticate(request=self.context.get('request'), 
                              username=phone_number, 
                              password=password)
            
            if not user:
                raise serializers.ValidationError('Numéro de téléphone ou mot de passe incorrect.')
            
            if not user.is_active:
                raise serializers.ValidationError('Ce compte est désactivé.')
            
            data['user'] = user
            return data
        else:
            raise serializers.ValidationError('Le numéro de téléphone et le mot de passe sont requis.')

class RegisterSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(max_length=20)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('phone_number', 'username', 'password')

    def validate(self, data):
        phone_number = data.get('phone_number')
        username = data.get('username')
        password = data.get('password')

        if not all([phone_number, username, password]):
            raise serializers.ValidationError('Tous les champs sont requis.')

        # Vérifier si le numéro de téléphone existe déjà
        if User.objects.filter(phone_number=phone_number).exists():
            raise serializers.ValidationError('Ce numéro de téléphone est déjà utilisé.')

        # Vérifier si le username existe déjà
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError('Ce nom d\'utilisateur est déjà utilisé.')

        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            phone_number=validated_data['phone_number'],
            username=validated_data['username'],
            password=validated_data['password']
        )
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