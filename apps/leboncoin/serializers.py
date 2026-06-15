from rest_framework import serializers

from .models import LocalListing


class LocalListingSerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    category_label = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = LocalListing
        fields = [
            'id', 'name', 'category', 'category_label', 'specialty', 'description',
            'address', 'city', 'district', 'latitude', 'longitude',
            'phone', 'email', 'website_url', 'photo_url', 'rating',
            'is_featured', 'opening_hours', 'tags',
        ]

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None

    def get_photo_url(self, obj):
        if not obj.photo:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.photo.url)
        return obj.photo.url
