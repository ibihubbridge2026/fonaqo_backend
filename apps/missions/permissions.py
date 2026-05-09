from rest_framework import permissions

class IsVerifiedAgent(permissions.BasePermission):
    """L'utilisateur doit être un agent avec KYC validé"""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'AGENT' and 
            request.user.kyc_status == 'VERIFIED'
        )

class IsMissionClient(permissions.BasePermission):
    """L'utilisateur doit être le client qui a créé la mission"""
    def has_object_permission(self, request, view, obj):
        return obj.client == request.user

class MissionAccessControl(permissions.BasePermission):
    """Contrôle d'accès granulaire aux données sensibles"""
    def has_object_permission(self, request, view, obj):
        # Si c'est le client de la mission, il voit tout
        if obj.client == request.user:
            return True
        
        # Si c'est l'agent assigné, il voit tout
        if obj.agent == request.user:
            return True
            
        # Sinon (agent qui regarde juste la liste), on masque les infos sensibles
        # Cette logique sera appliquée dans le Serializer
        return False