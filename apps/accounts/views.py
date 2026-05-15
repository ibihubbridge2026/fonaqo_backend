import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from .serializers import LoginSerializer, UserSerializer, RegisterSerializer, ProfileUpdateSerializer

User = get_user_model()
logger = logging.getLogger(__name__)

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
                'access_token': access_token,
                'refresh_token': refresh_token,
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
    Attend: phone_number, username, password, role, email (optionnel)
    Retourne: status, message, data: {access_token, refresh_token, user}
    """
    serializer = RegisterSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        user = serializer.save()
        
        # Génération des tokens JWT (comme pour le login)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Sérialisation des données utilisateur
        user_data = UserSerializer(user).data
        
        # Envoi d'email de bienvenue (non bloquant)
        try:
            from apps.services.email_utils import send_welcome_email, log_email_status
            
            # Vérifier la disponibilité de MailDev
            maildev_ok = log_email_status()
            
            if maildev_ok:
                # Envoyer l'email si MailDev est disponible
                email_sent = send_welcome_email(
                    user_email=user.email,
                    user_name=user.username or user.first_name or 'Utilisateur'
                )
                if email_sent:
                    logger.info("Email de bienvenue envoyé avec succès user=%s", user.id)
                else:
                    logger.warning("Échec envoi email de bienvenue user=%s", user.id)
            else:
                logger.warning("MailDev non disponible, email non envoyé user=%s", user.id)
                
        except Exception as email_error:
            # L'erreur d'email ne doit pas faire échouer l'inscription
            logger.error("Erreur critique envoi email user=%s: %s", user.id, str(email_error))
        
        logger.info("Inscription réussie avec tokens user=%s", user.id)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Inscription réussie',
            'data': {
                'access_token': access_token,
                'refresh_token': refresh_token,
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
    
    import secrets

    try:
        # Vérifier si l'utilisateur existe déjà
        user = User.objects.filter(email=email).first()
        
        if user:
            # Cas A: L'utilisateur existe déjà - Connexion directe (pas besoin de mot de passe)
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
            
            # Mot de passe aléatoire sécurisé (l'utilisateur se connecte via Google, jamais par mot de passe)
            secure_password = secrets.token_urlsafe(32)
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=secure_password,
                first_name=name.split()[0] if name else '',
                last_name=' '.join(name.split()[1:]) if name and len(name.split()) > 1 else '',
            )
            user.set_unusable_password()  # Marquer le mot de passe comme inutilisable
            
            # Par défaut, les utilisateurs Google sont des clients
            user.is_client = True
            user.is_agent = False
            user.save()
            
            message = 'Compte créé avec succès via Google'
            status_code = status.HTTP_201_CREATED
        
        # Génération des tokens JWT
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Sérialisation des données utilisateur
        user_data = UserSerializer(user).data
        
        return JsonResponse({
            'status': 'success',
            'message': message,
            'data': {
                'access_token': access_token,
                'refresh_token': refresh_token,
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


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_phone_view(request):
    """
    Vue pour mettre à jour le numéro de téléphone de l'utilisateur
    PATCH: Met à jour uniquement le numéro de téléphone
    """
    user = request.user
    phone_number = request.data.get('phone_number')
    
    if not phone_number:
        return JsonResponse({
            'status': 'error',
            'message': 'Le numéro de téléphone est requis',
            'data': {}
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Vérifier si le numéro de téléphone est déjà utilisé par un autre utilisateur
    if User.objects.filter(phone_number=phone_number).exclude(pk=user.pk).exists():
        return JsonResponse({
            'status': 'error',
            'message': 'Ce numéro de téléphone est déjà utilisé',
            'data': {}
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user.phone_number = phone_number
        user.save()
        
        # Retourner les données utilisateur mises à jour
        user_serializer = UserSerializer(user)
        return JsonResponse({
            'status': 'success',
            'message': 'Numéro de téléphone mis à jour avec succès',
            'data': {
                'user': user_serializer.data
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f'Erreur lors de la mise à jour du téléphone: {e}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erreur lors de la mise à jour: {str(e)}',
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_suggestions_view(request):
    """
    Agents pour le dashboard (cartes suggestions).
    Filtrage par localisation si fourni, sinon retourne les agents les plus proches.
    Priorité aux vérifiés, fallback sur tous les agents.
    """
    # Récupérer les coordonnées du client si disponibles
    client_lat = request.GET.get('latitude')
    client_lng = request.GET.get('longitude')
    limit = int(request.GET.get('limit', 12))
    
    # Base query pour les agents vérifiés
    base_qs = User.objects.filter(is_agent=True, is_verified=True)
    
    # Si le client a des coordonnées, filtrer par proximité
    if client_lat and client_lng:
        try:
            client_lat = float(client_lat)
            client_lng = float(client_lng)
            
            # Filtrer les agents avec des coordonnées valides
            agents_with_location = base_qs.filter(
                latitude__isnull=False,
                longitude__isnull=False
            )
            
            # Calculer la distance et trier (formule Haversine simplifiée)
            agents_with_distance = []
            for agent in agents_with_location:
                # Distance approximative en km
                distance = ((agent.latitude - client_lat) ** 2 + 
                           (agent.longitude - client_lng) ** 2) ** 0.5 * 111  # ~111km par degré
                agents_with_distance.append((agent, distance))
            
            # Trier par distance et prendre les plus proches
            agents_with_distance.sort(key=lambda x: x[1])
            qs = [agent for agent, distance in agents_with_distance[:limit]]
            
        except (ValueError, TypeError):
            # En cas d'erreur, fallback sur la liste par défaut
            qs = base_qs.order_by("-date_joined")[:limit]
    else:
        # Pas de coordonnées, retourner les agents les plus récents
        qs = base_qs.order_by("-date_joined")[:limit]
    
    # Fallback : si aucun agent vérifié, renvoyer les agents non vérifiés
    if not qs:
        qs = User.objects.filter(is_agent=True).order_by("-date_joined")[:limit]
    
    rows = []
    for u in qs:
        svc = u.offered_services.filter(is_active=True).first()
        specialty = ""
        if svc and svc.category:
            specialty = svc.category.name
        elif svc:
            specialty = svc.title
        
        avatar_url = u.profile_picture.url if u.profile_picture else None
        
        # Calculer la distance si les coordonnées du client sont disponibles
        distance_km = None
        if client_lat and client_lng and u.latitude and u.longitude:
            try:
                distance_km = ((float(u.latitude) - float(client_lat)) ** 2 + 
                             (float(u.longitude) - float(client_lng)) ** 2) ** 0.5 * 111
                distance_km = round(distance_km, 1)
            except (ValueError, TypeError):
                pass
        
        rows.append(
            {
                "id": str(u.id),
                "username": u.username,
                "first_name": u.first_name or "",
                "last_name": u.last_name or "",
                "specialty": specialty or "Agent terrain",
                "is_verified": u.is_verified,
                "avatar_url": avatar_url,
                "latitude": u.latitude,
                "longitude": u.longitude,
                "address": u.address,
                "city": u.city,
                "distance_km": distance_km,
                "reliability_score": u.reliability_score,
                "completion_rate": u.completion_rate,
            }
        )
    
    return JsonResponse(
        {
            "status": "success",
            "message": "Suggestions agents",
            "data": rows,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """
    Changement de mot de passe utilisateur
    """
    try:
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not old_password or not new_password:
            return JsonResponse({
                'status': 'error',
                'message': 'Ancien et nouveau mot de passe requis',
                'data': {}
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Vérifier l'ancien mot de passe
        if not request.user.check_password(old_password):
            return JsonResponse({
                'status': 'error', 
                'message': 'Ancien mot de passe incorrect',
                'data': {}
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Changer le mot de passe
        request.user.set_password(new_password)
        request.user.save()
        
        logger.info("Mot de passe changé pour user=%s", request.user.username)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Mot de passe changé avec succès',
            'data': {}
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur changement mot de passe: %s", str(e))
        return JsonResponse({
            'status': 'error',
            'message': 'Erreur lors du changement de mot de passe',
            'data': {}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
