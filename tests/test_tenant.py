"""
Tests für das BettaFish Tenant-Modul

Getestet werden:
- crypto.py: encrypt/decrypt Roundtrip (Klartext-Modus)
- jwt_validator.py: Token-Validierung (Mock)
- middleware.py: require_tenant Dekorator (Flask-Testclient)
- settings_override.py: TenantSettings Proxy
- context.py: TenantContext Datenstruktur
"""

import os
import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest


# ─── crypto ───────────────────────────────────────────────────────────────────

_VALID_MASTER_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="  # 32 Null-Bytes in Base64


class TestCrypto(unittest.TestCase):

    def setUp(self):
        """Key-Cache zurücksetzen zwischen Tests."""
        import tenant.crypto as c
        c._cached_key = None
        c._cached_key_b64 = None

    def tearDown(self):
        os.environ.pop("DERFISH_MASTER_KEY", None)
        import tenant.crypto as c
        c._cached_key = None
        c._cached_key_b64 = None

    # ── Klartext-Modus (kein MASTER_KEY) ──────────────────────

    def test_encrypt_decrypt_roundtrip_no_master_key(self):
        """Ohne MASTER_KEY: encrypt/decrypt → Klartext erhalten."""
        from tenant.crypto import decrypt_value, encrypt_value

        plaintext = "sk-test-api-key-12345"
        enc_bytes, iv = encrypt_value(plaintext)
        self.assertEqual(decrypt_value(enc_bytes, iv), plaintext)

    def test_encrypt_produces_utf8_bytes_without_master_key(self):
        """Ohne MASTER_KEY: Klartext-Bytes + Null-IV als Sentinel."""
        from tenant.crypto import encrypt_value

        enc_bytes, iv = encrypt_value("test-key")
        self.assertEqual(enc_bytes, b"test-key")
        self.assertEqual(iv, b"\x00" * 16)

    # ── Legacy-Kompatibilität (Null-IV auch mit MASTER_KEY) ────

    def test_decrypt_legacy_null_iv_with_master_key(self):
        """Null-IV wird immer als Klartext dekodiert (Migrations-Sentinel)."""
        from tenant.crypto import decrypt_value

        os.environ["DERFISH_MASTER_KEY"] = _VALID_MASTER_KEY
        result = decrypt_value(b"legacy-plaintext", b"\x00" * 16)
        self.assertEqual(result, "legacy-plaintext")

    # ── AES-256-GCM Modus ─────────────────────────────────────

    def test_encrypt_decrypt_roundtrip_with_master_key(self):
        """Mit MASTER_KEY: AES-256-GCM Roundtrip."""
        from tenant.crypto import decrypt_value, encrypt_value

        os.environ["DERFISH_MASTER_KEY"] = _VALID_MASTER_KEY
        plaintext = "sk-prod-secret-key-xyz"
        enc_bytes, iv = encrypt_value(plaintext)

        # IV muss 12 Bytes sein (GCM-Nonce)
        self.assertEqual(len(iv), 12)
        # ciphertext != Klartext
        self.assertNotEqual(enc_bytes, plaintext.encode())
        # Entschlüsseln ergibt wieder den Klartext
        self.assertEqual(decrypt_value(enc_bytes, iv), plaintext)

    def test_different_plaintexts_produce_different_ciphertexts(self):
        """Gleicher Key, unterschiedliche Plaintexts → unterschiedliche Ciphertexts."""
        from tenant.crypto import encrypt_value

        os.environ["DERFISH_MASTER_KEY"] = _VALID_MASTER_KEY
        enc1, _ = encrypt_value("key-a")
        enc2, _ = encrypt_value("key-b")
        self.assertNotEqual(enc1, enc2)

    def test_encrypt_uses_random_iv(self):
        """Jede Verschlüsselung erzeugt eine neue IV (probabilistisch)."""
        from tenant.crypto import encrypt_value

        os.environ["DERFISH_MASTER_KEY"] = _VALID_MASTER_KEY
        _, iv1 = encrypt_value("same-plaintext")
        _, iv2 = encrypt_value("same-plaintext")
        self.assertNotEqual(iv1, iv2)

    def test_tampered_ciphertext_raises(self):
        """Modifizierter Ciphertext → InvalidTag / DecryptionError."""
        from tenant.crypto import decrypt_value, encrypt_value

        os.environ["DERFISH_MASTER_KEY"] = _VALID_MASTER_KEY
        enc_bytes, iv = encrypt_value("secret")
        tampered = bytes([enc_bytes[0] ^ 0xFF]) + enc_bytes[1:]
        with self.assertRaises(Exception):
            decrypt_value(tampered, iv)

    def test_invalid_master_key_raises_value_error(self):
        """Ungültiges Base64 in MASTER_KEY → ValueError."""
        from tenant.crypto import encrypt_value

        os.environ["DERFISH_MASTER_KEY"] = "nicht-base64!!!"
        with self.assertRaises(ValueError):
            encrypt_value("x")

    def test_wrong_length_master_key_raises_value_error(self):
        """16-Byte-Key statt 32 Bytes → ValueError."""
        import base64
        from tenant.crypto import encrypt_value

        short_key = base64.b64encode(b"\x00" * 16).decode()
        os.environ["DERFISH_MASTER_KEY"] = short_key
        with self.assertRaises(ValueError):
            encrypt_value("x")


