from django.contrib import admin

from .models import LocalListing


@admin.register(LocalListing)
class LocalListingAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'city', 'district', 'is_featured', 'is_active', 'rating')
    list_filter = ('category', 'is_featured', 'is_active', 'city')
    search_fields = ('name', 'specialty', 'district', 'city', 'phone')
    readonly_fields = ('created_at', 'updated_at')
