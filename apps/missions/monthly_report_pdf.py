"""Génération PDF relevé mensuel agent (template FONAQO)."""
from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _fmt_fcfa(amount):
    val = int(Decimal(str(amount or 0)))
    return f'{val:,}'.replace(',', ' ') + ' FCFA'


def build_agent_monthly_report_pdf(user, month_str, transactions, totals):
    """Construit le PDF binaire du relevé mensuel."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.black,
        alignment=1,
        spaceAfter=8,
    )
    header_meta = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontSize=9,
        alignment=2,
    )
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.black,
        backColor=colors.HexColor('#FFD400'),
        spaceBefore=6,
        spaceAfter=6,
        leftIndent=4,
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        wordWrap='CJK',
    )

    elements.append(
        Paragraph(
            f'<b>FONAQO</b> &nbsp;&nbsp; Relevé N° FNQ-REL-{month_str.replace("-", "")}-0042',
            styles['Normal'],
        )
    )
    elements.append(Paragraph(f'Période : {month_str}', header_meta))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph('RELEVÉ MENSUEL AGENT — FONAQO', title_style))
    elements.append(Spacer(1, 12))

    agent_name = (
        f'{user.first_name or ""} {user.last_name or ""}'.strip()
        or user.username
        or 'Agent'
    )
    agent_info = [
        [Paragraph('<b>1. INFORMATIONS AGENT</b>', section_style)],
        [
            Paragraph(
                f'<b>Nom :</b> {agent_name}<br/>'
                f'<b>Téléphone :</b> {user.phone_number or "—"}<br/>'
                f'<b>Email :</b> {user.email or "—"}<br/>'
                f'<b>Catégorie :</b> {user.service_domain or "Polyvalent"}<br/>'
                f'<b>Statut :</b> Actif',
                cell_style,
            )
        ],
    ]
    info_table = Table(agent_info, colWidths=[doc.width])
    info_table.setStyle(
        TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFD400')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ])
    )
    elements.append(info_table)
    elements.append(Spacer(1, 14))

    elements.append(
        Paragraph('<b>2. MOUVEMENTS DU COMPTE — Dépôts &amp; Retraits</b>', section_style)
    )
    elements.append(Spacer(1, 6))

    headers = ['Date', 'Référence', 'Type', 'Description', 'Montant']
    rows = [[Paragraph(f'<b>{h}</b>', cell_style) for h in headers]]

    for tx in transactions:
        amount = Decimal(str(tx.amount))
        is_credit = amount >= 0
        type_label = tx.get_transaction_type_display()
        rows.append([
            Paragraph(tx.created_at.strftime('%d/%m/%Y'), cell_style),
            Paragraph(str(tx.reference or tx.id)[:12], cell_style),
            Paragraph(type_label[:20], cell_style),
            Paragraph((tx.description or '—')[:40], cell_style),
            Paragraph(
                f'<font color="{"#2E7D32" if is_credit else "#C62828"}">'
                f'{"+" if is_credit else ""}{_fmt_fcfa(amount)}</font>',
                cell_style,
            ),
        ])

    if len(rows) == 1:
        rows.append([
            Paragraph('—', cell_style),
            Paragraph('—', cell_style),
            Paragraph('—', cell_style),
            Paragraph('Aucun mouvement ce mois', cell_style),
            Paragraph('0 FCFA', cell_style),
        ])

    col_widths = [0.85 * inch, 0.95 * inch, 1.0 * inch, 2.4 * inch, 1.1 * inch]
    tx_table = Table(rows, colWidths=col_widths, repeatRows=1)
    tx_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFD400')),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ])
    )
    elements.append(tx_table)
    elements.append(Spacer(1, 10))

    summary = [
        ['Total dépôts', _fmt_fcfa(totals.get('deposits', 0))],
        ['Total retraits', _fmt_fcfa(totals.get('withdrawals', 0))],
        ['Solde net du mois', _fmt_fcfa(totals.get('net', 0))],
    ]
    summary_table = Table(summary, colWidths=[3.5 * inch, 2.0 * inch])
    summary_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8F5E9')),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#FCE4EC')),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#FFD400')),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ])
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 16))
    elements.append(
        Paragraph(
            'Merci pour votre engagement — L\'équipe Fonaqo<br/>'
            'Fonaqo SARL, Cotonou, Bénin | support@fonaqo.bj | www.fonaqo.bj',
            ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey),
        )
    )

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
