"""Payload public de suivi mission — partagé vitrine / API."""

from datetime import timedelta

from django.utils import timezone


def build_mission_track_payload(mission, request=None):
    from apps.missions.models import MissionTimelineEvent

    status_steps = [
        ('PENDING', 'Demande reçue', 'inbox'),
        ('ACCEPTED', 'Agent assigné', 'person_check'),
        ('ON_THE_WAY', 'En route', 'directions_car'),
        ('ARRIVED', 'Arrivé sur place', 'location_on'),
        ('IN_PROGRESS', 'Travaux en cours', 'construction'),
        ('IN_PROGRESS_REVIEW', 'Preuve soumise — validation', 'fact_check'),
        ('COMPLETED', 'Mission terminée', 'check_circle'),
    ]
    status_order = [s[0] for s in status_steps]
    current_idx = status_order.index(mission.status) if mission.status in status_order else -1

    events = MissionTimelineEvent.objects.filter(mission=mission).order_by('occurred_at')
    event_type_to_status = {
        'created': 'PENDING',
        'accepted': 'ACCEPTED',
        'agent_en_route': 'ON_THE_WAY',
        'agent_arrived': 'ARRIVED',
        'in_progress': 'IN_PROGRESS',
        'proofs_uploaded': 'IN_PROGRESS_REVIEW',
        'completed': 'COMPLETED',
        'validated': 'COMPLETED',
    }
    event_map = {}
    for event in events:
        code = event_type_to_status.get(event.event_type)
        if code:
            event_map[code] = event.occurred_at

    timeline = []
    for idx, (code, label, icon) in enumerate(status_steps):
        ts = event_map.get(code) or (mission.created_at if code == 'PENDING' else None)
        if code == 'ACCEPTED' and mission.agent_id and not ts:
            ts = mission.updated_at
        state = 'done' if idx < current_idx else ('current' if idx == current_idx else 'upcoming')
        if mission.status == 'CANCELLED' and code == 'COMPLETED':
            state = 'upcoming'
        timeline.append({
            'code': code,
            'label': label,
            'icon': icon,
            'state': state,
            'timestamp': ts.isoformat() if ts else None,
        })

    pending_alert = False
    if mission.status == 'PENDING' and not mission.agent_id:
        pending_alert = (timezone.now() - mission.created_at) >= timedelta(minutes=5)

    labor = mission.labor_cost or mission.service_amount or mission.price
    material = mission.material_cost or mission.purchase_amount
    escrow_status = None
    escrow_amount = None
    if hasattr(mission, 'escrow'):
        escrow_status = mission.escrow.status
        escrow_amount = float(mission.escrow.amount)

    agent_contact = None
    if mission.agent_id:
        agent = mission.agent
        first_name = (agent.first_name or '').strip() or agent.username
        skills = (agent.service_domain or '').strip()
        if not skills:
            try:
                skills = ', '.join(
                    agent.offered_services.filter(is_active=True).values_list(
                        'title', flat=True,
                    )[:5],
                )
            except Exception:
                pass
        agent_contact = {
            'first_name': first_name,
            'username': agent.username,
            'skills': skills or 'Agent FONACO',
            'phone': agent.phone_number,
            'phone_display': agent.phone_number,
        }

    proof_photo_url = None
    if mission.status in ('IN_PROGRESS_REVIEW', 'COMPLETED'):
        proof = mission.proofs.filter(is_primary=True).first()
        if not proof:
            proof = mission.proofs.order_by('-created_at').first()
        if proof and proof.image:
            if request:
                proof_photo_url = request.build_absolute_uri(proof.image.url)
            else:
                proof_photo_url = proof.image.url
        elif mission.end_photo:
            if request:
                proof_photo_url = request.build_absolute_uri(mission.end_photo.url)
            else:
                proof_photo_url = mission.end_photo.url

    return {
        'id': str(mission.id),
        'tracking_code': mission.tracking_code or '',
        'short_ref': (mission.tracking_code or str(mission.id)[:8]).upper(),
        'title': mission.title,
        'description': mission.description,
        'address': mission.address,
        'status': mission.status,
        'status_label': mission.get_status_display(),
        'budget_total': float((labor or 0) + (material or 0) + (mission.service_fee or 0)),
        'labor_cost': float(labor or 0),
        'material_cost': float(material or 0),
        'escrow_status': escrow_status,
        'escrow_amount': escrow_amount,
        'pending_unassigned_alert': pending_alert,
        'timeline': timeline,
        'agent': agent_contact,
        'proof_photo_url': proof_photo_url,
        'created_at': mission.created_at.isoformat(),
    }


def resolve_mission_by_reference(reference: str):
    from apps.missions.models import Mission

    ref = (reference or '').strip().replace('#', '').upper()
    if len(ref) < 4:
        return None

    mission = Mission.objects.filter(tracking_code__iexact=ref).first()
    if mission:
        return mission
    if len(ref) >= 32:
        mission = Mission.objects.filter(id=ref).first()
        if mission:
            return mission
    return Mission.objects.filter(id__istartswith=ref).first()
