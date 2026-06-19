"""Badges de progression agent (gamification)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentBadge:
    tier: str
    label: str
    min_missions: int
    color_hex: str


BADGE_TIERS: tuple[AgentBadge, ...] = (
    AgentBadge('legend', 'Ambassadeur', 1000, '#6C3BFF'),
    AgentBadge('sapphire', 'Maître Artisan', 500, '#0EA5E9'),
    AgentBadge('platinum', 'Élite FONACO', 300, '#64748B'),
    AgentBadge('gold', 'Expert Certifié', 100, '#EAB308'),
    AgentBadge('silver', 'Agent Vétéran', 50, '#94A3B8'),
    AgentBadge('bronze', 'Débutant de confiance', 20, '#CD7F32'),
)


def compute_agent_badge(completed_count: int) -> dict | None:
    """Retourne le badge le plus élevé atteint, ou None si < 20 missions."""
    for badge in BADGE_TIERS:
        if completed_count >= badge.min_missions:
            return {
                'tier': badge.tier,
                'label': badge.label,
                'min_missions': badge.min_missions,
                'color': badge.color_hex,
                'completed_missions': completed_count,
            }
    return None
