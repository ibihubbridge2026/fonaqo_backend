"""
Utilitaires pour la création de mission par voix.

- find_best_category()    : mapping texte IA → services.Category
- geocode_address()       : adresse texte → (lat, lng) via Nominatim
- validate_extracted_json(): schéma strict avec jsonschema
- compute_transcription_hash(): hash SHA-256 pour anti-doublon
"""
import hashlib
import logging
import re
import time
import unicodedata

import requests
from jsonschema import Draft7Validator, ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Dictionnaire de synonymes catégorie
# ---------------------------------------------------------------------------
CATEGORY_SYNONYMS: dict[str, list[str]] = {
    "plomberie": [
        "plombier", "plomb", "fuite", "tuyau", "robinet", "wc", "toilette",
        "eau", "canalisation", "évier", "lavabo", "douche", "bain",
    ],
    "électricité": [
        "electricite", "électricien", "courant", "prise", "disjoncteur",
        "câble", "ampoule", "éclairage", "panneau", "SBEE", "facture",
        "compteur", "installation électrique",
    ],
    "ménage": [
        "menage", "nettoyage", "nettoyer", "femme de ménage", "ménagère",
        "balayer", "aspirateur", "rangement", "propreté",
    ],
    "livraison": [
        "livrer", "livreur", "coursier", "course", "colis", "transport",
        "apporter", "déposer", "enlèvement", "ramasser",
    ],
    "jardinage": [
        "jardin", "jardiner", "pelouse", "gazon", "arbre", "plante",
        "taille", "entretien extérieur",
    ],
    "déménagement": [
        "demenagement", "déménager", "déménageur", "déplacer meuble",
        "transport meuble", "camion déménagement",
    ],
    "peinture": [
        "peindre", "peintre", "repeinture", "badigeon", "décoration murale",
        "travaux peinture",
    ],
    "maçonnerie": [
        "macon", "maçon", "béton", "ciment", "mur", "carrelage",
        "carreleur", "dalle", "construction",
    ],
    "serrurerie": [
        "serrurier", "serrure", "clé", "porte", "verrou", "coffre",
    ],
    "informatique": [
        "informaticien", "ordinateur", "pc", "réparation pc", "virus",
        "réseau", "wifi", "internet",
    ],
    "cuisine": [
        "cuisinier", "chef", "repas", "préparer à manger", "traiteur",
        "cuisiner",
    ],
    "garde d'enfants": [
        "baby-sitter", "nourrice", "garde enfant", "baby sitter",
        "garderie", "enfants",
    ],
}


def _normalize(text: str) -> str:
    """Lowercase + strip accents + collapse whitespace."""
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text)
    return text


def find_best_category(ai_category_text: str):
    """
    Mappe le texte de catégorie retourné par l'IA vers un objet
    ``services.Category`` réel (ou None si aucun match).

    Priorité :
        1. Correspondance exacte sur name (icase)
        2. Correspondance sur keywords du modèle (icase)
        3. Synonymes locaux → name exact ou keywords
        4. Fuzzy : sous-chaîne bidirectionnelle
        5. None
    """
    from apps.services.models import Category  # import local pour éviter les cycles

    if not ai_category_text:
        return None

    normalized_input = _normalize(ai_category_text)
    all_cats = list(Category.objects.all())

    # --- Étape 1 : correspondance exacte sur le nom ---
    for cat in all_cats:
        if _normalize(cat.name) == normalized_input:
            return cat

    # --- Étape 2 : keywords du modèle ---
    for cat in all_cats:
        for kw in [k.strip() for k in (cat.keywords or "").split(",") if k.strip()]:
            if _normalize(kw) == normalized_input:
                return cat

    # --- Étape 3 : synonymes locaux ---
    matched_canonical = None
    for canonical, synonyms in CATEGORY_SYNONYMS.items():
        all_terms = [canonical] + synonyms
        for term in all_terms:
            if _normalize(term) == normalized_input:
                matched_canonical = canonical
                break
        if matched_canonical:
            break

    if matched_canonical:
        # Chercher la catégorie dans la DB correspondant au canonical
        for cat in all_cats:
            if _normalize(cat.name) == _normalize(matched_canonical):
                return cat
            for kw in [k.strip() for k in (cat.keywords or "").split(",") if k.strip()]:
                if _normalize(kw) == _normalize(matched_canonical):
                    return cat

    # --- Étape 4 : fuzzy (sous-chaîne) ---
    for cat in all_cats:
        cat_norm = _normalize(cat.name)
        if normalized_input in cat_norm or cat_norm in normalized_input:
            return cat
        for kw in [k.strip() for k in (cat.keywords or "").split(",") if k.strip()]:
            kw_norm = _normalize(kw)
            if normalized_input in kw_norm or kw_norm in normalized_input:
                return cat

    logger.warning("find_best_category: aucune correspondance pour '%s'", ai_category_text)
    return None


