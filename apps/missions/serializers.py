import logging

from django.contrib.gis.geos import Point
from django.contrib.humanize.templatetags.humanize import naturaltime
from rest_framework import serializers

from .models import Mission, MissionTimeline, Tag

logger = logging.getLogger(__name__)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("name", "slug")


class MissionTimelineSerializer(serializers.ModelSerializer):
    """Historique des étapes (lecture seule)."""

    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    time_ago = serializers.SerializerMethodField()
    author_name = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = MissionTimeline
        fields = (
            "status",
            "status_display",
            "message",
            "time_ago",
            "author_name",
            "created_at",
        )

    def get_time_ago(self, obj):
        return naturaltime(obj.created_at)


class MissionSerializer(serializers.ModelSerializer):
    """
    Représentation plate pour Flutter (latitude / longitude en doubles),
    sans GeoJSON FeatureCollection.
    """

    latitude = serializers.FloatField(write_only=True, required=False)
    longitude = serializers.FloatField(write_only=True, required=False)

    client_phone = serializers.ReadOnlyField(source="client.phone_number")
    agent_name = serializers.ReadOnlyField(source="agent.username")
    agent_phone = serializers.ReadOnlyField(source="agent.phone_number")

    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    tags = TagSerializer(many=True, read_only=True)
    timeline = MissionTimelineSerializer(many=True, read_only=True)
    distance = serializers.SerializerMethodField()

    end_photo = serializers.ImageField(required=False, allow_null=True)
    start_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Mission
        fields = (
            "id",
            "client",
            "client_phone",
            "agent",
            "agent_name",
            "agent_phone",
            "title",
            "description",
            "price",
            "service_fee",
            "status",
            "status_display",
            "address",
            "requires_procuration",
            "target_agent_username",
            "qr_code_token",
            "start_photo",
            "end_photo",
            "tags",
            "timeline",
            "distance",
            "created_at",
            "updated_at",
            "latitude",
            "longitude",
        )
        read_only_fields = (
            "id",
            "status",
            "qr_code_token",
            "agent",
            "client",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            'requires_procuration': {'default': False}
        }

    def get_distance(self, obj):
        if hasattr(obj, "distance"):
            dist = obj.distance.m
            if dist > 1000:
                return f"{round(dist / 1000, 1)} km"
            return f"{int(dist)} m"
        return None

    def create(self, validated_data):
        lat = validated_data.pop("latitude", None)
        lng = validated_data.pop("longitude", None)
        if lat is None or lng is None:
            raise serializers.ValidationError(
                {"latitude": "Requis", "longitude": "Requis"}
            )
        validated_data["location"] = Point(float(lng), float(lat), srid=4326)
        mission = super().create(validated_data)
        logger.info("Mission créée id=%s", mission.id)
        return mission

    def update(self, instance, validated_data):
        lat = validated_data.pop("latitude", None)
        lng = validated_data.pop("longitude", None)
        if lat is not None and lng is not None:
            validated_data["location"] = Point(float(lng), float(lat), srid=4326)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        if instance.location:
            data["latitude"] = instance.location.y
            data["longitude"] = instance.location.x
        else:
            data["latitude"] = None
            data["longitude"] = None
        data["client_name"] = (
            instance.client.username if instance.client_id else None
        )
        data["agent_name"] = (
            instance.agent.username if instance.agent_id else None
        )
        data.pop("client", None)
        data.pop("agent", None)
        return data
