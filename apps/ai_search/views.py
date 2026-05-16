from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from .models import AISearchQuery, AISearchSuggestion
from .serializers import AISearchQuerySerializer, AISearchSuggestionSerializer
from .services import AISearchService


class AISearchViewSet(viewsets.ModelViewSet):
    """ViewSet pour la recherche IA"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = AISearchQuerySerializer
    
    def get_queryset(self):
        return AISearchQuery.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Effectue une recherche IA et sauvegarde le résultat"""
        query = request.data.get('query', '').strip()
        search_type = request.data.get('type', 'general').strip()
        
        if not query:
            return Response(
                {'error': 'La requête ne peut pas être vide'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Valider le type de recherche
        valid_types = ['agent', 'mission', 'general']
        if search_type not in valid_types:
            search_type = 'general'
        
        # Utiliser le service IA pour traiter la requête
        ai_service = AISearchService()
        response = ai_service.search(query, request.user, search_type)
        
        # Sauvegarder la recherche
        search_query = AISearchQuery.objects.create(
            user=request.user,
            query=query,
            response=response
        )
        
        # Mettre à jour les suggestions
        ai_service.update_suggestions(query, response)
        
        serializer = self.get_serializer(search_query)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['GET'])
    def suggestions(self, request):
        """Retourne des suggestions basées sur l'historique"""
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return Response(
                {'suggestions': []},
                status=status.HTTP_200_OK
            )
        
        # Récupérer les suggestions correspondantes
        suggestions = AISearchSuggestion.objects.filter(
            query__icontains=query
        ).order_by('-frequency', '-last_used')[:5]
        
        serializer = AISearchSuggestionSerializer(suggestions, many=True)
        return Response({'suggestions': serializer.data})
    
    @action(detail=False, methods=['GET'])
    def history(self, request):
        """Retourne l'historique des recherches de l'utilisateur"""
        limit = min(int(request.query_params.get('limit', 20)), 50)
        
        searches = self.get_queryset()[:limit]
        serializer = self.get_serializer(searches, many=True)
        return Response(serializer.data)
