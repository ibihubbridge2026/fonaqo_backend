from decimal import Decimal, InvalidOperation

from django.core.cache import cache

from .models import PlatformConfiguration

CACHE_TTL = 300

FEES_URGENT_KEY = 'FEES_URGENT'
FEES_CONFIDENTIAL_KEY = 'FEES_CONFIDENTIAL'
SPLIT_AGENT_PCT_KEY = 'SPLIT_AGENT_PCT'
SPLIT_PLATFORM_PCT_KEY = 'SPLIT_PLATFORM_PCT'
SPLIT_INFLUENCER_PCT_KEY = 'SPLIT_INFLUENCER_PCT'
BOOST_PROMO_PERCENT_KEY = 'BOOST_PROMO_PERCENT'
BOOST_PROMO_UNTIL_KEY = 'BOOST_PROMO_UNTIL'
AGENT_MISSION_DELAY_MINUTES_KEY = 'AGENT_MISSION_DELAY_MINUTES'

DEFAULT_FEES = {
    FEES_URGENT_KEY: Decimal('500'),
    FEES_CONFIDENTIAL_KEY: Decimal('500'),
}

DEFAULT_SPLIT = {
    SPLIT_AGENT_PCT_KEY: Decimal('88'),
    SPLIT_PLATFORM_PCT_KEY: Decimal('10'),
    SPLIT_INFLUENCER_PCT_KEY: Decimal('2'),
}

DEFAULT_AGENT_MISSION_DELAY_MINUTES = 10


class PlatformConfigService:
    """Lecture centralisée des paramètres plateforme."""

    @staticmethod
    def get_raw(key: str, default: str = '') -> str:
        cache_key = f'platform_cfg:{key}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            value = PlatformConfiguration.objects.get(key=key).value
        except PlatformConfiguration.DoesNotExist:
            value = default
        cache.set(cache_key, value, CACHE_TTL)
        return value

    @classmethod
    def get_decimal(cls, key: str, default: Decimal | str = '0') -> Decimal:
        raw = cls.get_raw(key, str(default))
        try:
            return Decimal(str(raw).strip())
        except (InvalidOperation, TypeError):
            return Decimal(str(default))

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        try:
            return int(cls.get_decimal(key, default))
        except (ValueError, TypeError):
            return default

    @classmethod
    def mission_options_fee(cls, *, is_urgent: bool, is_confidential: bool) -> Decimal:
        total = Decimal('0')
        if is_urgent:
            total += cls.get_decimal(
                FEES_URGENT_KEY,
                DEFAULT_FEES[FEES_URGENT_KEY],
            )
        if is_confidential:
            total += cls.get_decimal(
                FEES_CONFIDENTIAL_KEY,
                DEFAULT_FEES[FEES_CONFIDENTIAL_KEY],
            )
        return total

    @classmethod
    def agent_mission_delay_minutes(cls) -> int:
        """Délai avant visibilité panier agent (non boost), configurable SuperAdmin."""
        delay = cls.get_int(
            AGENT_MISSION_DELAY_MINUTES_KEY,
            DEFAULT_AGENT_MISSION_DELAY_MINUTES,
        )
        return max(0, min(delay, 120))

    @classmethod
    def invalidate(cls, key: str | None = None) -> None:
        if key:
            cache.delete(f'platform_cfg:{key}')
            return
        for k in DEFAULT_FEES:
            cache.delete(f'platform_cfg:{k}')

    @classmethod
    def set_value(cls, key: str, value: str, description: str = '') -> PlatformConfiguration:
        obj, _ = PlatformConfiguration.objects.update_or_create(
            key=key,
            defaults={
                'value': str(value).strip(),
                'description': description,
            },
        )
        cls.invalidate(key)
        return obj
