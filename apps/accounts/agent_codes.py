"""Génération séquentielle des identifiants agents AGT-00001."""

from __future__ import annotations

import re

from django.db import transaction

_AGENT_CODE_RE = re.compile(r'^AGT-(\d+)$')


def allocate_agent_code() -> str:
    """Alloue le prochain code agent unique (transactionnel)."""
    from apps.accounts.models import AgentProfile

    with transaction.atomic():
        max_num = 0
        for code in AgentProfile.objects.select_for_update().exclude(
            agent_code='',
        ).values_list('agent_code', flat=True):
            match = _AGENT_CODE_RE.match(code or '')
            if match:
                max_num = max(max_num, int(match.group(1)))
        return f'AGT-{max_num + 1:05d}'


def ensure_agent_code(profile) -> str:
    """Assigne un code agent au profil s'il n'en a pas encore."""
    if profile.agent_code:
        return profile.agent_code
    code = allocate_agent_code()
    profile.agent_code = code
    profile.save(update_fields=['agent_code', 'updated_at'])
    return code