# ─── context ──────────────────────────────────────────────────────────────────

class TestTenantContext(unittest.TestCase):

    def test_context_creation(self):
        from tenant.context import TenantContext

        ctx = TenantContext(
            tenant_id="uuid-1234",
            org_id="org_abc",
            org_slug="meine-firma",
            display_name="Meine Firma GmbH",
            schema_name="tenant_meine_firma",
            plan="pro",
            config_overrides={"QUERY_ENGINE_API_KEY": "sk-override"},
        )
        self.assertEqual(ctx.schema_name, "tenant_meine_firma")
        self.assertEqual(ctx.plan, "pro")
        self.assertEqual(ctx.config_overrides["QUERY_ENGINE_API_KEY"], "sk-override")

    def test_context_defaults_empty_overrides(self):
        from tenant.context import TenantContext

        ctx = TenantContext(
            tenant_id="uuid-1",
            org_id="org_x",
            org_slug="slug",
            display_name="Test",
            schema_name="tenant_test",
            plan="free",
        )
        self.assertEqual(ctx.config_overrides, {})


# ─── settings_override ────────────────────────────────────────────────────────

class TestTenantSettings(unittest.TestCase):

    def _make_base_settings(self):
        s = MagicMock()
        s.QUERY_ENGINE_API_KEY = "base-key"
        s.QUERY_ENGINE_BASE_URL = "https://base.example.com"
        s.QUERY_ENGINE_MODEL_NAME = "base-model"
        return s

    def test_falls_back_to_base_outside_flask_context(self):
        """Außerhalb eines Flask-Requests → Base-Settings verwenden."""
        from tenant.settings_override import TenantSettings

        base = self._make_base_settings()
        ts = TenantSettings(base)
        # Kein Flask-Kontext → RuntimeError wird abgefangen → Base-Wert
        self.assertEqual(ts.QUERY_ENGINE_API_KEY, "base-key")
        self.assertEqual(ts.QUERY_ENGINE_BASE_URL, "https://base.example.com")

    def test_override_within_flask_context(self):
        """Im Flask-Kontext mit g.tenant → Tenant-Override verwenden."""
        from flask import Flask
        from tenant.context import TenantContext
        from tenant.settings_override import TenantSettings

        app = Flask(__name__)
        base = self._make_base_settings()
        ts = TenantSettings(base)

        with app.test_request_context("/"):
            from flask import g
            g.tenant = TenantContext(
                tenant_id="uuid-1",
                org_id="org_1",
                org_slug="org-1",
                display_name="Org 1",
                schema_name="tenant_org_1",
                plan="pro",
                config_overrides={"QUERY_ENGINE_API_KEY": "tenant-override-key"},
            )
            self.assertEqual(ts.QUERY_ENGINE_API_KEY, "tenant-override-key")
            # Nicht überschriebenes Feld → Base
            self.assertEqual(ts.QUERY_ENGINE_BASE_URL, "https://base.example.com")

    def test_no_override_when_tenant_not_set(self):
        """Flask-Kontext ohne g.tenant → Base-Settings."""
        from flask import Flask
        from tenant.settings_override import TenantSettings

        app = Flask(__name__)
        base = self._make_base_settings()
        ts = TenantSettings(base)

        with app.test_request_context("/"):
            self.assertEqual(ts.QUERY_ENGINE_API_KEY, "base-key")

    def test_setattr_raises(self):
        from tenant.settings_override import TenantSettings

        base = self._make_base_settings()
        ts = TenantSettings(base)
        with self.assertRaises(AttributeError):
            ts.QUERY_ENGINE_API_KEY = "new-key"


