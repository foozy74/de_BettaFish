"""
Clerk JWT-Validierung via JWKS

Clerk signiert JWTs mit RS256. Die öffentlichen Schlüssel werden vom
JWKS-Endpoint abgerufen und für 5 Minuten gecacht (PyJWKClient mit lifespan).

Relevante JWT-Claims:
    sub:      Clerk User ID
    org_id:   Clerk Organization ID  → wird für Tenant-Lookup verwendet
    org_slug: Organization Slug
    exp:      Ablaufzeitpunkt
"""

import threading
from typing import Any, Dict

import jwt
from jwt import InvalidTokenError, PyJWKClient  # PyJWT >= 2.8.0
from loguru import logger

# Ein PyJWKClient pro JWKS-URL (normalerweise nur einer)
_clients: Dict[str, PyJWKClient] = {}
_lock = threading.Lock()


def _get_client(jwks_url: str) -> PyJWKClient:
    """Gibt einen gecachten PyJWKClient für die URL zurück (Thread-sicher)."""
    if jwks_url not in _clients:
        with _lock:
            if jwks_url not in _clients:
                _clients[jwks_url] = PyJWKClient(
                    jwks_url,
                    cache_jwk_set=True,
                    lifespan=300,  # 5 Minuten JWKS-Cache
                )
                logger.info(f"JWKS-Client initialisiert: {jwks_url}")
    return _clients[jwks_url]


def validate_clerk_token(token: str, jwks_url: str) -> Dict[str, Any]:
    """
    Validiert ein Clerk JWT und gibt den Payload zurück.

    Args:
        token:    Bearer-Token aus dem Authorization-Header
        jwks_url: URL zum JWKS-Endpoint, z.B.
                  https://<clerk-domain>/.well-known/jwks.json

    Returns:
        Decodierter JWT-Payload als Dictionary

    Raises:
        jwt.ExpiredSignatureError:  Token ist abgelaufen
        jwt.InvalidTokenError:      Token ist ungültig (Signatur, Format, etc.)
    """
    client = _get_client(jwks_url)

    try:
        signing_key = client.get_signing_key_from_jwt(token)
    except Exception as exc:
        raise InvalidTokenError(f"JWKS-Schlüssel nicht gefunden: {exc}") from exc

    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"require": ["exp", "sub"]},
        leeway=30,  # 30 Sekunden Toleranz für Uhrzeit-Abweichungen
    )
