from rest_framework import serializers

from .models import Dispute
from .resolution import DisputeResolutionService


class DisputeSerializer(serializers.ModelSerializer):
  evidence_file_url = serializers.SerializerMethodField()

  class Meta:
    model = Dispute
    fields = (
      'id', 'mission', 'opened_by', 'assigned_to', 'resolved_by',
      'title', 'description', 'status', 'priority',
      'evidence_file', 'evidence_file_url',
      'resolution_notes', 'refund_amount', 'penalty_amount',
      'resolved_at', 'created_at', 'updated_at',
    )
    read_only_fields = (
      'id', 'opened_by', 'resolved_by', 'resolved_at',
      'refund_amount', 'penalty_amount', 'created_at', 'updated_at',
    )

  def get_evidence_file_url(self, obj):
    if not obj.evidence_file:
      return None
    request = self.context.get('request')
    if request:
      return request.build_absolute_uri(obj.evidence_file.url)
    return obj.evidence_file.url


class DisputeCreateSerializer(serializers.ModelSerializer):
  class Meta:
    model = Dispute
    fields = ('mission', 'title', 'description', 'priority', 'evidence_file')

  def create(self, validated_data):
    validated_data['opened_by'] = self.context['request'].user
    return super().create(validated_data)


class DisputeResolveSerializer(serializers.Serializer):
  resolution_type = serializers.ChoiceField(
    choices=[
      DisputeResolutionService.REFUND_CLIENT,
      DisputeResolutionService.PAY_AGENT,
      DisputeResolutionService.ARBITRAGE_SPLIT,
    ],
  )
  notes = serializers.CharField(required=False, allow_blank=True, default='')
  client_percent = serializers.DecimalField(
    max_digits=5,
    decimal_places=2,
    required=False,
    allow_null=True,
  )
  agent_percent = serializers.DecimalField(
    max_digits=5,
    decimal_places=2,
    required=False,
    allow_null=True,
  )

  def validate(self, attrs):
    if attrs['resolution_type'] == DisputeResolutionService.ARBITRAGE_SPLIT:
      client_pct = attrs.get('client_percent')
      agent_pct = attrs.get('agent_percent')
      if client_pct is None or agent_pct is None:
        raise serializers.ValidationError(
          'client_percent et agent_percent sont requis pour ARBITRAGE_SPLIT.',
        )
    return attrs
