from rest_framework import permissions

class IsAgent(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur est un agent.
    """
    message = "Cette action est réservée aux agents."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_agent
        )


class IsClient(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur est un client.
    """
    message = "Cette action est réservée aux clients."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_client
        )


class IsAdmin(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur est un administrateur staff.
    """
    message = "Cette action est réservée aux administrateurs."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_staff
        )


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