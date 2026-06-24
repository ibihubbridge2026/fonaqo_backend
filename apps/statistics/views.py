from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from .models import AgentStatistics
from .serializers import (
    AgentStatisticsSerializer, AgentPerformanceStatsSerializer,
    AgentWeeklyStatsSerializer, AgentMonthlyStatsSerializer,
    LeaderboardSerializer, AgentEarningsBreakdownSerializer,
    AgentStatsFilterSerializer
)


from apps.accounts.permissions import IsAgent


class AgentStatisticsViewSet(viewsets.ModelViewSet):
    """ViewSet pour les statistiques d'agent"""
    serializer_class = AgentStatisticsSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgent]
    
    def get_queryset(self):
        user = self.request.user
        return AgentStatistics.objects.filter(agent=user)
    
    @action(detail=False, methods=['get'])
    def performance_stats(self, request):
        """Statistiques de performance détaillées"""
        user = request.user
        if not hasattr(user, 'agentprofile'):
            return Response(
                {'error': 'Agent profile requis'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        agent = user.agentprofile
        from apps.missions.models import Mission
        
        # Calculer les stats de performance
        total_missions = Mission.objects.filter(assigned_agent=agent).count()
        completed_missions = Mission.objects.filter(
            assigned_agent=agent,
            status='completed'
        ).count()
        cancelled_missions = Mission.objects.filter(
            assigned_agent=agent,
            status='cancelled'
        ).count()
        
        total_earnings = Mission.objects.filter(
            assigned_agent=agent,
            status='completed'
        ).aggregate(total=Sum('price'))['total'] or 0
        
        average_earnings = (total_earnings / completed_missions) if completed_missions > 0 else 0
        
        total_disputes = Mission.objects.filter(
            assigned_agent=agent
        ).aggregate(count=Count('disputes'))['count'] or 0
        
        dispute_rate = (total_disputes / total_missions * 100) if total_missions > 0 else 0
        
        # Obtenir les stats détaillées
        stats, created = AgentStatistics.objects.get_or_create(agent=agent)
        
        # Calculer les missions pour le prochain niveau
        missions_to_next_level = 0
        rating_needed = 0
        current_level = stats.level
        
        if current_level == 'Newcomer':
            missions_to_next_level = 10 - completed_missions
            rating_needed = 4.0
        elif current_level == 'Bronze':
            missions_to_next_level = 50 - completed_missions
            rating_needed = 4.0
        elif current_level == 'Silver':
            missions_to_next_level = 200 - completed_missions
            rating_needed = 4.5
        elif current_level == 'Gold':
            missions_to_next_level = 500 - completed_missions
            rating_needed = 4.8
        
        performance_data = {
            'total_missions': total_missions,
            'completed_missions': completed_missions,
            'cancelled_missions': cancelled_missions,
            'completion_rate': stats.completion_rate,
            'total_earnings': total_earnings,
            'average_earnings_per_mission': average_earnings,
            'average_rating': stats.average_rating,
            'total_ratings': stats.total_ratings,
            'total_disputes': total_disputes,
            'dispute_rate': dispute_rate,
            'total_active_hours': stats.total_active_hours,
            'average_response_time': stats.average_response_time,
            'current_streak_days': stats.current_streak_days,
            'level': stats.level,
            'missions_to_next_level': max(0, missions_to_next_level),
            'rating_needed_for_next_level': rating_needed
        }
        
        serializer = AgentPerformanceStatsSerializer(performance_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def weekly_stats(self, request):
        """Statistiques hebdomadaires"""
        user = request.user
        if not hasattr(user, 'agentprofile'):
            return Response(
                {'error': 'Agent profile requis'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        agent = user.agentprofile
        from apps.missions.models import Mission
        
        # Calculer les stats de la semaine actuelle
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        # Semaine actuelle
        current_week_missions = Mission.objects.filter(
            assigned_agent=agent,
            updated_at__date__gte=week_start,
            updated_at__date__lte=week_end,
            status='completed'
        ).count()
        
        current_week_earnings = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date__gte=week_start,
            updated_at__date__lte=week_end
        ).aggregate(total=Sum('price'))['total'] or 0
        
        # Semaine précédente
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_end - timedelta(days=7)
        
        prev_week_missions = Mission.objects.filter(
            assigned_agent=agent,
            updated_at__date__gte=prev_week_start,
            updated_at__date__lte=prev_week_end,
            status='completed'
        ).count()
        
        prev_week_earnings = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date__gte=prev_week_start,
            updated_at__date__lte=prev_week_end
        ).aggregate(total=Sum('price'))['total'] or 0
        
        # Calculer les heures travaillées (estimation)
        hours_worked = current_week_missions * 2  # Estimation de 2h par mission
        
        # Obtenir la moyenne des notes de la semaine
        week_rating = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date__gte=week_start,
            updated_at__date__lte=week_end
        ).aggregate(avg=Avg('client_rating'))['avg'] or 0
        
        weekly_data = {
            'week_start': week_start,
            'week_end': week_end,
            'missions_completed': current_week_missions,
            'earnings': current_week_earnings,
            'hours_worked': hours_worked,
            'average_rating': week_rating,
            'missions_change': current_week_missions - prev_week_missions,
            'earnings_change': current_week_earnings - prev_week_earnings,
            'rating_change': week_rating - (Mission.objects.filter(
                assigned_agent=agent,
                status='completed',
                updated_at__date__gte=prev_week_start,
                updated_at__date__lte=prev_week_end
            ).aggregate(avg=Avg('client_rating'))['avg'] or 0)
        }
        
        serializer = AgentWeeklyStatsSerializer(weekly_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def monthly_stats(self, request):
        """Statistiques mensuelles"""
        user = request.user
        if not hasattr(user, 'agentprofile'):
            return Response(
                {'error': 'Agent profile requis'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        agent = user.agentprofile
        from apps.missions.models import Mission
        
        # Obtenir le mois et l'année (par défaut le mois actuel)
        month = int(request.query_params.get('month', timezone.now().month))
        year = int(request.query_params.get('year', timezone.now().year))
        
        month_start = timezone.datetime(year, month, 1).date()
        if month == 12:
            month_end = timezone.datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            month_end = timezone.datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        # Stats du mois
        month_missions = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date__gte=month_start,
            updated_at__date__lte=month_end
        ).count()
        
        month_earnings = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date__gte=month_start,
            updated_at__date__lte=month_end
        ).aggregate(total=Sum('price'))['total'] or 0
        
        hours_worked = month_missions * 2  # Estimation
        
        month_rating = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date__gte=month_start,
            updated_at__date__lte=month_end
        ).aggregate(avg=Avg('client_rating'))['avg'] or 0
        
        # Répartition par catégorie
        missions_by_category = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date__gte=month_start,
            updated_at__date__lte=month_end
        ).values('service_type').annotate(count=Count('id')).order_by('-count')
        
        category_dict = {item['service_type']: item['count'] for item in missions_by_category}
        
        # Meilleur jour
        best_day = Mission.objects.filter(
            assigned_agent=agent,
            status='completed',
            updated_at__date__gte=month_start,
            updated_at__date__lte=month_end
        ).values('updated_at__date').annotate(
            missions=Count('id'),
            earnings=Sum('price')
        ).order_by('-earnings').first()
        
        monthly_data = {
            'month': month,
            'year': year,
            'missions_completed': month_missions,
            'earnings': month_earnings,
            'hours_worked': hours_worked,
            'average_rating': month_rating,
            'missions_by_category': category_dict,
            'best_day_earnings': best_day['earnings'] if best_day else 0,
            'best_day_missions': best_day['missions'] if best_day else 0
        }
        
        serializer = AgentMonthlyStatsSerializer(monthly_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """Classement des agents"""
        from apps.accounts.models import AgentProfile
        
        # Obtenir les agents les plus performants
        agents = AgentProfile.objects.filter(
            is_verified=True
        ).annotate(
            completed_missions=Count('missions', filter=Q(missions__status='completed')),
            total_earnings=Sum('missions__price', filter=Q(missions__status='completed'))
        ).order_by('-total_earnings')[:20]
        
        leaderboard_data = []
        current_user_rank = None
        
        for rank, agent in enumerate(agents, 1):
            agent_stats, created = AgentStatistics.objects.get_or_create(agent=agent)
            
            is_current_user = (request.user == agent.user)
            if is_current_user:
                current_user_rank = rank
            
            leaderboard_data.append({
                'rank': rank,
                'agent_id': agent.id,
                'agent_name': f"{agent.user.first_name} {agent.user.last_name}",
                'agent_avatar': agent.profile_picture.url if agent.profile_picture else None,
                'completed_missions': agent_stats.completed_missions,
                'total_earnings': agent_stats.total_earnings,
                'average_rating': agent_stats.average_rating,
                'completion_rate': agent_stats.completion_rate,
                'level': agent_stats.level,
                'is_current_user': is_current_user
            })
        
        return Response({
            'leaderboard': LeaderboardSerializer(leaderboard_data, many=True).data,
            'current_user_rank': current_user_rank
        })
    
    @action(detail=False, methods=['get'])
    def earnings_breakdown(self, request):
        """Répartition des revenus"""
        user = request.user
        if not hasattr(user, 'agentprofile'):
            return Response(
                {'error': 'Agent profile requis'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        agent = user.agentprofile
        from apps.missions.models import Mission
        
        period = request.query_params.get('period', 'month')
        
        # Définir la période
        if period == 'today':
            start_date = timezone.now().date()
        elif period == 'week':
            start_date = timezone.now().date() - timedelta(days=7)
        elif period == 'month':
            start_date = timezone.now().date().replace(day=1)
        elif period == 'year':
            start_date = timezone.now().date().replace(month=1, day=1)
        else:  # all
            start_date = None
        
        # Calculer les revenus
        missions_filter = {'assigned_agent': agent, 'status': 'completed'}
        if start_date:
            missions_filter['updated_at__date__gte'] = start_date
        
        total_earnings = Mission.objects.filter(**missions_filter).aggregate(
            total=Sum('price')
        )['total'] or 0
        
        # Répartition par catégorie
        earnings_by_category = Mission.objects.filter(**missions_filter).values(
            'service_type'
        ).annotate(
            total=Sum('price')
        ).order_by('-total')
        
        category_dict = {item['service_type']: item['total'] for item in earnings_by_category}
        
        # Moyenne quotidienne
        days_count = (timezone.now().date() - start_date).days + 1 if start_date else 365
        daily_average = total_earnings / days_count if days_count > 0 else 0
        
        # Projection mensuelle
        projected_monthly = daily_average * 30
        
        earnings_data = {
            'period': period,
            'total_earnings': total_earnings,
            'mission_earnings': total_earnings,  # Pour l'instant tout vient des missions
            'bonus_earnings': 0,
            'tip_earnings': 0,
            'earnings_by_category': category_dict,
            'daily_average': daily_average,
            'projected_monthly': projected_monthly
        }
        
        serializer = AgentEarningsBreakdownSerializer(earnings_data)
        return Response(serializer.data)
