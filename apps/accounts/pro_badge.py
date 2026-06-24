"""Génération PDF du badge professionnel agent FONACO."""

from __future__ import annotations

import io
from datetime import datetime

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _public_agent_url(user) -> str:
    base = getattr(settings, 'SITE_BASE_URL', 'http://localhost:8000').rstrip('/')
    return f'{base}/vitrine/agent/{user.pk}/'


def _draw_rounded_rect(c, x, y, w, h, r, fill=1, stroke=0):
    c.roundRect(x, y, w, h, r, fill=fill, stroke=stroke)


def build_agent_pro_badge_pdf(user, profile) -> bytes:
    """Construit le PDF du badge professionnel (format carte horizontale)."""
    width, height = landscape((85.6 * mm, 54 * mm))
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setTitle(f'Badge FONACO — {profile.agent_code or user.username}')

    yellow = colors.HexColor('#FFD100')
    orange = colors.HexColor('#C45A00')
    dark = colors.HexColor('#1A1A1A')

    # Sidebar jaune
    sidebar_w = 22 * mm
    _draw_rounded_rect(c, 0, 0, sidebar_w, height, 4 * mm, fill=1, stroke=0)
    c.setFillColor(yellow)
    c.rect(0, 0, sidebar_w, height, fill=1, stroke=0)

    c.setFillColor(dark)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(3 * mm, height - 14 * mm, 'FONACO')
    c.setFont('Helvetica', 5.5)
    c.drawString(3 * mm, height - 18 * mm, 'TA MISSION,')
    c.drawString(3 * mm, height - 21 * mm, 'NOTRE ACTION.')

    # Zone blanche principale
    c.setFillColor(colors.white)
    c.rect(sidebar_w, 0, width - sidebar_w, height, fill=1, stroke=0)

    content_x = sidebar_w + 4 * mm
    top_y = height - 8 * mm

    # Badge certifié si agent interne — bandeau séparé du nom
    name_y = top_y - 2 * mm
    if profile.is_internal:
        c.setFillColor(yellow)
        _draw_rounded_rect(c, width - 48 * mm, top_y - 2 * mm, 44 * mm, 7 * mm, 3 * mm)
        c.setFillColor(dark)
        c.setFont('Helvetica-Bold', 7)
        c.drawCentredString(width - 26 * mm, top_y + 0.5 * mm, 'AGENT CERTIFIÉ ★')
        name_y = top_y - 12 * mm

    # Nom agent (sous le bandeau certifié le cas échéant)
    full_name = (user.get_full_name() or user.username).upper()
    if len(full_name) > 22:
        full_name = full_name[:20] + '…'
    c.setFillColor(dark)
    c.setFont('Helvetica-Bold', 13)
    c.drawString(content_x + 18 * mm, name_y, full_name)

    # Rôle / catégorie
    specialty = user.service_domain or user.expertises or 'Agent terrain'
    if len(specialty) > 40:
        specialty = specialty[:38] + '…'
    c.setFillColor(orange)
    c.setFont('Helvetica', 7.5)
    c.drawString(content_x + 18 * mm, name_y - 6 * mm, f'Agent — {specialty}')

    # Photo placeholder (cercle jaune)
    photo_x = content_x
    photo_y = top_y - 22 * mm
    c.setStrokeColor(yellow)
    c.setLineWidth(1.5)
    c.circle(photo_x + 8 * mm, photo_y + 8 * mm, 8 * mm, fill=0, stroke=1)
    photo = profile.badge_photo or profile.selfie_photo
    if photo:
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(photo.path)
            c.drawImage(
                img,
                photo_x,
                photo_y,
                16 * mm,
                16 * mm,
                mask='auto',
            )
        except Exception:
            c.setFillColor(colors.HexColor('#E5E5E5'))
            c.circle(photo_x + 8 * mm, photo_y + 8 * mm, 7 * mm, fill=1, stroke=0)
    else:
        c.setFillColor(colors.HexColor('#E5E5E5'))
        c.circle(photo_x + 8 * mm, photo_y + 8 * mm, 7 * mm, fill=1, stroke=0)

    # Infos
    info_y = top_y - 14 * mm
    c.setFillColor(orange)
    c.setFont('Helvetica', 6.5)
    agent_id = profile.agent_code or f'AGT-{str(user.pk)[:5]}'
    phone = user.phone_number or '—'
    zone = ' — '.join(filter(None, [user.city, user.address])) or '—'
    joined = user.date_joined.strftime('%m/%Y') if user.date_joined else '—'

    for line in (
        f'ID : {agent_id}',
        f'Téléphone : {phone}',
        f'Zone : {zone}',
        f'Inscrit depuis : {joined}',
    ):
        c.drawString(content_x + 18 * mm, info_y, line)
        info_y -= 4 * mm

    # QR code (via qrcode lib si dispo, sinon placeholder)
    qr_url = _public_agent_url(user)
    qr_size = 16 * mm
    qr_x = width - qr_size - 5 * mm
    qr_y = 6 * mm
    try:
        import qrcode
        qr_img = qrcode.make(qr_url)
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format='PNG')
        qr_buf.seek(0)
        from reportlab.lib.utils import ImageReader
        c.setStrokeColor(yellow)
        c.setLineWidth(2)
        c.rect(qr_x - 1 * mm, qr_y - 1 * mm, qr_size + 2 * mm, qr_size + 2 * mm, fill=0, stroke=1)
        c.drawImage(ImageReader(qr_buf), qr_x, qr_y, qr_size, qr_size)
    except ImportError:
        c.setStrokeColor(yellow)
        c.setLineWidth(2)
        c.rect(qr_x - 1 * mm, qr_y - 1 * mm, qr_size + 2 * mm, qr_size + 2 * mm, fill=0, stroke=1)
        c.setFillColor(dark)
        c.setFont('Helvetica', 5)
        c.drawCentredString(qr_x + qr_size / 2, qr_y + qr_size / 2, 'QR')

    # Footer — signature (pas de validité)
    c.setStrokeColor(colors.HexColor('#CCCCCC'))
    c.line(content_x, 5 * mm, width - 30 * mm, 5 * mm)
    c.setFillColor(colors.HexColor('#888888'))
    c.setFont('Helvetica', 5.5)
    c.drawCentredString(content_x + 25 * mm, 2 * mm, 'Signature autorisée')

    c.setFont('Helvetica', 4)
    c.setFillColor(colors.HexColor('#AAAAAA'))
    c.drawRightString(width - 4 * mm, 2 * mm, datetime.now().strftime('%d/%m/%Y'))

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
