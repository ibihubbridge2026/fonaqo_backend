from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.http import JsonResponse
from rest_framework import status
from .models import Category


@api_view(['GET'])
@permission_classes([AllowAny])
def categories_list(request):
    """
    Retourne la liste des catégories de services disponibles
    """
    try:
        categories = Category.objects.all()
        categories_data = []
        
        for category in categories:
            categories_data.append({
                'id': category.id,
                'name': category.name,
                'icon': category.icon.url if category.icon else None,
                'keywords': category.keywords
            })
        
        return JsonResponse({
            'status': 'success',
            'message': 'Catégories récupérées avec succès',
            'data': categories_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Erreur lors de la récupération des catégories: {str(e)}',
            'data': []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)