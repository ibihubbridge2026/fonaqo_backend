from rest_framework import serializers
from .models import Opportunity

class OpportunitySerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = Opportunity
        fields = [
            'id', 'title', 'description', 'category', 'category_display',
            'location', 'price_range', 'image_url', 'rating', 
            'is_open', 'is_urgent', 'provider_name', 'created_at'
        ]
        read_only_fields = ['created_at']
