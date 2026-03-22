"""
BettaFish Tenant-Modul

Stellt Tenant-Isolation für Multi-Tenant-Betrieb bereit:
- JWT-Validierung via Clerk JWKS
- Tenant-Kontext (schema_name, plan, config_overrides)
- PostgreSQL search_path per Tenant (async Engine-Cache)
- TenantSettings-Wrapper für API-Key-Overrides

Verwendung:
    from tenant.middleware import require_tenant
    from tenant.context import TenantContext
    from tenant.settings_override import TenantSettings
    from flask import g

    @app.route("/api/analyse", methods=["POST"])
    @require_tenant
    def analyse():
        tenant: TenantContext = g.tenant
        # tenant.schema_name, tenant.plan, tenant.config_overrides
        ...
"""

__all__ = ["TenantContext", "require_tenant", "TenantSettings", "tenant_bp"]


def __getattr__(name: str):
    if name == "TenantContext":
        from .context import TenantContext
        return TenantContext
    if name == "require_tenant":
        from .middleware import require_tenant
        return require_tenant
    if name == "TenantSettings":
        from .settings_override import TenantSettings
        return TenantSettings
    if name == "tenant_bp":
        from .api import tenant_bp
        return tenant_bp
    raise AttributeError(f"module 'tenant' hat kein Attribut '{name}'")
