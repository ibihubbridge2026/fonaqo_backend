"""
Utilitaires pour la vulgarisation des messages techniques
Convertit les messages d'erreur techniques en messages lisibles par l'équipe support
"""

def get_human_readable_message(technical_message: str) -> str:
    """
    Convertit un message technique en message lisible par un humain
    
    Args:
        technical_message: Le message technique brut
        
    Returns:
        Le message vulgarisé pour l'équipe support
    """
    if not technical_message:
        return technical_message
    
    message_lower = technical_message.lower()
    
    # Conversion des erreurs WebSocket
    if 'websocketexception' in message_lower or 'was not upgraded' in message_lower:
        return "Échec de synchronisation en temps réel : Problème de protocole réseau"
    
    # Conversion des erreurs HTTP 406
    if 'statuscode=406' in message_lower or 'status code 406' in message_lower:
        return "Erreur de format : L'appareil de l'utilisateur a rejeté le format du relevé mensuel"
    
    # Conversion des erreurs JWT expirées
    if 'jwt expired' in message_lower or 'signature has expired' in message_lower:
        return "Session expirée : L'utilisateur a été déconnecté automatiquement par sécurité"
    
    # Conversion des erreurs de connexion refusée
    if 'connection refused' in message_lower:
        return "Réseau interrompu : Impossible de joindre le serveur distant"
    
    # Conversion des erreurs de timeout
    if 'timeout' in message_lower or 'timed out' in message_lower:
        return "Délai d'attente dépassé : Le serveur n'a pas répondu dans le temps imparti"
    
    # Conversion des erreurs de permission
    if 'permission denied' in message_lower or 'forbidden' in message_lower or '403' in message_lower:
        return "Accès refusé : L'utilisateur n'a pas les droits nécessaires pour cette action"
    
    # Conversion des erreurs 404
    if 'not found' in message_lower or '404' in message_lower:
        return "Ressource introuvable : L'élément demandé n'existe pas ou a été supprimé"
    
    # Conversion des erreurs de validation
    if 'validation error' in message_lower or 'invalid' in message_lower:
        return "Données invalides : Les informations fournies ne respectent pas le format attendu"
    
    # Conversion des erreurs de base de données
    if 'database error' in message_lower or 'integrity error' in message_lower:
        return "Erreur de base de données : Impossible d'enregistrer les informations"
    
    # Conversion des erreurs de paiement
    if 'payment failed' in message_lower or 'transaction failed' in message_lower:
        return "Échec de transaction : Le paiement n'a pas pu être traité"
    
    # Si aucun motif n'est reconnu, retourner le message original
    return technical_message


def format_notification_message(title: str, message: str) -> dict:
    """
    Formate un message de notification pour l'affichage dans le SuperAdmin
    
    Args:
        title: Le titre de la notification
        message: Le message technique brut
        
    Returns:
        Un dictionnaire avec le message vulgarisé
    """
    return {
        'title': title,
        'message': get_human_readable_message(message),
        'original_message': message  # Garder l'original pour le débogage
    }
