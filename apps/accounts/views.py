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
    
    # TODO: Intégrer un vrai service d'envoi d'emails (SendGrid, Mailjet...)
    return JsonResponse({
        'status': 'error',
        'message': 'La réinitialisation par email n\'est pas encore disponible. Contactez le support.',
        'data': {}
    }, status=status.HTTP_501_NOT_IMPLEMENTED)


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
                'is_new_user': status_code == status.HTTP_201_CREATED
            }
        }, status=status_code)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Erreur lors de l\'authentification Google: {str(e)}',
            'data': {}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_phone_view(request):
    """Met à jour le numéro de téléphone de l'utilisateur"""
    try:
        new_phone = request.data.get('phone_number')
        
        if not new_phone:
            return JsonResponse({
                'status': 'error',
                'message': 'Numéro de téléphone requis',
                'data': {}
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Vérifier si le numéro est déjà utilisé
        if User.objects.filter(phone_number=new_phone).exclude(id=request.user.id).exists():
            return JsonResponse({
                'status': 'error',
                'message': 'Ce numéro de téléphone est déjà utilisé',
                'data': {}
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Mettre à jour le numéro
        request.user.phone_number = new_phone
        request.user.save()
        
        logger.info("Numéro de téléphone mis à jour pour user=%s", request.user.username)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Numéro de téléphone mis à jour avec succès',
            'data': {'phone_number': new_phone}
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur mise à jour téléphone: %s", str(e))
        return JsonResponse({
            'status': 'error',
            'message': 'Erreur lors de la mise à jour du numéro de téléphone',
            'data': {}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST', 'PATCH'])
@permission_classes([IsAuthenticated])
def agent_status_view(request):
    """Met à jour le statut en ligne/hors ligne de l'agent"""
    try:
        # Vérifier que l'utilisateur est un agent
        if not request.user.is_agent:
            return JsonResponse({
                'status': 'error',
                'message': 'Accès refusé. Cette fonctionnalité est réservée aux agents.',
                'data': {}
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Récupérer le nouveau statut
        is_online = request.data.get('is_online', False)
        
        # Mettre à jour le statut (pour l'instant on utilise un champ temporaire)
        # TODO: Ajouter un champ is_online dans le modèle User quand nécessaire
        request.user.is_online = is_online
        request.user.save(update_fields=['is_online'])
        
        logger.info("Statut agent mis à jour: user=%s, is_online=%s", request.user.username, is_online)
        
        return JsonResponse({
            'status': 'success',
            'message': f'Statut mis à jour: {"en ligne" if is_online else "hors ligne"}',
            'data': {
                'is_online': is_online,
                'user_id': str(request.user.id)
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error("Erreur mise à jour statut agent: %s", str(e))
        return JsonResponse({
            'status': 'error',
            'message': 'Erreur lors de la mise à jour du statut',
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
    
    RADIUS_KM = 5.0
    DEG_PER_KM = 1.0 / 111.0

    base_qs = User.objects.filter(is_agent=True)

    if client_lat and client_lng:
        try:
            client_lat = float(client_lat)
            client_lng = float(client_lng)

            delta = RADIUS_KM * DEG_PER_KM
            agents_with_location = base_qs.filter(
                latitude__isnull=False,
                longitude__isnull=False,
                latitude__range=(client_lat - delta, client_lat + delta),
                longitude__range=(client_lng - delta, client_lng + delta),
            )

            agents_with_distance = []
            for agent in agents_with_location:
                distance = ((agent.latitude - client_lat) ** 2 +
                            (agent.longitude - client_lng) ** 2) ** 0.5 * 111
                if distance <= RADIUS_KM:
                    agents_with_distance.append((agent, distance))

            agents_with_distance.sort(key=lambda x: x[1])
            qs = [agent for agent, _ in agents_with_distance[:limit]]

            if not qs:
                qs = list(base_qs.order_by('-date_joined')[:limit])

        except (ValueError, TypeError):
            qs = list(base_qs.order_by('-date_joined')[:limit])
    else:
        qs = list(base_qs.order_by('-date_joined')[:limit])
    
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
                "is_online": u.is_online,
                "is_available": u.is_online and u.is_agent,
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def nearby_agents_view(request):
    """
    Agents à proximité avec filtres avancés.
    Accepte: latitude, longitude, radius_km, min_rating, verified_only, mission_types, min_price, max_price, limit
    """
    try:
        client_lat = request.GET.get('latitude')
        client_lng = request.GET.get('longitude')
        radius_km = float(request.GET.get('radius_km', 10))
        min_rating = float(request.GET.get('min_rating', 0))
        verified_only = request.GET.get('verified_only', 'true').lower() == 'true'
        mission_types_str = request.GET.get('mission_types', '')
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        limit = int(request.GET.get('limit', 20))

        if not client_lat or not client_lng:
            return JsonResponse({
                'status': 'error',
                'message': 'Coordonnées GPS requises',
                'data': []
            }, status=status.HTTP_400_BAD_REQUEST)

        client_lat = float(client_lat)
        client_lng = float(client_lng)

        DEG_PER_KM = 1.0 / 111.0
        delta = radius_km * DEG_PER_KM

        base_qs = User.objects.filter(is_agent=True, latitude__isnull=False, longitude__isnull=False)

        # Filtre par zone géographique
        agents_in_range = base_qs.filter(
            latitude__range=(client_lat - delta, client_lat + delta),
            longitude__range=(client_lng - delta, client_lng + delta),
        )

        # Filtre par note minimale
        if min_rating > 0:
            agents_in_range = agents_in_range.filter(reliability_score__gte=min_rating)

        # Filtre par vérification
        if verified_only:
            agents_in_range = agents_in_range.filter(is_verified=True)

        # Filtre par types de mission
        if mission_types_str:
            mission_types = mission_types_str.split(',')
            # Filtrer les agents qui offrent au moins un des types de mission demandés
            agents_in_range = agents_in_range.filter(
                offered_services__category__name__in=mission_types,
                offered_services__is_active=True
            ).distinct()

        # Calculer les distances et filtrer
        agents_with_distance = []
        for agent in agents_in_range:
            distance = ((agent.latitude - client_lat) ** 2 +
                        (agent.longitude - client_lng) ** 2) ** 0.5 * 111
            if distance <= radius_km:
                agents_with_distance.append((agent, distance))

        # Trier par distance
        agents_with_distance.sort(key=lambda x: x[1])
        qs = [agent for agent, _ in agents_with_distance[:limit]]

        rows = []
        for u in qs:
            # Calculer la distance précise
            distance_km = ((float(u.latitude) - client_lat) ** 2 + 
                         (float(u.longitude) - client_lng) ** 2) ** 0.5 * 111
            distance_km = round(distance_km, 1)

            # Obtenir la spécialité
            svc = u.offered_services.filter(is_active=True).first()
            specialty = ""
            if svc and svc.category:
                specialty = svc.category.name
            elif svc:
                specialty = svc.title

            avatar_url = u.profile_picture.url if u.profile_picture else None

            rows.append({
                "id": str(u.id),
                "username": u.username,
                "first_name": u.first_name or "",
                "last_name": u.last_name or "",
                "specialty": specialty or "Agent terrain",
                "is_verified": u.is_verified,
                "is_online": u.is_online,
                "is_available": u.is_online and u.is_agent,
                "avatar_url": avatar_url,
                "latitude": u.latitude,
                "longitude": u.longitude,
                "address": u.address,
                "city": u.city,
                "distance_km": distance_km,
                "reliability_score": u.reliability_score,
                "completion_rate": u.completion_rate,
            })

        return JsonResponse({
            'status': 'success',
            'message': 'Agents à proximité',
            'data': rows
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Erreur nearby agents: %s", str(e))
        return JsonResponse({
            'status': 'error',
            'message': 'Erreur lors de la récupération des agents',
            'data': []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
