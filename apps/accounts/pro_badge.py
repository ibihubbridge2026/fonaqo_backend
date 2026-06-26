"""Génération PDF badge agent FONAQO — ReportLab pixel-perfect (54×86 mm)."""

from __future__ import annotations

import io
import math
import os

from django.conf import settings
from django.contrib.staticfiles.finders import find
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

GOLD     = colors.HexColor('#f8c400')
DARK     = colors.HexColor('#111111')
WHITE    = colors.white
GREY     = colors.HexColor('#f2f2f2')
LABEL    = colors.HexColor('#444444')
GREY2    = colors.HexColor('#888888')
GREY3    = colors.HexColor('#cccccc')

CARD_W   = 54 * mm
CARD_H   = 86 * mm
HEADER_H = 31 * mm
FOOTER_H = 5 * mm


def _verify_url(agent_code: str) -> str:
    base = getattr(settings, 'SITE_BASE_URL', 'https://fonaqo.com').rstrip('/')
    return f'{base}/verify/badge/{agent_code}'


def _load_photo(profile) -> ImageReader | None:
    """
    Charge la photo pour le badge avec priorité stricte :
    1. user.profile_picture (photo de profil officielle)
    2. profile.badge_photo (photo dédiée au badge)
    JAMAIS selfie_photo (photo KYC avec carte d'identité)
    """
    user = getattr(profile, 'user', None)
    
    # Priorité 1: Photo de profil officielle
    if user and hasattr(user, 'profile_picture') and user.profile_picture:
        try:
            return ImageReader(user.profile_picture.path)
        except Exception:
            pass
    
    # Priorité 2: Photo dédiée au badge
    badge_photo = getattr(profile, 'badge_photo', None)
    if badge_photo:
        try:
            return ImageReader(badge_photo.path)
        except Exception:
            pass
    
    return None


def _load_header_image() -> ImageReader | None:
    path = find('images/background.png')
    if path and os.path.isfile(path):
        try:
            return ImageReader(path)
        except Exception:
            pass
    return None


def _clip_circle(c: canvas.Canvas, cx: float, cy: float, r: float, img: ImageReader) -> None:
    c.saveState()
    path = c.beginPath()
    for i in range(64):
        angle = 2 * math.pi * i / 64
        px, py = cx + r * math.cos(angle), cy + r * math.sin(angle)
        path.moveTo(px, py) if i == 0 else path.lineTo(px, py)
    path.close()
    c.clipPath(path, fill=0, stroke=0)
    # Fond sombre avant l'image pour éliminer tout blanc
    c.setFillColor(colors.HexColor('#1a1a1a'))
    c.circle(cx, cy, r, fill=1, stroke=0)
    c.drawImage(img, cx - r * 1.1, cy - r * 1.1, 2 * r * 1.1, 2 * r * 1.1, mask='auto')
    c.restoreState()


def _draw_yellow_wave(c: canvas.Canvas, header_bottom_y: float) -> None:
    """Vague jaune continue fluide sous le header noir."""
    c.setFillColor(GOLD)
    p = c.beginPath()
    wave_y = header_bottom_y - 4 * mm
    p.moveTo(-0.15 * CARD_W, header_bottom_y)
    p.curveTo(CARD_W * 0.25, wave_y + 5 * mm, CARD_W * 0.5, wave_y - 2 * mm, CARD_W * 1.15, header_bottom_y)
    p.lineTo(CARD_W * 1.15, wave_y - 8 * mm)
    p.curveTo(CARD_W * 0.5, wave_y - 13 * mm, CARD_W * 0.25, wave_y - 3 * mm, -0.15 * CARD_W, wave_y - 8 * mm)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    c.setFillColor(WHITE)
    p2 = c.beginPath()
    white_y = header_bottom_y - 7 * mm
    p2.moveTo(-0.15 * CARD_W, header_bottom_y - 1 * mm)
    p2.curveTo(CARD_W * 0.25, white_y + 4 * mm, CARD_W * 0.5, white_y - 3 * mm, CARD_W * 1.15, header_bottom_y - 1 * mm)
    p2.lineTo(CARD_W * 1.15, white_y - 11 * mm)
    p2.curveTo(CARD_W * 0.5, white_y - 16 * mm, CARD_W * 0.25, white_y - 4 * mm, -0.15 * CARD_W, white_y - 11 * mm)
    p2.close()
    c.drawPath(p2, fill=1, stroke=0)


