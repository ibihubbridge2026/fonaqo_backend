import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.choices import MissionStatus
from apps.missions.models import Mission

from .models import FavoriteAgent, AgentProfile
from .serializers import LoginSerializer, ProfileUpdateSerializer, RegisterSerializer, UserSerializer
from apps.core.choices import AgentKYCStatus

User = get_user_model()
logger = logging.getLogger(__name__)


def _agent_specialty(user):
    svc = user.offered_services.filter(is_active=True).first()
    if svc and svc.category:
        return svc.category.name
    if svc:
        return svc.title
    return "Agent terrain"


def _agent_avatar_url(user, request):
    if not user.profile_picture:
        return ""
    url = user.profile_picture.url
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def _agent_rating(user):
    score = user.reliability_score or 0
    if score <= 0:
        return 0.0
    if score <= 5:
        return round(float(score), 1)
    return round(min(5.0, float(score) / 20.0), 1)


def _agent_to_artisan_dict(user, request=None):
    from apps.accounts.badges import compute_agent_badge
    from apps.accounts.models import AgentProfile
    from apps.boosts.models import AgentBoost

    completed = Mission.objects.filter(
        agent=user,
        status=MissionStatus.COMPLETED,
    ).count()
    joined = user.date_joined
    years = max(0, timezone.now().year - joined.year) if joined else 0
    profile, _ = AgentProfile.objects.get_or_create(user=user)
    now = timezone.now()
    has_boost = AgentBoost.objects.filter(
        agent=user, status='active', expires_at__gt=now,
    ).exists()
    reviews = Mission.objects.filter(
        agent=user,
        status=MissionStatus.COMPLETED,
        client_rating__isnull=False,
    ).order_by('-updated_at')[:20]

    return {
        "id": str(user.id),
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "avatar_url": _agent_avatar_url(user, request),
        "specialty": _agent_specialty(user),
        "biography": profile.bio or "",
        "bio": profile.bio or "",
        "years_of_experience": years,
        "city": user.city or "",
        "district": user.address or "",
        "phone": user.phone_number or "",
        "email": user.email or "",
        "rating": _agent_rating(user),
        "completed_missions": completed,
        "badge": compute_agent_badge(completed),
        "certified": user.is_verified,
        "premium": bool(user.level_id),
        "is_boosted": has_boost,
        "service_domain": user.service_domain or "",
        "gallery": [],
        "reviews": [
            {
                "rating": m.client_rating,
                "comment": m.client_comment or "",
                "client_name": (
                    f"{m.client.first_name} {m.client.last_name}".strip()
                    or m.client.username
                ),
                "created_at": m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in reviews
        ],
    }


def _verified_agents_queryset():
    return User.objects.filter(is_agent=True, is_verified=True)


def _listing_to_artisan_dict(listing, request=None):
  photo_url = listing.photo.url if listing.photo else None
  if request and photo_url and not photo_url.startswith('http'):
    photo_url = request.build_absolute_uri(photo_url)
  return {
    'id': str(listing.id),
    'first_name': listing.name.split(' ')[0] if listing.name else '',
    'last_name': ' '.join(listing.name.split(' ')[1:]) if listing.name else '',
    'name': listing.name,
    'avatar_url': photo_url,
    'specialty': listing.specialty or listing.get_category_display(),
    'biography': listing.description or '',
    'bio': listing.description or '',
    'city': listing.city or '',
    'district': listing.district or '',
    'phone': listing.phone or '',
    'email': listing.email or '',
    'rating': float(listing.rating or 0),
    'certified': listing.is_featured,
    'source': 'leboncoin',
  }


def _agent_suggestion_priority(user, now=None):
    """Score de priorité : interne et boost actif en tête."""
    from apps.accounts.models import AgentProfile
    from apps.boosts.models import AgentBoost

    if now is None:
        now = timezone.now()
    profile = AgentProfile.objects.filter(user=user).first()
    score = 0
    if profile and profile.is_internal:
        score += 100
    if AgentBoost.objects.filter(agent=user, status='active', expires_at__gt=now).exists():
        score += 50
    if user.is_verified:
        score += 10
    return score


@api_view(['GET'])
@permission_classes([AllowAny])
def public_artisans_list_view(request):
    """
    Annuaire public des artisans experts (LeBonCoin — LocalListing).
    Filtres optionnels: query, specialty, location.
    """
    from apps.leboncoin.models import LocalListing

    qs = LocalListing.objects.filter(
        category=LocalListing.Category.ARTISAN,
        is_active=True,
    )

    query = (request.GET.get('query') or '').strip()
    specialty = (request.GET.get('specialty') or '').strip()
    location = (request.GET.get('location') or '').strip()

    if specialty:
        qs = qs.filter(
            Q(specialty__icontains=specialty) | Q(description__icontains=specialty),
        )

    if location:
        qs = qs.filter(
            Q(city__icontains=location) | Q(district__icontains=location) | Q(address__icontains=location),
        )

    if query:
        qs = qs.filter(
            Q(name__icontains=query)
            | Q(specialty__icontains=query)
            | Q(city__icontains=query)
            | Q(district__icontains=query)
            | Q(description__icontains=query),
        )

    rows = [
        _listing_to_artisan_dict(listing, request)
        for listing in qs.order_by('-is_featured', '-rating', 'name')
    ]

    return JsonResponse(
        {
            "status": "success",
            "message": "Artisans publics",
            "data": rows,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def public_artisan_detail_view(request, artisan_id):
    """Détail public d'un artisan LeBonCoin par identifiant."""
    from apps.leboncoin.models import LocalListing

    listing = LocalListing.objects.filter(
        pk=artisan_id,
        category=LocalListing.Category.ARTISAN,
        is_active=True,
    ).first()
    if listing is None:
        return JsonResponse(
            {
                "status": "error",
                "message": "Artisan introuvable",
                "data": {},
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    return JsonResponse(
        {
            "status": "success",
            "message": "Artisan public",
            "data": _listing_to_artisan_dict(listing, request),
        },
        status=status.HTTP_200_OK,
    )


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
    
    errors = serializer.errors
    code = errors.get('code')
    if isinstance(code, list):
        code = code[0] if code else None
    detail = errors.get('detail')
    if isinstance(detail, list):
        detail = detail[0] if detail else None
    if str(code) == 'ACCOUNT_SUSPENDED':
        return JsonResponse({
            'status': 'error',
            'message': detail or 'Compte suspendu',
            'code': 'ACCOUNT_SUSPENDED',
            'data': {},
        }, status=status.HTTP_403_FORBIDDEN)

    return JsonResponse({
        'status': 'error',
        'message': 'Erreur de connexion',
        'data': errors,
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
    
    errors = serializer.errors
    username_errors = errors.get('username')
    if username_errors:
        first_msg = (
            username_errors[0]
            if isinstance(username_errors, list)
            else str(username_errors)
        )
        if 'déjà utilisé' in first_msg:
            return JsonResponse(
                {'message': 'Ce nom d\'utilisateur est déjà utilisé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    return JsonResponse(
        {
            'status': 'error',
            'message': 'Erreur lors de l\'inscription',
            'data': errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password_view(request):
    """
    Mot de passe oublié — email (message info) ou téléphone (demande staff PENDING).
    """
    from apps.core.models import PasswordResetRequest

    email = (request.data.get('email') or '').strip()
    phone = (request.data.get('phone_number') or request.data.get('phone') or '').strip()

    if phone:
        user = User.objects.filter(phone_number=phone).first()
        if not user:
            return JsonResponse({
                'status': 'success',
                'message': 'Si ce numéro est enregistré, une demande a été créée.',
                'data': {},
            }, status=status.HTTP_200_OK)

        existing = PasswordResetRequest.objects.filter(
            user=user, status=PasswordResetRequest.Status.PENDING,
        ).exists()
        if not existing:
            PasswordResetRequest.objects.create(user=user, phone_number=phone)

        return JsonResponse({
            'status': 'success',
            'message': (
                'Demande enregistrée. Un administrateur FONACO vous contactera '
                'avec un mot de passe temporaire.'
            ),
            'data': {'method': 'phone'},
        }, status=status.HTTP_200_OK)

    if email:
        return JsonResponse({
            'status': 'error',
            'message': (
                'Réinitialisation par email bientôt disponible. '
                'Utilisez l\'onglet Numéro ou contactez le support.'
            ),
            'data': {},
        }, status=status.HTTP_501_NOT_IMPLEMENTED)

    return JsonResponse({
        'status': 'error',
        'message': 'Numéro de téléphone ou email requis',
        'data': {},
    }, status=status.HTTP_400_BAD_REQUEST)


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
            user.save(update_fields=['is_client', 'is_agent', 'updated_at'])
            
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
        request.user.save(update_fields=['phone_number', 'updated_at'])
        
        logger.info("Numéro de téléphone mis à jour pour user=%s", request.user.username)
        
        user_data = UserSerializer(request.user).data
        return JsonResponse({
            'status': 'success',
            'message': 'Numéro de téléphone mis à jour avec succès',
            'data': {
                'phone_number': new_phone,
                'user': user_data,
            },
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
        serializer = UserSerializer(user, context={'request': request})
        return JsonResponse({
            'status': 'success',
            'message': 'Profil récupéré avec succès',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'PATCH':
        try:
            serializer = ProfileUpdateSerializer(
                user, data=request.data, partial=True, context={'request': request},
            )
            if serializer.is_valid():
                updated_user = serializer.save()
                user_serializer = UserSerializer(updated_user, context={'request': request})
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
        except Exception as exc:
            logger.exception('Erreur mise à jour profil user=%s', user.id)
            return JsonResponse({
                'status': 'error',
                'message': f'Erreur serveur: {exc}',
                'data': {},
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

            agents_with_distance.sort(key=lambda x: (-_agent_suggestion_priority(x[0]), x[1]))
            qs = [agent for agent, _ in agents_with_distance[:limit]]

            if not qs:
                fallback = list(base_qs.order_by('-date_joined')[:limit * 2])
                fallback.sort(key=lambda u: (-_agent_suggestion_priority(u), u.date_joined), reverse=True)
                qs = fallback[:limit]

        except (ValueError, TypeError):
            fallback = list(base_qs.order_by('-date_joined')[:limit * 2])
            fallback.sort(key=lambda u: (-_agent_suggestion_priority(u), u.date_joined), reverse=True)
            qs = fallback[:limit]
    else:
        fallback = list(base_qs.order_by('-date_joined')[:limit * 2])
        fallback.sort(key=lambda u: (-_agent_suggestion_priority(u), u.date_joined), reverse=True)
        qs = fallback[:limit]
    
    # Fallback : si aucun agent, renvoyer les agents non vérifiés
    if not qs:
        fallback = list(User.objects.filter(is_agent=True).order_by("-date_joined")[:limit * 2])
        fallback.sort(key=lambda u: (-_agent_suggestion_priority(u), u.date_joined), reverse=True)
        qs = fallback[:limit]
    
    rows = []
    from apps.accounts.models import AgentProfile
    from apps.boosts.models import AgentBoost
    now = timezone.now()
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
        
        expertise_tags = list(
            u.offered_services.filter(is_active=True)
            .values_list("category__name", flat=True)
            .distinct()[:5]
        )
        profile = AgentProfile.objects.filter(user=u).first()
        is_internal = bool(profile and profile.is_internal)
        is_boosted = AgentBoost.objects.filter(
            agent=u, status='active', expires_at__gt=now,
        ).exists()

        rows.append(
            {
                "id": str(u.id),
                "username": u.username,
                "first_name": u.first_name or "",
                "last_name": u.last_name or "",
                "specialty": specialty or "Agent terrain",
                "expertise_tags": expertise_tags,
                "is_verified": u.is_verified,
                "is_internal": is_internal,
                "is_boosted": is_boosted,
                "is_priority": is_internal or is_boosted,
                "agent_code": profile.agent_code if profile else "",
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

        use_gps = bool(client_lat and client_lng)

        base_qs = User.objects.filter(is_agent=True)

        if use_gps:
            client_lat = float(client_lat)
            client_lng = float(client_lng)
            DEG_PER_KM = 1.0 / 111.0
            delta = radius_km * DEG_PER_KM
            base_qs = base_qs.filter(
                latitude__isnull=False,
                longitude__isnull=False,
                latitude__range=(client_lat - delta, client_lat + delta),
                longitude__range=(client_lng - delta, client_lng + delta),
            )
        
        # Filtre par note minimale
        if min_rating > 0:
            base_qs = base_qs.filter(reliability_score__gte=min_rating)

        # Filtre par vérification
        if verified_only:
            base_qs = base_qs.filter(is_verified=True)

        # Filtre par types de mission
        if mission_types_str:
            mission_types = mission_types_str.split(',')
            base_qs = base_qs.filter(
                offered_services__category__name__in=mission_types,
                offered_services__is_active=True
            ).distinct()

        if use_gps:
            # Calculer les distances et filtrer
            agents_with_distance = []
            for agent in base_qs:
                if agent.latitude is None or agent.longitude is None:
                    continue
                distance = ((float(agent.latitude) - client_lat) ** 2 +
                            (float(agent.longitude) - client_lng) ** 2) ** 0.5 * 111
                if distance <= radius_km:
                    agents_with_distance.append((agent, distance))
            agents_with_distance.sort(key=lambda x: x[1])
            qs = [agent for agent, _ in agents_with_distance[:limit]]
        else:
            # Sans GPS : retourner tous les agents actifs triés par fiabilité
            qs = list(base_qs.order_by('-reliability_score', '-is_online')[:limit])

        rows = []
        from apps.boosts.models import AgentBoost
        now = timezone.now()
        for u in qs:
            if use_gps and u.latitude is not None and u.longitude is not None:
                distance_km = round(((float(u.latitude) - client_lat) ** 2 +
                             (float(u.longitude) - client_lng) ** 2) ** 0.5 * 111, 1)
            else:
                distance_km = None

            # Obtenir la spécialité
            svc = u.offered_services.filter(is_active=True).first()
            specialty = ""
            if svc and svc.category:
                specialty = svc.category.name
            elif svc:
                specialty = svc.title

            avatar_url = u.profile_picture.url if u.profile_picture else None
            expertise_tags = list(
                u.offered_services.filter(is_active=True)
                .values_list("category__name", flat=True)
                .distinct()[:5]
            )

            rows.append({
                "id": str(u.id),
                "username": u.username,
                "first_name": u.first_name or "",
                "last_name": u.last_name or "",
                "specialty": specialty or "Agent terrain",
                "expertise_tags": expertise_tags,
                "is_verified": u.is_verified,
                "is_boosted": AgentBoost.objects.filter(
                    agent=u, status='active', expires_at__gt=now,
                ).exists(),
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def favorites_list_view(request):
    """Liste des IDs d'agents favoris du client connecté."""
    if not request.user.is_client:
        return JsonResponse(
            {'status': 'error', 'message': 'Réservé aux clients', 'data': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    agent_ids = [
        str(agent_id)
        for agent_id in FavoriteAgent.objects.filter(client=request.user)
        .values_list('agent_id', flat=True)
    ]
    return JsonResponse(
        {'status': 'success', 'message': 'Favoris', 'data': agent_ids},
        status=status.HTTP_200_OK,
    )


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def favorites_detail_view(request, agent_id):
    """Ajoute (POST) ou retire (DELETE) un agent des favoris."""
    if not request.user.is_client:
        return JsonResponse(
            {'status': 'error', 'message': 'Réservé aux clients', 'data': {}},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'POST':
        agent = User.objects.filter(pk=agent_id, is_agent=True).first()
        if agent is None:
            return JsonResponse(
                {'status': 'error', 'message': 'Agent introuvable', 'data': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        FavoriteAgent.objects.get_or_create(client=request.user, agent=agent)
        return JsonResponse(
            {
                'status': 'success',
                'message': 'Agent ajouté aux favoris',
                'data': {'agent_id': str(agent.id)},
            },
            status=status.HTTP_201_CREATED,
        )

    deleted, _ = FavoriteAgent.objects.filter(
        client=request.user,
        agent_id=agent_id,
    ).delete()
    if not deleted:
        return JsonResponse(
            {'status': 'error', 'message': 'Favori introuvable', 'data': {}},
            status=status.HTTP_404_NOT_FOUND,
        )
    return JsonResponse(
        {'status': 'success', 'message': 'Agent retiré des favoris', 'data': {}},
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
        confirm_password = request.data.get('confirm_password')

        if not old_password or not new_password or not confirm_password:
            return JsonResponse(
                {
                    'message': (
                        'Ancien mot de passe, nouveau mot de passe '
                        'et confirmation sont requis.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return JsonResponse(
                {'message': 'Les nouveaux mots de passe ne correspondent pas.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(str(new_password)) < 8:
            return JsonResponse(
                {
                    'message': (
                        'Le mot de passe doit contenir au moins 8 caractères.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.check_password(old_password):
            return JsonResponse(
                {'message': 'Ancien mot de passe incorrect.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(new_password)
        request.user.save(update_fields=['password', 'updated_at'])
        
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def kyc_submit_view(request):
    """Soumission KYC agent (pièce d'identité + selfie)."""
    user = request.user
    if not user.is_agent:
        return JsonResponse(
            {'message': 'Réservé aux agents.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    id_card = request.FILES.get('id_card_photo')
    selfie = request.FILES.get('selfie_photo')
    if not id_card or not selfie:
        return JsonResponse(
            {'message': 'Les fichiers id_card_photo et selfie_photo sont obligatoires.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile, _ = AgentProfile.objects.get_or_create(user=user)
    profile.id_card_photo = id_card
    profile.selfie_photo = selfie
    profile.kyc_status = AgentKYCStatus.SUBMITTED
    profile.rejection_reason = ''
    profile.save()

    return JsonResponse({
        'status': 'success',
        'message': 'Documents KYC soumis. Validation en cours.',
        'data': {'kyc_status': profile.kyc_status},
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def referral_join_preview(request, referral_slug):
    """
    Valide un slug de parrainage deep link (fonaco.app/join/CODE).
    Utilisé par Flutter avant inscription.
    """
    from .models import Influencer

    code = (referral_slug or '').strip()
    if not code:
        return Response({'message': 'Code invalide.'}, status=status.HTTP_400_BAD_REQUEST)

    influencer = Influencer.objects.filter(
        Q(code_promo__iexact=code) | Q(referral_slug__iexact=code),
    ).select_related('user').first()
    if not influencer:
        return Response({'message': 'Code de parrainage inconnu.'}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'referral_code': influencer.referral_slug or influencer.code_promo,
        'influencer_name': influencer.user.get_full_name() or influencer.user.username,
        'valid': True,
    })
