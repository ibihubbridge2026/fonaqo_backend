from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.db.models import Q

from .models import LocalListing
from .serializers import LocalListingSerializer


class LocalListingViewSet(viewsets.ReadOnlyModelViewSet):
    """Annuaire public LeBonCoin — lecture seule côté app mobile."""

    serializer_class = LocalListingSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'pk'

    def get_queryset(self):
        qs = LocalListing.objects.filter(is_active=True)

        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)

        query = (self.request.query_params.get('query') or '').strip()
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(specialty__icontains=query)
                | Q(description__icontains=query)
                | Q(district__icontains=query)
                | Q(city__icontains=query)
            )

        city = (self.request.query_params.get('city') or '').strip()
        if city:
            qs = qs.filter(city__icontains=city)

        lat = self.request.query_params.get('latitude')
        lng = self.request.query_params.get('longitude')
        radius_m = self.request.query_params.get('radius')
        if lat and lng:
            try:
                user_point = Point(float(lng), float(lat), srid=4326)
                qs = qs.filter(location__isnull=False).annotate(
                    distance=Distance('location', user_point),
                )
                if radius_m:
                    qs = qs.filter(distance__lte=float(radius_m)).order_by('distance')
            except (TypeError, ValueError):
                pass

        featured = self.request.query_params.get('featured')
        if featured in ('true', '1', 'yes'):
            qs = qs.filter(is_featured=True)

        return qs

    @action(detail=False, methods=['get'])
    def map(self, request):
        """Liste légère pour affichage carte (id, coords, nom, catégorie)."""
        listings = self.filter_queryset(self.get_queryset())
        data = [
            {
                'id': str(item.id),
                'name': item.name,
                'category': item.category,
                'latitude': item.location.y if item.location else None,
                'longitude': item.location.x if item.location else None,
                'is_featured': item.is_featured,
            }
            for item in listings[:500]
        ]
        return Response({'results': data, 'count': len(data)})

    @action(detail=False, methods=['get'])
    def categories(self, request):
        return Response({
            'results': [
                {'value': value, 'label': label}
                for value, label in LocalListing.Category.choices
            ],
        })
