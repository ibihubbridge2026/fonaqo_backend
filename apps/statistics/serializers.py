from rest_framework import serializers
from .models import AgentStatistics
from apps.accounts.serializers import UserSerializer
from django.db.models import Count, Sum, Avg, Q
from datetime import datetime, timedelta
from django.utils import timezone


class AgentStatisticsSerializer(serializers.ModelSerializer):
    """Serializer pour les statistiques d'agent"""
    agent = UserSerializer(read_only=True)
    success_rate = serializers.ReadOnlyField()
    level = serializers.ReadOnlyField()
    
    class Meta:
        model = AgentStatistics
        fields = [
            'id', 'agent',
            'total_missions', 'completed_missions', 'cancelled_missions',
            'total_earnings', 'current_month_earnings',
            'average_rating', 'total_ratings',
            'completion_rate', 'average_response_time',
            'total_active_hours', 'total_disputes', 'resolved_disputes',
            'current_streak_days', 'longest_streak_days',
            'success_rate', 'level',
            'last_updated', 'last_mission_date'
        ]
        read_only_fields = [
            'agent', 'last_updated', 'success_rate', 'level'
        ]


class AgentPerformanceStatsSerializer(serializers.Serializer):
    """Serializer pour les stats de performance d'agent"""
    # Performance globale
    total_missions = serializers.IntegerField()
    completed_missions = serializers.IntegerField()
    cancelled_missions = serializers.IntegerField()
    completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Revenus
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_earnings_per_mission = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # Qualité
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    total_ratings = serializers.IntegerField()
    total_disputes = serializers.IntegerField()
    dispute_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Activité
    total_active_hours = serializers.DecimalField(max_digits=8, decimal_places=2)
    average_response_time = serializers.IntegerField()
    current_streak_days = serializers.IntegerField()
    
    # Niveau et progression
    level = serializers.CharField()
    missions_to_next_level = serializers.IntegerField()
    rating_needed_for_next_level = serializers.DecimalField(max_digits=3, decimal_places=2)


class AgentWeeklyStatsSerializer(serializers.Serializer):
    """Serializer pour les stats hebdomadaires"""
    week_start = serializers.DateField()
    week_end = serializers.DateField()
    
    # Stats de la semaine
    missions_completed = serializers.IntegerField()
    earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    hours_worked = serializers.DecimalField(max_digits=6, decimal_places=2)
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    
    # Comparaison avec semaine précédente
    missions_change = serializers.IntegerField()
    earnings_change = serializers.DecimalField(max_digits=10, decimal_places=2)
    rating_change = serializers.DecimalField(max_digits=3, decimal_places=2)


class AgentMonthlyStatsSerializer(serializers.Serializer):
    """Serializer pour les stats mensuelles"""
    month = serializers.IntegerField()
    year = serializers.IntegerField()
    
    # Stats du mois
    missions_completed = serializers.IntegerField()
    earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    hours_worked = serializers.DecimalField(max_digits=6, decimal_places=2)
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    
    # Répartition par type de mission
    missions_by_category = serializers.DictField()
    
    # Top performances
    best_day_earnings = serializers.DecimalField(max_digits=8, decimal_places=2)
    best_day_missions = serializers.IntegerField()


class LeaderboardSerializer(serializers.Serializer):
    """Serializer pour le classement des agents"""
    rank = serializers.IntegerField()
    agent_id = serializers.IntegerField()
    agent_name = serializers.CharField()
    agent_avatar = serializers.URLField()
    
    # Stats de performance
    completed_missions = serializers.IntegerField()
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Badge de niveau
    level = serializers.CharField()
    is_current_user = serializers.BooleanField()


class AgentEarningsBreakdownSerializer(serializers.Serializer):
    """Serializer pour la répartition des revenus"""
    period = serializers.CharField()  # 'today', 'week', 'month', 'year'
    
    # Revenus totaux
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    # Répartition par source
    mission_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    bonus_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    tip_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    # Répartition par catégorie
    earnings_by_category = serializers.DictField()
    
    # Tendances
    daily_average = serializers.DecimalField(max_digits=10, decimal_places=2)
    projected_monthly = serializers.DecimalField(max_digits=12, decimal_places=2)


class AgentStatsUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour mettre à jour les stats d'agent (cron)"""
    
    class Meta:
        model = AgentStatistics
        fields = [
            'total_missions', 'completed_missions', 'cancelled_missions',
            'total_earnings', 'current_month_earnings',
            'average_rating', 'total_ratings',
            'completion_rate', 'average_response_time',
            'total_active_hours', 'total_disputes', 'resolved_disputes',
            'current_streak_days', 'longest_streak_days',
            'last_mission_date'
        ]


class AgentStatsFilterSerializer(serializers.Serializer):
    """Serializer pour filtrer les stats"""
    period = serializers.ChoiceField(
        choices=['today', 'week', 'month', 'year', 'all'],
        default='month'
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    category = serializers.CharField(required=False)
    
    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                "La date de début doit être antérieure à la date de fin"
            )
        
        return data