def _draw_internal_badge(c: canvas.Canvas) -> None:
    """Badge AGENT INTERNE - Design élégant à gauche (cercle + label)."""
    badge_x = 2 * mm
    badge_y = CARD_H - 2 * mm - 5 * mm
    circle_r = 2.5 * mm
    circle_cx = badge_x + circle_r
    circle_cy = badge_y + circle_r
    
    # Cercle jaune avec bordure noire
    c.setFillColor(GOLD)
    c.circle(circle_cx, circle_cy, circle_r, fill=1, stroke=0)
    c.setLineWidth(0.5 * mm)
    c.setStrokeColor(DARK)
    c.circle(circle_cx, circle_cy, circle_r, fill=0, stroke=1)
    
    # Icône étoile dans le cercle
    c.setFillColor(DARK)
    c.setFont('ZapfDingbats', 7)
    c.drawCentredString(circle_cx, circle_cy - 0.5 * mm, '★')
    
    # Label noir avec texte jaune
    label_x = badge_x + circle_r * 2 + 1 * mm
    label_y = badge_y + 0.8 * mm
    label_w = 10 * mm
    label_h = 3.4 * mm
    corner_r = 1 * mm
    
    c.setFillColor(DARK)
    c.roundRect(label_x, label_y, label_w, label_h, corner_r, fill=1, stroke=0)
    
    c.setFillColor(GOLD)
    c.setFont('Helvetica-Bold', 3.5)
    c.drawString(label_x + 2 * mm, label_y + 1.2 * mm, 'INTERNE')


def _draw_user_icon(c: canvas.Canvas, x: float, y: float, size: float) -> None:
    """Dessine une icône utilisateur géométrique (cercle tête + arc buste)."""
    c.setFillColor(colors.HexColor('#F7C600'))
    cx, cy = x + size / 2, y + size / 2
    head_r = size * 0.22
    c.circle(cx, cy + size * 0.12, head_r, fill=1, stroke=0)
    # Buste (arc de cercle)
    p = c.beginPath()
    p.moveTo(cx - size * 0.35, cy - size * 0.35)
    p.curveTo(cx - size * 0.35, cy + size * 0.1, cx + size * 0.35, cy + size * 0.1, cx + size * 0.35, cy - size * 0.35)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def _draw_calendar_icon(c: canvas.Canvas, x: float, y: float, size: float) -> None:
    """Dessine une icône calendrier géométrique (rectangle + lignes)."""
    c.setFillColor(colors.HexColor('#F7C600'))
    cx, cy = x + size / 2, y + size / 2
    rect_w, rect_h = size * 0.5, size * 0.38
    rect_x, rect_y = cx - rect_w / 2, cy - rect_h / 2
    c.roundRect(rect_x, rect_y, rect_w, rect_h, size * 0.08, fill=1, stroke=0)
    # Ligne horizontale supérieure
    c.setStrokeColor(DARK)
    c.setLineWidth(size * 0.05)
    c.line(rect_x + size * 0.1, rect_y + size * 0.12, rect_x + rect_w - size * 0.1, rect_y + size * 0.12)
    # Lignes verticales (jours)
    line_y = rect_y + size * 0.22
    c.line(rect_x + size * 0.1, line_y, rect_x + size * 0.1, rect_y + rect_h - size * 0.08)
    c.line(rect_x + rect_w - size * 0.1, line_y, rect_x + rect_w - size * 0.1, rect_y + rect_h - size * 0.08)


