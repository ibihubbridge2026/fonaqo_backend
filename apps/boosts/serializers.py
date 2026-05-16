from rest_framework import serializers
from .models import BoostPlan, AgentBoost
from apps.accounts.serializers import UserSerializer


class BoostPlanSerializer(serializers.ModelSerializer):
    """Serializer pour les plans de boost"""
    duration_display = serializers.ReadOnlyField()
    
    class Meta:
        model = BoostPlan
        fields = [
            'id', 'name', 'duration_hours', 'duration_display',
            'price', 'description', 'visibility_multiplier',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AgentBoostSerializer(serializers.ModelSerializer):
    """Serializer pour les boosts d'agents"""
    plan = BoostPlanSerializer(read_only=True)
    plan_id = serializers.IntegerField(write_only=True, required=False)
    agent = UserSerializer(read_only=True)
    time_remaining_seconds = serializers.ReadOnlyField()
    time_remaining_display = serializers.ReadOnlyField()
    is_currently_active = serializers.ReadOnlyField()
    
    class Meta:
        model = AgentBoost
        fields = [
            'id', 'agent', 'plan', 'plan_id', 'started_at', 'expires_at',
            'status', 'purchase_amount', 'transaction_id',
            'time_remaining_seconds', 'time_remaining_display',
            'is_currently_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'agent', 'started_at', 'time_remaining_seconds',
            'time_remaining_display', 'is_currently_active',
            'created_at', 'updated_at'
        ]


class AgentBoostCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un boost (achat)"""
    
    class Meta:
        model = AgentBoost
        fields = [
            'plan', 'purchase_amount', 'transaction_id'
        ]
    
    def validate_plan(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Ce plan de boost n'est pas actif")
        return value
    
    def validate_purchase_amount(self, value):
        plan = self.initial_data.get('plan')
        if plan and float(value) != float(plan.price):
            raise serializers.ValidationError(
                f"Le montant doit correspondre au prix du plan: {plan.price} FCFA"
            )
        return value


class BoostCostCalculateSerializer(serializers.Serializer):
    """Serializer pour calculer le coût d'un boost"""
    plan_id = serializers.IntegerField()
    
    def validate_plan_id(self, value):
        try:
            plan = BoostPlan.objects.get(id=value, is_active=True)
            self.plan = plan
        except BoostPlan.DoesNotExist:
            raise serializers.ValidationError("Plan de boost invalide ou inactif")
        return value
