from .models import AdminAuditLog


def log_admin_action(admin, action: str, *, target_type: str = '', target_id: str = '',
                     detail: str = '', metadata: dict | None = None) -> AdminAuditLog:
    """Enregistre une action staff pour le journal d'audit."""
    return AdminAuditLog.objects.create(
        admin=admin if getattr(admin, 'is_authenticated', False) else None,
        action=action,
        target_type=target_type or '',
        target_id=str(target_id) if target_id else '',
        detail=detail or '',
        metadata=metadata or {},
    )
