from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .services import AISearchService
from .serializers import SearchRequestSerializer
from .models import SearchQueryLog

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_agents(request):
    """Recherche IA d'agents pour un client"""
    serializer = SearchRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': serializer.errors}, status=400)
    
    query = serializer.validated_data['query']
    
    # Analyse et recherche
    analysis = AISearchService.analyze_query(query, 'client')
    agents = AISearchService.find_agents_for_client(query, request.user)
    
    # Log la recherche
    SearchQueryLog.objects.create(
        user=request.user,
        query=query,
        user_type='client',
        results_count=len(agents)
    )
    
    # Génération phrase humaine
    service_phrase = ""
    if analysis['service_type']:
        service_phrase = f"un agent spécialisé en {analysis['service_type']}"
    else:
        service_phrase = "un agent disponible"
    
    analysis_text = f"Je cherche {service_phrase} {analysis.get('timeframe', '')}."
    if analysis['location']:
        analysis_text += f" Près de {analysis['location']}."
    
    return Response({
        'analysis': analysis_text,
        'agents': agents
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_missions(request):
    """Recherche IA de missions pour un agent"""
    serializer = SearchRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': serializer.errors}, status=400)
    
    query = serializer.validated_data['query']
    
    # Analyse et recherche
    analysis = AISearchService.analyze_query(query, 'agent')
    missions = AISearchService.find_missions_for_agent(query, request.user)
    
    # Log la recherche
    SearchQueryLog.objects.create(
        user=request.user,
        query=query,
        user_type='agent',
        results_count=len(missions)
    )
    
    # Génération phrase humaine
    service_phrase = ""
    if analysis['service_type']:
        service_phrase = f"une mission de {analysis['service_type']}"
    else:
        service_phrase = "une mission"
    
    urgency_phrase = "standard"
    if analysis['urgency'] == 'high':
        urgency_phrase = "urgente"
    
    analysis_text = f"Je cherche {service_phrase} {urgency_phrase}."
    if analysis['location']:
        analysis_text += f" Près de {analysis['location']}."
    
    return Response({
        'analysis': analysis_text,
        'missions': missions
    })
