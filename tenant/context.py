"""
Tenant-Kontext-Datenstruktur

Wird pro Request in flask.g.tenant gespeichert.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class TenantContext:
    """
    Enthält alle mandantenspezifischen Daten für einen Request.

    Attribute:
        tenant_id:        UUID aus shared.tenants
        org_id:           Clerk Organization ID (z.B. "org_abc123")
        org_slug:         Clerk Organization Slug (z.B. "meine-firma")
        display_name:     Anzeigename der Organisation
        schema_name:      PostgreSQL-Schema (z.B. "tenant_meine_firma")
        plan:             Tarif (free / starter / pro / enterprise)
        config_overrides: Mapping von Settings-Key → Klartext-Wert
                          (z.B. {"QUERY_ENGINE_API_KEY": "sk-..."})
    """

    tenant_id: str
    org_id: str
    org_slug: str
    display_name: str
    schema_name: str
    plan: str
    config_overrides: Dict[str, str] = field(default_factory=dict)