def _draw_icon_box(c: canvas.Canvas, x: float, y: float, size: float, icon_type: str) -> None:
    """Dessine un carré noir avec icône géométrique à l'intérieur."""
    c.setFillColor(DARK)
    c.roundRect(x, y, size, size, 0.8 * mm, fill=1, stroke=0)
    if icon_type == 'user':
        _draw_user_icon(c, x, y, size)
    elif icon_type == 'calendar':
        _draw_calendar_icon(c, x, y, size)


def _draw_qr(c: canvas.Canvas, url: str, x: float, y: float, size: float) -> None:
    try:
        import qrcode as _qr
        qr = _qr.QRCode(error_correction=_qr.constants.ERROR_CORRECT_M, box_size=4, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        c.drawImage(ImageReader(buf), x, y, size, size)
    except Exception:
        c.setFillColor(WHITE)
        c.rect(x, y, size, size, fill=1, stroke=0)
        c.setFillColor(DARK)
        c.setFont('Helvetica-Bold', 4)
        c.drawCentredString(x + size / 2, y + size / 2, 'QR')


def build_agent_pro_badge_pdf(user, profile) -> bytes:
    """PDF badge PVC ID-1 pixel-perfect (54mm × 86mm)."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(CARD_W, CARD_H))
    c.setTitle(f'Badge FONAQO — {profile.agent_code or user.username}')

    agent_code = profile.agent_code or f'AGT-{str(user.pk)[:5].upper()}'
    raw_name = (user.get_full_name() or user.username or '').upper().strip()
    # Logique intelligente : premier nom entier, autres abrégés si trop long
    parts = raw_name.split()
    if len(parts) > 1 and len(raw_name) > 24:
        first_name = parts[0]
        other_names = ' '.join([p[0] + '.' for p in parts[1:]])
        full_name = f'{first_name} {other_names}'
    else:
        full_name = raw_name[:24] + '…' if len(raw_name) > 24 else raw_name
    joined = user.date_joined.strftime('%m / %Y') if getattr(user, 'date_joined', None) else '—'
    verify_url = _verify_url(agent_code)
    is_internal = getattr(profile, 'is_internal', False)
    header_bottom_y = CARD_H - HEADER_H
    wave_y = header_bottom_y - 8 * mm

    # Fond blanc
    c.setFillColor(WHITE)
    c.rect(0, 0, CARD_W, CARD_H, fill=1, stroke=0)

    # Header noir avec image background.png — couverture totale jusqu'à la ligne jaune
    c.setFillColor(DARK)
    header_extended_y = header_bottom_y - 12 * mm
    c.rect(0, header_extended_y, CARD_W, HEADER_H + 12 * mm, fill=1, stroke=0)
    header_img = _load_header_image()
    if header_img:
        c.saveState()
        clip_path = c.beginPath()
        clip_path.moveTo(0, CARD_H)
        clip_path.lineTo(CARD_W, CARD_H)
        clip_path.lineTo(CARD_W, header_bottom_y)
        wave_y = header_bottom_y - 4 * mm
        clip_path.curveTo(
            CARD_W * 0.25, wave_y + 5 * mm,
            CARD_W * 0.5, wave_y - 2 * mm,
            CARD_W * 1.15, header_bottom_y,
        )
        clip_path.lineTo(CARD_W * 1.15, wave_y - 8 * mm)
        clip_path.curveTo(
            CARD_W * 0.5, wave_y - 13 * mm,
            CARD_W * 0.25, wave_y - 3 * mm,
            0, header_bottom_y,
        )
        clip_path.close()
        c.clipPath(clip_path, fill=0, stroke=0)
        c.drawImage(
            header_img,
            0,
            header_extended_y,
            CARD_W,
            HEADER_H + 12 * mm,
            preserveAspectRatio=False,
            mask='auto',
        )
        c.restoreState()

    # Ruban AGENT INTERNE conditionnel
    if is_internal:
        _draw_internal_badge(c)

    # Vague jaune continue
    _draw_yellow_wave(c, header_bottom_y)

    # Photo ronde avec bordure jaune — positionnée à 50% haut / 50% bas
    photo_r = 12 * mm
    photo_cx = CARD_W / 2
    photo_cy = header_bottom_y
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.2 * mm)
    c.circle(photo_cx, photo_cy, photo_r, fill=0, stroke=1)
    img = _load_photo(profile)
    inner_r = photo_r - 1.2 * mm
    if img:
        _clip_circle(c, photo_cx, photo_cy, inner_r, img)
    else:
        c.setFillColor(colors.HexColor('#EAEAEA'))
        c.circle(photo_cx, photo_cy, inner_r, fill=1, stroke=0)

    # Nom centré
    name_y = photo_cy - photo_r - 3.5 * mm - 1.5 * mm
    c.setFillColor(DARK)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(CARD_W / 2, name_y, full_name)

    # Pilule AGENT DE TERRAIN
    pill_w, pill_h = 26 * mm, 5 * mm
    pill_x = (CARD_W - pill_w) / 2
    pill_y = name_y - 3 * mm
    c.setFillColor(DARK)
    c.roundRect(pill_x, pill_y - pill_h, pill_w, pill_h, 2.5 * mm, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont('Helvetica-Bold', 6)
    c.drawCentredString(CARD_W / 2, pill_y - pill_h / 2 - 0.5 * mm, 'AGENT DE TERRAIN')

    # Grille informations — espacement 5mm minimum sous pilule
    table_w = CARD_W * 0.86
    table_x = (CARD_W - table_w) / 2
    icon_size = 4 * mm
    row_gap = 7 * mm
    row1_baseline = pill_y - pill_h - 5 * mm
    row2_baseline = row1_baseline - row_gap

    _draw_icon_box(c, table_x, row1_baseline - icon_size / 2 + 0.6 * mm, icon_size, 'user')
    c.setFillColor(LABEL)
    c.setFont('Helvetica-Bold', 6)
    c.drawString(table_x + icon_size + 2 * mm, row1_baseline, 'ID AGENT')
    c.setFillColor(DARK)
    c.setFont('Helvetica-Bold', 6.8)
    c.drawRightString(table_x + table_w - 5 * mm, row1_baseline, agent_code)

    c.setStrokeColor(GREY)
    c.setLineWidth(0.2 * mm)
    c.line(table_x, row1_baseline - 1.5 * mm, table_x + table_w, row1_baseline - 1.5 * mm)

    _draw_icon_box(c, table_x, row2_baseline - icon_size / 2 + 0.6 * mm, icon_size, 'calendar')
    c.setFillColor(LABEL)
    c.setFont('Helvetica-Bold', 6)
    c.drawString(table_x + icon_size + 2 * mm, row2_baseline, 'INSCRIT DEPUIS')
    c.setFillColor(DARK)
    c.setFont('Helvetica-Bold', 6.8)
    c.drawRightString(table_x + table_w - 5 * mm, row2_baseline, joined)

    # Zone signature + QR code
    bottom_y = FOOTER_H + 2.5 * mm
    sig_x = table_x
    sig_w = table_w * 0.45
    
    c.setStrokeColor(GREY3)
    c.setLineWidth(0.2 * mm)
    c.line(sig_x, bottom_y + 2 * mm, sig_x + sig_w, bottom_y + 2 * mm)
    c.setFillColor(GREY2)
    c.setFont('Helvetica-Bold', 4)
    c.drawString(sig_x, bottom_y - 0.5 * mm, 'SIGNATURE DE L\'AGENT')

    qr_size = 9.5 * mm
    qr_x = table_x + table_w - qr_size
    qr_y = FOOTER_H + 0.5 * mm
    _draw_qr(c, verify_url, qr_x, qr_y, qr_size)
    c.setFillColor(DARK)
    c.setFont('Helvetica-Bold', 4)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 2 * mm, 'VÉRIFIER CE BADGE')

    # Footer noir
    c.setFillColor(DARK)
    c.rect(0, 0, CARD_W, FOOTER_H, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 4.5)
    c.drawCentredString(CARD_W / 2, FOOTER_H / 2 - 0.5 * mm, 'VOTRE CONFIANCE, NOTRE ENGAGEMENT.')

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
