from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework.response import Response
from .models import Opportunity
from .serializers import OpportunitySerializer

class OpportunityViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer les opportunités"""
    queryset = Opportunity.objects.all()
    serializer_class = OpportunitySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticatedOrReadOnly()]
    
    def get_queryset(self):
        queryset = Opportunity.objects.filter(is_open=True)
        
        # Filtre par catégorie
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        
        # Filtre urgent
        is_urgent = self.request.query_params.get('is_urgent', None)
        if is_urgent == 'true':
            queryset = queryset.filter(is_urgent=True)
        
        return queryset

@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
def opportunities_list(request):
    """Endpoint alternatif pour liste avec filtres"""
    queryset = Opportunity.objects.filter(is_open=True)
    
    category = request.query_params.get('category', None)
    if category:
        queryset = queryset.filter(category=category)
    
    serializer = OpportunitySerializer(queryset[:20], many=True)
    return Response(serializer.data)
