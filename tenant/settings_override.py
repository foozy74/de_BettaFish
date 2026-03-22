"""
TenantSettings — Settings-Proxy mit Tenant-spezifischen API-Key-Overrides

Wenn ein Tenant eigene API-Keys in shared.tenant_api_keys gespeichert hat,
werden die globalen BettaFish-Settings für diesen Request überschrieben.
Für nicht überschriebene Felder wird auf die System-Defaults zurückgefallen.

Verwendung in Agent-Modulen:

    # Statt:
    from config import settings

    # Verwenden:
    from tenant.settings_override import TenantSettings
    from config import settings as _base_settings

    def get_settings():
        return TenantSettings(_base_settings)

    # Im Route-Handler:
    settings = get_settings()
    api_key = settings.QUERY_ENGINE_API_KEY   # Tenant-Key oder System-Default
    base_url = settings.QUERY_ENGINE_BASE_URL  # Tenant-URL  oder System-Default

Bekannte Settings-Keys (werden als config_overrides gespeichert):
    INSIGHT_ENGINE_API_KEY   / _BASE_URL / _MODEL_NAME
    MEDIA_ENGINE_API_KEY     / _BASE_URL / _MODEL_NAME
    QUERY_ENGINE_API_KEY     / _BASE_URL / _MODEL_NAME
    REPORT_ENGINE_API_KEY    / _BASE_URL / _MODEL_NAME
    MINDSPIDER_API_KEY       / _BASE_URL / _MODEL_NAME
    FORUM_HOST_API_KEY       / _BASE_URL / _MODEL_NAME
    KEYWORD_OPTIMIZER_API_KEY / _BASE_URL / _MODEL_NAME
    TAVILY_API_KEY
"""

from typing import Any, Optional

from loguru import logger


def _get_tenant_override(key: str) -> Optional[str]:
    """
    Liest den Tenant-spezifischen Wert für key aus flask.g.tenant.

    Gibt None zurück wenn:
    - Kein Flask-Kontext vorhanden (außerhalb eines Requests)
    - g.tenant nicht gesetzt
    - Key nicht in config_overrides
    """
    try:
        from flask import g
        tenant = getattr(g, "tenant", None)
        if tenant and tenant.config_overrides:
            return tenant.config_overrides.get(key)
    except RuntimeError:
        # Außerhalb des Flask-Request-Kontexts (z.B. CLI-Aufruf)
        pass
    return None


class TenantSettings:
    """
    Read-only Proxy für globale BettaFish-Settings mit Tenant-Overrides.

    Attribute-Zugriff:
    1. Prüft flask.g.tenant.config_overrides auf einen Wert für den Key
    2. Fällt auf das ursprüngliche Settings-Objekt zurück

    Schreibzugriffe werden nicht unterstützt (immutable Proxy).
    """

    __slots__ = ("_base",)

    def __init__(self, base_settings: Any) -> None:
        object.__setattr__(self, "_base", base_settings)

    def __getattr__(self, name: str) -> Any:
        override = _get_tenant_override(name)
        if override is not None:
            logger.debug(f"TenantSettings: Override für '{name}' aktiv")
            return override
        return getattr(object.__getattribute__(self, "_base"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(
            "TenantSettings ist ein read-only Proxy. "
            "Schreibe direkt in shared.tenant_api_keys über die Admin-API."
        )

    def __repr__(self) -> str:
        base = object.__getattribute__(self, "_base")
        return f"TenantSettings(base={base!r})"
