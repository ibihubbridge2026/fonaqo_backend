from rest_framework import permissions

class IsVerifiedAgent(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur est un agent ET s'il est vérifié par l'admin.
    """
    message = "Votre compte n'est pas encore vérifié. Veuillez compléter votre KYC."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_agent and 
            request.user.is_verified
        )