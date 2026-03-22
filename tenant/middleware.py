"""
Flask Tenant-Middleware

Stellt den require_tenant-Dekorator bereit.

Ablauf pro Request:
1. Authorization: Bearer <token> Header auslesen
2. JWT via Clerk JWKS validieren (RS256)
3. org_id aus dem JWT-Payload extrahieren
4. Tenant aus shared.tenants laden + API-Keys entschlüsseln
5. TenantContext in flask.g.tenant speichern
6. Route-Handler aufrufen

Konfiguration (Umgebungsvariablen):
    CLERK_JWKS_URL     Pflicht: JWKS-Endpoint des Clerk-Projekts
                       z.B. https://<frontend-api>/.well-known/jwks.json

Verwendung:
    from tenant.middleware import require_tenant
    from flask import g

    @app.route("/api/analyse", methods=["POST"])
    @require_tenant
    def analyse():
        tenant = g.tenant        # TenantContext
        schema = tenant.schema_name
        plan   = tenant.plan
        ...
"""

import os
from functools import wraps
from typing import Optional

import jwt as pyjwt
from flask import g, jsonify, request
from loguru import logger

from .db import get_tenant_from_db
from .jwt_validator import validate_clerk_token


def _extract_bearer_token() -> Optional[str]:
    """Liest den Bearer-Token aus dem Authorization-Header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):]
    return None


def require_tenant(f):
    """
    Flask-Dekorator: Validiert Clerk JWT und lädt den Tenant-Kontext.

    Gibt folgende HTTP-Fehler zurück:
        401  Kein Token / Token abgelaufen / ungültig
        403  Token enthält keine org_id / Tenant nicht gefunden oder gesperrt
        500  Server-Konfigurationsfehler (CLERK_JWKS_URL nicht gesetzt)
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({"error": "Authentifizierung erforderlich"}), 401

        jwks_url = os.environ.get("CLERK_JWKS_URL", "")
        if not jwks_url:
            logger.error("CLERK_JWKS_URL ist nicht konfiguriert")
            return jsonify({"error": "Serverkonfigurationsfehler"}), 500

        # JWT validieren
        try:
            payload = validate_clerk_token(token, jwks_url)
        except pyjwt.ExpiredSignatureError:
            return jsonify({"error": "Token abgelaufen"}), 401
        except pyjwt.InvalidTokenError as exc:
            logger.warning(f"Ungültiges JWT: {exc}")
            return jsonify({"error": "Ungültiges Token"}), 401

        # Organisations-Kontext prüfen
        org_id = payload.get("org_id")
        if not org_id:
            return jsonify({
                "error": "Token enthält keinen Organisations-Kontext. "
                         "Bitte zuerst eine Organisation in Clerk auswählen."
            }), 403

        # Tenant aus DB laden
        tenant = get_tenant_from_db(org_id)
        if not tenant:
            return jsonify({
                "error": "Mandant nicht gefunden oder gesperrt",
                "org_id": org_id,
            }), 403

        g.tenant = tenant
        logger.debug(
            f"Tenant-Kontext gesetzt: org={tenant.org_slug} "
            f"schema={tenant.schema_name} plan={tenant.plan}"
        )
        return f(*args, **kwargs)

    return decorated
