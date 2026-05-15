"""Diffusion temps réel sur le groupe WebSocket GPS d'une mission."""
import json
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def broadcast_gps_group(mission_id: str, message: dict) -> None:
    """Envoie un message JSON à tous les sockets du groupe `gps_<mission_id>`."""
    layer = get_channel_layer()
    if layer is None:
        logger.warning("Pas de channel layer : diffusion GPS ignorée.")
        return
    try:
        async_to_sync(layer.group_send)(
            f"gps_{mission_id}",
            {
                "type": "gps.client.push",
                "text": json.dumps(message),
            },
        )
    except Exception as exc:
        logger.exception("Échec diffusion GPS mission=%s : %s", mission_id, exc)
