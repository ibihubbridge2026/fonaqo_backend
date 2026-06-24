"""
AUDIT FIX [P0] — Validateurs de fichiers : MIME type + extension + taille
"""
import os

import magic
from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_IMAGE_MIME = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
}

ALLOWED_AUDIO_MIME = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg", "audio/webm",
}

ALLOWED_DOCUMENT_MIME = {
    "application/pdf",
}

ALLOWED_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".webp", ".gif"},
    "audio": {".mp3", ".mp4", ".wav", ".ogg", ".webm", ".m4a"},
    "document": {".pdf"},
}


def validate_file_mime_and_extension(
    file,
    allowed_mimes: set,
    allowed_extensions: set,
    max_size_mb: int = 10,
):
    """
    Valider un fichier uploadé par MIME réel, extension et taille.
    AUDIT FIX [P0] — Empêche l'upload de fichiers malveillants.
    """
    max_bytes = max_size_mb * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(
            f"Fichier trop volumineux. Maximum : {max_size_mb} Mo."
        )

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            f"Extension '{ext}' non autorisée. "
            f"Extensions acceptées : {', '.join(sorted(allowed_extensions))}"
        )

    file.seek(0)
    header = file.read(2048)
    file.seek(0)

    mime_type = magic.from_buffer(header, mime=True)
    if mime_type not in allowed_mimes:
        raise ValidationError(f"Type de fichier '{mime_type}' non autorisé.")


def validate_image_upload(file):
    """Valider un upload d'image."""
    validate_file_mime_and_extension(
        file,
        allowed_mimes=ALLOWED_IMAGE_MIME,
        allowed_extensions=ALLOWED_EXTENSIONS["image"],
        max_size_mb=getattr(settings, "UPLOAD_MAX_SIZE_MB", 10),
    )


def validate_audio_upload(file):
    """Valider un upload audio."""
    validate_file_mime_and_extension(
        file,
        allowed_mimes=ALLOWED_AUDIO_MIME,
        allowed_extensions=ALLOWED_EXTENSIONS["audio"],
        max_size_mb=getattr(settings, "UPLOAD_MAX_SIZE_MB", 10),
    )


def validate_document_upload(file):
    """Valider un upload de document."""
    validate_file_mime_and_extension(
        file,
        allowed_mimes=ALLOWED_DOCUMENT_MIME,
        allowed_extensions=ALLOWED_EXTENSIONS["document"],
        max_size_mb=50,
    )


def validate_chat_media(file):
    """Valider les fichiers media du chat (images)."""
    validate_image_upload(file)


def validate_chat_attachment(file):
    """Valider les pièces jointes du chat (images + PDF)."""
    allowed_mimes = ALLOWED_IMAGE_MIME | ALLOWED_DOCUMENT_MIME
    allowed_ext = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
    max_size = getattr(settings, "UPLOAD_MAX_SIZE_MB", 10)

    max_bytes = max_size * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(f"Fichier trop volumineux. Maximum : {max_size} Mo.")

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_ext:
        raise ValidationError(f"Extension non autorisée : {ext}")

    file.seek(0)
    header = file.read(2048)
    file.seek(0)
    mime_type = magic.from_buffer(header, mime=True)
    if mime_type not in allowed_mimes:
        raise ValidationError(f"Type de fichier non autorisé : {mime_type}")