# ─── middleware ───────────────────────────────────────────────────────────────

class TestRequireTenantDecorator(unittest.TestCase):

    def _make_app(self):
        from flask import Flask, g, jsonify
        from tenant.middleware import require_tenant

        app = Flask(__name__)

        @app.route("/protected", methods=["GET"])
        @require_tenant
        def protected():
            return jsonify({"schema": g.tenant.schema_name})

        return app

    def test_missing_auth_header_returns_401(self):
        app = self._make_app()
        client = app.test_client()
        resp = client.get("/protected")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Authentifizierung", resp.get_json()["error"])

    def test_missing_jwks_url_returns_500(self):
        app = self._make_app()
        os.environ.pop("CLERK_JWKS_URL", None)
        client = app.test_client()
        resp = client.get("/protected", headers={"Authorization": "Bearer faketoken"})
        self.assertEqual(resp.status_code, 500)

    @patch("tenant.middleware.validate_clerk_token")
    @patch("tenant.middleware.get_tenant_from_db")
    def test_valid_token_sets_g_tenant(self, mock_get_tenant, mock_validate):
        from tenant.context import TenantContext

        mock_validate.return_value = {
            "sub": "user_abc",
            "org_id": "org_test",
            "org_slug": "test-org",
        }
        mock_get_tenant.return_value = TenantContext(
            tenant_id="uuid-x",
            org_id="org_test",
            org_slug="test-org",
            display_name="Test Org",
            schema_name="tenant_test_org",
            plan="pro",
        )

        os.environ["CLERK_JWKS_URL"] = "https://example.clerk.dev/.well-known/jwks.json"
        app = self._make_app()
        client = app.test_client()
        resp = client.get("/protected", headers={"Authorization": "Bearer validtoken"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["schema"], "tenant_test_org")

    @patch("tenant.middleware.validate_clerk_token")
    def test_token_without_org_id_returns_403(self, mock_validate):
        mock_validate.return_value = {"sub": "user_abc"}  # kein org_id
        os.environ["CLERK_JWKS_URL"] = "https://example.clerk.dev/.well-known/jwks.json"
        app = self._make_app()
        client = app.test_client()
        resp = client.get("/protected", headers={"Authorization": "Bearer token"})
        self.assertEqual(resp.status_code, 403)

    @patch("tenant.middleware.validate_clerk_token")
    @patch("tenant.middleware.get_tenant_from_db")
    def test_unknown_tenant_returns_403(self, mock_get_tenant, mock_validate):
        mock_validate.return_value = {"sub": "user_abc", "org_id": "org_unknown"}
        mock_get_tenant.return_value = None
        os.environ["CLERK_JWKS_URL"] = "https://example.clerk.dev/.well-known/jwks.json"
        app = self._make_app()
        client = app.test_client()
        resp = client.get("/protected", headers={"Authorization": "Bearer token"})
        self.assertEqual(resp.status_code, 403)

    @patch("tenant.middleware.validate_clerk_token")
    def test_expired_token_returns_401(self, mock_validate):
        import jwt as pyjwt
        mock_validate.side_effect = pyjwt.ExpiredSignatureError("Token abgelaufen")
        os.environ["CLERK_JWKS_URL"] = "https://example.clerk.dev/.well-known/jwks.json"
        app = self._make_app()
        client = app.test_client()
        resp = client.get("/protected", headers={"Authorization": "Bearer expired"})
        self.assertEqual(resp.status_code, 401)
        self.assertIn("abgelaufen", resp.get_json()["error"])

    @patch("tenant.middleware.validate_clerk_token")
    def test_invalid_token_returns_401(self, mock_validate):
        import jwt as pyjwt
        mock_validate.side_effect = pyjwt.InvalidTokenError("bad signature")
        os.environ["CLERK_JWKS_URL"] = "https://example.clerk.dev/.well-known/jwks.json"
        app = self._make_app()
        client = app.test_client()
        resp = client.get("/protected", headers={"Authorization": "Bearer bad"})
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
