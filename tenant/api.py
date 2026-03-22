"""
Tenant Self-Service API (BettaFish)

Ermöglicht authentifizierten Tenants:
- Eigene API-Keys hinterlegen / aktualisieren / löschen
- Aktuellen Monatsverbrauch + Limits abfragen

Routen (alle mit @require_tenant geschützt):
    GET  /api/tenant/info            → Tenant-Info + gemaskerte Keys + Verbrauch
    PUT  /api/tenant/keys            → API-Key speichern / aktualisieren
    DELETE /api/tenant/keys/<name>   → API-Key entfernen

Erlaubte Key-Namen (ALLOWED_KEY_NAMES) schützen vor dem Speichern
beliebiger Spaltenwerte in die DB.
"""

from flask import Blueprint, g, jsonify, request
from .middleware import require_tenant
from .db import (
    delete_tenant_api_key,
    get_tenant_usage,
    list_tenant_api_keys_masked,
    upsert_tenant_api_key,
)

tenant_bp = Blueprint("tenant_self_service", __name__)

# Welche Key-Namen darf ein Tenant selbst setzen?
ALLOWED_KEY_NAMES: frozenset = frozenset({
    "INSIGHT_ENGINE_API_KEY",
    "INSIGHT_ENGINE_BASE_URL",
    "INSIGHT_ENGINE_MODEL_NAME",
    "MEDIA_ENGINE_API_KEY",
    "MEDIA_ENGINE_BASE_URL",
    "MEDIA_ENGINE_MODEL_NAME",
    "QUERY_ENGINE_API_KEY",
    "QUERY_ENGINE_BASE_URL",
    "QUERY_ENGINE_MODEL_NAME",
    "REPORT_ENGINE_API_KEY",
    "REPORT_ENGINE_BASE_URL",
    "REPORT_ENGINE_MODEL_NAME",
    "FORUM_HOST_API_KEY",
    "FORUM_HOST_BASE_URL",
    "FORUM_HOST_MODEL_NAME",
    "MINDSPIDER_API_KEY",
    "MINDSPIDER_BASE_URL",
    "MINDSPIDER_MODEL_NAME",
    "TAVILY_API_KEY",
    "BOCHA_WEB_SEARCH_API_KEY",
    "ANSPIRE_API_KEY",
})


@tenant_bp.get("/info")
@require_tenant
def tenant_info():
    """
    Gibt Tenant-Metadaten, gemaskerte API-Keys und Monatsverbrauch zurück.

    Response:
        {
          "tenant": {id, display_name, plan, org_slug},
          "keys": [{key_name, masked}],
          "usage": [{service, metric, current, limit}]
        }
    """
    tenant = g.tenant
    keys = list_tenant_api_keys_masked(tenant.tenant_id)
    usage = get_tenant_usage(tenant.tenant_id, tenant.plan)

    return jsonify({
        "tenant": {
            "id":           tenant.tenant_id,
            "display_name": tenant.display_name,
            "plan":         tenant.plan,
            "org_slug":     tenant.org_slug,
        },
        "keys":  keys,
        "usage": usage,
    })


@tenant_bp.put("/keys")
@require_tenant
def upsert_key():
    """
    Speichert oder aktualisiert einen API-Key des Tenants.

    Body (JSON):
        {
          "key_name": "INSIGHT_ENGINE_API_KEY",
          "value":    "sk-..."
        }

    Returns 400 wenn key_name nicht erlaubt oder value leer.
    """
    tenant = g.tenant
    body = request.get_json(silent=True) or {}

    key_name = body.get("key_name", "").strip()
    value = body.get("value", "").strip()

    if not key_name:
        return jsonify({"error": "key_name fehlt"}), 400
    if key_name not in ALLOWED_KEY_NAMES:
        return jsonify({"error": f"key_name '{key_name}' nicht erlaubt"}), 400
    if not value:
        return jsonify({"error": "value darf nicht leer sein"}), 400
    if len(value) > 512:
        return jsonify({"error": "value zu lang (max. 512 Zeichen)"}), 400

    upsert_tenant_api_key(tenant.tenant_id, key_name, value)
    return jsonify({"ok": True, "key_name": key_name}), 200


@tenant_bp.delete("/keys/<key_name>")
@require_tenant
def delete_key(key_name: str):
    """
    Löscht einen API-Key des Tenants.

    Returns 404 wenn der Key nicht vorhanden war.
    """
    tenant = g.tenant
    key_name = key_name.strip()

    if key_name not in ALLOWED_KEY_NAMES:
        return jsonify({"error": f"key_name '{key_name}' nicht erlaubt"}), 400

    deleted = delete_tenant_api_key(tenant.tenant_id, key_name)
    if not deleted:
        return jsonify({"error": "Key nicht gefunden"}), 404
    return jsonify({"ok": True, "key_name": key_name}), 200