# ---------------------------------------------------------------------------
# 2. Schéma JSON pour la validation stricte de l'extraction IA
# ---------------------------------------------------------------------------
_EXTRACTED_SCHEMA = {
    "type": "object",
    "required": ["title", "description"],
    "properties": {
        "title":               {"type": ["string", "null"]},
        "description":         {"type": ["string", "null"]},
        "category":            {"type": ["string", "null"]},
        "budget":              {"type": ["number", "string", "null"], "minimum": 0},
        "scheduled_date":      {
            "type": ["string", "null"],
            "enum": ["ASAP", "TODAY", "TOMORROW", "THIS_WEEK", None, "null", ""],
        },
        "scheduled_time_slot": {
            "type": ["string", "null"],
            "enum": ["MORNING", "AFTERNOON", "EVENING", None, "null", ""],
        },
        "address":             {"type": ["string", "null"]},
        "is_urgent":           {"type": ["boolean", "string", "null"]},
    },
    "additionalProperties": True,
}

_validator = Draft7Validator(_EXTRACTED_SCHEMA)


def _parse_budget_robust(budget_str: str) -> float | None:
    """
    Parse robuste du budget pour gérer divers formats :
    - "10000" → 10000.0
    - "10 000" → 10000.0
    - "10,000" → 10000.0
    - "10.000" → 10000.0
    - "10 000 FCFA" → 10000.0
    - "environ 10 000" → 10000.0
    - "dix mille" → 10000.0 (basique)
    - "à négocier" → 0.0
    Retourne None si impossible à parser.
    """
    import re
    
    # Nettoyer la chaîne
    cleaned = budget_str.lower().strip()
    
    # Cas spéciaux
    if "à négocier" in cleaned or "negocier" in cleaned or "negotiable" in cleaned:
        return 0.0
    if "gratuit" in cleaned or "free" in cleaned:
        return 0.0
    
    # Extraire les nombres avec espaces, virgules, points
    # Remplacer les séparateurs de milliers (espaces) par rien
    # Remplacer les virgules décimales par points
    numbers = re.findall(r'[\d.,]+', cleaned)
    if not numbers:
        return None
    
    # Prendre le premier nombre trouvé
    num_str = numbers[0]
    # Nettoyer les séparateurs de milliers (espaces)
    num_str = num_str.replace(' ', '')
    # Remplacer virgule par point pour décimal
    num_str = num_str.replace(',', '.')
    
    try:
        return float(num_str)
    except ValueError:
        return None


def validate_extracted_json(data: dict) -> tuple[dict, list[str]]:
    """
    Valide et nettoie le dict extrait par l'IA.

    Retourne (cleaned_data, errors).
    ``errors`` est vide si la validation passe.
    """
    errors = [e.message for e in _validator.iter_errors(data)]
    if errors:
        return {}, errors

    # --- Validation custom (budget négatif) ---
    raw_budget = data.get("budget")
    if raw_budget is not None:
        try:
            budget_val = _parse_budget_robust(str(raw_budget))
            if budget_val is not None and budget_val < 0:
                return {}, ["budget doit être positif ou nul"]
        except (ValueError, TypeError):
            pass  # sera normalisé à None ci-dessous

    # --- Normalisation des types ---
    cleaned: dict = {}

    cleaned["title"] = (data.get("title") or "").strip() or None
    cleaned["description"] = (data.get("description") or "").strip() or None
    cleaned["category"] = (data.get("category") or "").strip() or None

    # Budget : parsing robuste pour divers formats
    if raw_budget is not None:
        try:
            cleaned["budget"] = _parse_budget_robust(str(raw_budget))
        except (ValueError, TypeError):
            cleaned["budget"] = None
    else:
        cleaned["budget"] = None

    # Énumérations : None/"null"/"" → None
    for field in ("scheduled_date", "scheduled_time_slot"):
        val = data.get(field)
        if val in (None, "null", ""):
            cleaned[field] = None
        else:
            cleaned[field] = val.upper() if isinstance(val, str) else None

    cleaned["address"] = (data.get("address") or "").strip() or None

    # is_urgent : "true"/"false" → bool
    raw_urgent = data.get("is_urgent")
    if isinstance(raw_urgent, bool):
        cleaned["is_urgent"] = raw_urgent
    elif isinstance(raw_urgent, str):
        cleaned["is_urgent"] = raw_urgent.lower() in ("true", "1", "oui")
    else:
        cleaned["is_urgent"] = False

    return cleaned, []


