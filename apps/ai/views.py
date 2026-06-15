import json
import os
import re

from django.conf import settings as django_settings
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response


_MOKI_SYSTEM_PROMPT = """Tu es Moki, l'assistant IA de FONACO (conciergerie client/agent à Cotonou, Bénin).

Tu aides les clients sur :
- création de mission (onglet Missions → CRÉER, texte ou vocal),
- paiement (FeexPay ou portefeuille FONACO, minimum 500 FCFA prestation),
- annulation (20 % pour l'agent si mission acceptée/en cours),
- litiges (détail mission, réponse sous 24 h ouvrées),
- recherche d'agents (onglet Agents, favoris, profils).

Réponds en français, de façon concise et utile (3 à 6 phrases max).
Si la question concerne trouver un agent, une prestation ou un service (livraison, courses, queue, etc.),
indique-le clairement dans ta réponse.

Tu DOIS répondre UNIQUEMENT avec un JSON valide de la forme :
{
  "reply": "ta réponse en texte brut sans markdown",
  "suggest_agents": true ou false,
  "agent_search": {
    "mission_types": ["livraison", "courses", "autre"],
    "keywords": ["mot1", "mot2"],
    "location_hint": "ville ou quartier ou null"
  }
}

Règles agent_search :
- suggest_agents = true si l'utilisateur cherche un agent, un service ou une compétence.
- mission_types : sous-ensemble de ["livraison", "courses", "queue", "autre"] le plus pertinent.
- keywords : 2 à 5 mots-clés en minuscules.
- location_hint : extrait de la question ou null.
"""


def _fallback_reply(message: str) -> dict:
    q = message.lower()
    suggest = any(
        k in q
        for k in (
            'agent', 'livraison', 'course', 'queue', 'banque',
            'trouver', 'chercher', 'disponible', 'recommand',
        )
    )
    mission_types = []
    if 'livraison' in q or 'colis' in q:
        mission_types.append('livraison')
    if 'course' in q:
        mission_types.append('courses')
    if 'queue' in q or 'banque' in q:
        mission_types.append('queue')
    if not mission_types and suggest:
        mission_types.append('autre')

    if 'mission' in q or 'créer' in q:
        reply = (
            'Pour créer une mission : onglet Missions → CRÉER. '
            'Choisissez la catégorie, décrivez votre besoin (texte ou micro), '
            'puis indiquez la destination et le paiement.'
        )
    elif 'paiement' in q or 'wallet' in q or 'feex' in q:
        reply = (
            'Vous pouvez payer via FeexPay ou votre portefeuille FONACO. '
            'Le montant minimal de prestation est de 500 FCFA.'
        )
    elif 'annul' in q:
        reply = (
            "Une mission acceptée ou en cours peut être annulée avec un "
            'dédommagement obligatoire de 20 % pour l\'agent.'
        )
    elif 'litige' in q:
        reply = (
            'Ouvrez un litige depuis le détail d\'une mission en cours. '
            'Notre équipe revient vers vous sous 24 h ouvrées maximum.'
        )
    elif suggest:
        reply = (
            'Voici des agents susceptibles de correspondre à votre recherche. '
            'Consultez leur profil ou créez une mission pour les contacter.'
        )
    else:
        reply = (
            'Je suis Moki, votre assistant FONACO. Posez-moi une question sur '
            'les missions, les paiements, les agents ou les litiges.'
        )

    return {
        'reply': reply,
        'suggest_agents': suggest,
        'agent_search': {
            'mission_types': mission_types,
            'keywords': re.findall(r'[a-zàâäéèêëïîôùûüç]{3,}', q)[:5],
            'location_hint': None,
        },
    }


def _call_mistral(message: str, history: list | None) -> dict | None:
    mistral_api_key = os.environ.get('MISTRAL_API_KEY') or getattr(
        django_settings, 'MISTRAL_API_KEY', None
    )
    if not mistral_api_key:
        return None

    try:
        from mistralai import Mistral

        client = Mistral(api_key=mistral_api_key)
        messages = [{'role': 'system', 'content': _MOKI_SYSTEM_PROMPT}]
        for turn in history or []:
            role = turn.get('role')
            content = turn.get('content', '')
            if role in ('user', 'assistant') and content:
                messages.append({'role': role, 'content': content})
        messages.append({'role': 'user', 'content': message})

        response = client.chat.complete(
            model='mistral-small-latest',
            messages=messages,
            temperature=0.4,
            max_tokens=600,
            response_format={'type': 'json_object'},
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        if not isinstance(parsed, dict) or 'reply' not in parsed:
            return None
        agent_search = parsed.get('agent_search') or {}
        if not isinstance(agent_search, dict):
            agent_search = {}
        return {
            'reply': str(parsed.get('reply', '')).strip(),
            'suggest_agents': bool(parsed.get('suggest_agents')),
            'agent_search': {
                'mission_types': agent_search.get('mission_types') or [],
                'keywords': agent_search.get('keywords') or [],
                'location_hint': agent_search.get('location_hint'),
            },
        }
    except Exception:
        return None


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def assistant_chat(request):
    """Assistant Moki — réponse IA + paramètres de recherche agents."""
    message = (request.data.get('message') or '').strip()
    if not message:
        return Response(
            {'status': 'error', 'message': 'Le champ message est requis.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    history = request.data.get('history') or []
    if not isinstance(history, list):
        history = []

    payload = _call_mistral(message, history) or _fallback_reply(message)

    if not payload.get('reply'):
        payload = _fallback_reply(message)

    return Response({'status': 'success', 'data': payload})
