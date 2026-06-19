from django.shortcuts import redirect


class StaffDashboardRedirectMiddleware:
    """
    Redirige automatiquement les utilisateurs staff/superuser vers le dashboard
    SuperAdmin après connexion session ou accès à la racine admin.
    """

    STAFF_PREFIXES = (
        '/admin-dashboard/',
        '/admin-portal/',
    )
    EXEMPT_PREFIXES = (
        '/admin/',
        '/api/',
        '/health/',
        '/static/',
        '/media/',
        '/track/',
        '/api/schema/',
        '/api/docs/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated:
            return self.get_response(request)

        if not (user.is_staff or user.is_superuser):
            return self.get_response(request)

        if path in ('/', '/login/', '/accounts/login/'):
            return redirect('/admin-dashboard/')

        if path.startswith('/admin-portal') and path not in (
            '/admin-portal/login/',
            '/admin-portal/logout/',
        ):
            if path.rstrip('/') in ('/admin-portal', '/admin-portal/'):
                return redirect('/admin-dashboard/')

        return self.get_response(request)