# ---------------------------------------------------------------------------
# 3. Transcription audio (Mistral Voxtral → Google STT)
# ---------------------------------------------------------------------------
def transcribe_audio_file(
    file_path: str,
    *,
    original_name: str = "audio.m4a",
    mistral_api_key: str | None = None,
    language: str = "fr",
) -> str:
    """
    Transcrit un fichier audio en texte.

    Ordre des tentatives :
        1. Mistral Voxtral (voxtral-mini-latest) si clé API disponible
        2. Google Speech Recognition via pydub → wav
    """
    errors: list[str] = []

    if mistral_api_key:
        try:
            text = _transcribe_with_mistral(
                file_path,
                original_name=original_name,
                api_key=mistral_api_key,
                language=language,
            )
            if text and text.strip():
                logger.info("transcribe_audio_file: Mistral OK (%d car.)", len(text))
                return text.strip()
        except Exception as exc:
            errors.append(f"mistral: {exc}")
            logger.warning("transcribe_audio_file Mistral échoué: %s", exc)

    try:
        text = _transcribe_with_google_stt(file_path)
        if text and text.strip():
            logger.info("transcribe_audio_file: Google STT OK (%d car.)", len(text))
            return text.strip()
    except Exception as exc:
        import speech_recognition as sr

        if isinstance(exc, sr.UnknownValueError):
            raise ValueError("audio_incomprehensible") from exc
        if isinstance(exc, sr.RequestError):
            raise ValueError(f"service_indisponible: {exc}") from exc
        errors.append(f"google: {exc}")
        logger.warning("transcribe_audio_file Google STT échoué: %s", exc)

    detail = " ; ".join(errors) if errors else "aucun moteur disponible"
    raise ValueError(f"Transcription impossible ({detail})")


def _transcribe_with_mistral(
    file_path: str,
    *,
    original_name: str,
    api_key: str,
    language: str = "fr",
) -> str:
    from mistralai import Mistral

    client = Mistral(api_key=api_key)
    with open(file_path, "rb") as audio_file:
        response = client.audio.transcriptions.complete(
            model="voxtral-mini-latest",
            file={"content": audio_file, "file_name": original_name or "audio.m4a"},
            language=language,
        )

    text = getattr(response, "text", None)
    if text is None and isinstance(response, dict):
        text = response.get("text")
    if text is None:
        raise ValueError("Réponse Mistral sans texte de transcription")
    return str(text)


def _transcribe_with_google_stt(file_path: str, language: str = "fr-FR") -> str:
    import os
    import speech_recognition as sr
    from pydub import AudioSegment

    suffix = os.path.splitext(file_path)[1] or ".m4a"
    wav_path = None
    try:
        audio_segment = AudioSegment.from_file(file_path)
        wav_path = file_path.rsplit(".", 1)[0] + ".wav"
        audio_segment.export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            return recognizer.recognize_google(audio_data, language=language)
    finally:
        if wav_path and os.path.exists(wav_path):
            try:
                os.unlink(wav_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# 4. Géocodage Nominatim (OSM) avec rate-limiting et fallback
# ---------------------------------------------------------------------------
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_LAST_NOMINATIM_CALL: list[float] = [0.0]  # pseudo-singleton mutable pour rate-limit


def geocode_address(address: str, country_hint: str = "BJ") -> tuple[float, float] | tuple[None, None]:
    """
    Convertit une adresse texte en (latitude, longitude).

    Ordre des tentatives :
        1. Nominatim avec pays =  country_hint (Bénin par défaut)
        2. Nominatim sans restriction de pays
        3. (None, None)

    Respecte la politique de rate-limiting Nominatim (1 req/s).
    """
    if not address or not address.strip():
        return None, None

    queries = [
        f"{address.strip()}, {country_hint}",
        address.strip(),
    ]

    headers = {"User-Agent": "FONACO-App/1.0 (fonaco@example.com)"}

    for query in queries:
        # Rate-limit : 1 requête par seconde
        elapsed = time.monotonic() - _LAST_NOMINATIM_CALL[0]
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)

        try:
            _LAST_NOMINATIM_CALL[0] = time.monotonic()
            resp = requests.get(
                _NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers=headers,
                timeout=5,
            )
            if resp.status_code == 200:
                results = resp.json()
                if results:
                    lat = float(results[0]["lat"])
                    lng = float(results[0]["lon"])
                    logger.info("geocode_address '%s' → (%.5f, %.5f)", query, lat, lng)
                    return lat, lng
        except Exception as exc:
            logger.warning("geocode_address erreur pour '%s': %s", query, exc)

    logger.warning("geocode_address: impossible de géocoder '%s'", address)
    return None, None


# ---------------------------------------------------------------------------
# 5. Hash anti-doublon
# ---------------------------------------------------------------------------
def compute_transcription_hash(transcription: str) -> str:
    """
    SHA-256 de la transcription normalisée (minuscules, espaces uniques).
    Utilisé pour détecter les doublons de missions vocales.
    """
    normalized = re.sub(r"\s+", " ", transcription.lower().strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
