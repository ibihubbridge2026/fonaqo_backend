"""Envoi d'emails système FONACO via SMTP (Maildev en local)."""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _send_html_email(*, to: str, subject: str, template: str, context: dict) -> bool:
    if not to or '@internal.fonaqo.local' in to:
        logger.info('Email ignoré (adresse interne): %s — %s', to, subject)
        return False
    try:
        html = render_to_string(template, context)
        text = render_to_string(template.replace('.html', '.txt'), context)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )
        msg.attach_alternative(html, 'text/html')
        msg.send(fail_silently=False)
        logger.info('Email envoyé à %s — %s', to, subject)
        return True
    except Exception:
        logger.exception('Échec envoi email à %s — %s', to, subject)
        return False


def send_welcome_email(user) -> bool:
    role = 'agent' if user.is_agent else 'client'
    return _send_html_email(
        to=user.email,
        subject='Bienvenue sur FONACO',
        template='emails/welcome.html',
        context={'user': user, 'role': role},
    )


def send_kyc_approved_email(user) -> bool:
    return _send_html_email(
        to=user.email,
        subject='Votre compte agent FONACO est validé',
        template='emails/kyc_approved.html',
        context={'user': user},
    )


def send_kyc_rejected_email(user, reason: str = '') -> bool:
    return _send_html_email(
        to=user.email,
        subject='Votre dossier KYC nécessite une correction',
        template='emails/kyc_rejected.html',
        context={'user': user, 'reason': reason},
    )


def send_account_suspended_email(user, reason: str = '') -> bool:
    return _send_html_email(
        to=user.email,
        subject='Suspension de votre compte FONACO',
        template='emails/account_suspended.html',
        context={'user': user, 'reason': reason},
    )


def send_account_reactivated_email(user) -> bool:
    return _send_html_email(
        to=user.email,
        subject='Votre compte FONACO est réactivé',
        template='emails/account_reactivated.html',
        context={'user': user},
    )


def send_badge_approved_email(user, agent_code: str = '') -> bool:
    return _send_html_email(
        to=user.email,
        subject='Votre badge professionnel FONACO est prêt',
        template='emails/badge_approved.html',
        context={'user': user, 'agent_code': agent_code},
    )
