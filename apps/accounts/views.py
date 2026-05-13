from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from .serializers import LoginSerializer, UserSerializer, RegisterSerializer, ProfileUpdateSerializer

User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Vue de connexion pour l'authentification JWT
    Attend: phone_number, password
    Retourne: status, message, data: {access_token, refresh_token, user}
    """
    serializer = LoginSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Génération des tokens JWT
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Sérialisation des données utilisateur
        user_data = UserSerializer(user).data
        
        return JsonResponse({
            'status': 'success',
            'message': 'Connexion réussie',
            'data': {
                'access_token': str(refresh.access_token),
                'user': user_data
            }
        }, status=status.HTTP_200_OK)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Erreur de connexion',
        'data': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """
    Vue d'inscription pour créer un nouvel utilisateur
    Attend: phone_number, username, password
    Retourne: status, message, data: {user}
    """
    serializer = RegisterSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        user = serializer.save()
        
        # Sérialisation des données utilisateur
        user_data = UserSerializer(user).data
        
        return JsonResponse({
            'status': 'success',
            'message': 'Inscription réussie',
            'data': {
                'user': user_data
            }
        }, status=status.HTTP_201_CREATED)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Erreur lors de l\'inscription',
        'data': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password_view(request):
    """
    Vue pour le mot de passe oublié
    Attend: email
    Retourne: status, message, data: {}
    """
    email = request.data.get('email')
    
    if not email:
        return JsonResponse({
            'status': 'error',
            'message': 'L\'adresse email est requise',
            'data': {}
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Simulation - envoyer un email de réinitialisation
    # TODO: Intégrer un vrai service d'envoi d'emails
    return JsonResponse({
        'status': 'success',
        'message': 'Un email de réinitialisation a été envoyé',
        'data': {
            'email': email
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def google_auth_view(request):
    """
    Vue pour l'authentification Google OAuth
    Attend: email, name, google_id
    Retourne: status, message, data: {access_token, user}
    """
    email = request.data.get('email')
    name = request.data.get('name')
    google_id = request.data.get('google_id')
    
    if not email or not google_id:
        return JsonResponse({
            'status': 'error',
            'message': 'Email et Google ID sont requis',
            'data': {}
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Vérifier si l'utilisateur existe déjà
        user = User.objects.filter(email=email).first()
        
        if user:
            # Cas A: L'utilisateur existe déjà - Connexion
            if not user.check_password('google_oauth_temp_password'):
                # Mettre à jour le mot de passe temporaire si nécessaire
                user.set_password('google_oauth_temp_password')
                user.save()
            
            message = 'Connexion réussie avec Google'
            status_code = status.HTTP_200_OK
        else:
            # Cas B: L'utilisateur n'existe pas - Création automatique du profil
            username = email.split('@')[0]  # Extraire username de l'email
            counter = 1
            original_username = username
            
            # S'assurer que le username est unique
            while User.objects.filter(username=username).exists():
                username = f"{original_username}_{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password='google_oauth_temp_password',  # Mot de passe temporaire
                first_name=name.split()[0] if name else '',
                last_name=' '.join(name.split()[1:]) if name and len(name.split()) > 1 else '',
            )
            
            # Par défaut, les utilisateurs Google sont des clients
            user.is_client = True
            user.is_agent = False
            user.save()
            
            message = 'Compte créé avec succès via Google'
            status_code = status.HTTP_201_CREATED
        
        # Génération des tokens JWT
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        # Sérialisation des données utilisateur
        user_data = UserSerializer(user).data
        
        return JsonResponse({
            'status': 'success',
            'message': message,
            'data': {
                'access_token': access_token,
                'user': user_data,
                'is_new_user': not User.objects.filter(email=email).exclude(pk=user.pk).exists()
            }
        }, status=status_code)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Erreur lors de l\'authentification Google: {str(e)}',
            'data': {}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    Vue pour consulter et mettre à jour le profil utilisateur
    GET: Retourne les informations du profil
    PATCH: Met à jour les informations du profil
    """
    user = request.user
    
    if request.method == 'GET':
        serializer = UserSerializer(user)
        return JsonResponse({
            'status': 'success',
            'message': 'Profil récupéré avec succès',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'PATCH':
        serializer = ProfileUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            updated_user = serializer.save()
            
            # Retourner les données complètes mises à jour
            user_serializer = UserSerializer(updated_user)
            return JsonResponse({
                'status': 'success',
                'message': 'Profil mis à jour avec succès',
                'data': user_serializer.data
            }, status=status.HTTP_200_OK)
        
        return JsonResponse({
            'status': 'error',
            'message': 'Erreur lors de la mise à jour du profil',
            'data': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
