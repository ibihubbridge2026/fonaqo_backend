from rest_framework import serializers

class AgentSearchResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    avatar_url = serializers.CharField()
    rating = serializers.FloatField()
    specialty = serializers.CharField()
    completed_missions = serializers.IntegerField()
    estimated_price = serializers.CharField()
    is_top_choice = serializers.BooleanField()

class MissionSearchResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    location = serializers.CharField()
    price = serializers.CharField()
    distance = serializers.CharField()
    type = serializers.CharField()
    is_urgent = serializers.BooleanField()

class SearchRequestSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=500)
