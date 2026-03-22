"""
API-Key Verschlüsselung / Entschlüsselung — AES-256-GCM

Verschlüsselungsschema:
    - Algorithmus:  AES-256-GCM (authenticated encryption)
    - Schlüssel:    32 Bytes, Base64url-kodiert in DERFISH_MASTER_KEY
    - Nonce/IV:     12 zufällige Bytes (GCM-Standard; os.urandom)
    - Tag:          16 Bytes, von AESGCM automatisch an Ciphertext angehängt
    - DB-Spalten:   encrypted_value BYTEA  (ciphertext + 16-Byte-Tag)
                    iv              BYTEA  (12 Bytes)

Rückwärtskompatibilität (Migration von Phase 1c):
    iv == b"\\x00" * 16  →  Klartext-Eintrag (noch nicht migriert)
    Alle neuen Einträge werden mit AES-256-GCM gespeichert.

Entwicklungsmodus (kein DERFISH_MASTER_KEY):
    encrypt_value() gibt (plaintext.encode(), b"\\x00" * 16) zurück.
    decrypt_value() erkennt Null-IV und gibt Klartext zurück.
    → Damit bleibt die lokale Entwicklung ohne Key möglich.

Master-Key generieren (einmalig auf dem Server):
    python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
    # → z.B. "3q2+79bp..." → in .env.adminfish / .env.bettafish setzen
"""

import base64
import os

# ─── Interner Key-Cache ────────────────────────────────────────────────────────

_cached_key: bytes | None = None
_cached_key_b64: str | None = None


def _get_master_key() -> bytes:
    """
    Liest und cached den Master-Key aus DERFISH_MASTER_KEY.

    Raises:
        ValueError: Wenn der Key fehlt oder nicht 32 Bytes ergibt.
    """
    global _cached_key, _cached_key_b64

    b64 = os.environ.get("DERFISH_MASTER_KEY", "")
    if not b64:
        raise ValueError(
            "DERFISH_MASTER_KEY ist nicht gesetzt. "
            "Setze ihn oder entferne verschlüsselte Werte aus der DB."
        )
    if b64 == _cached_key_b64 and _cached_key is not None:
        return _cached_key

    try:
        key = base64.b64decode(b64)
    except Exception as exc:
        raise ValueError(f"DERFISH_MASTER_KEY ist kein gültiges Base64: {exc}") from exc

    if len(key) != 32:
        raise ValueError(
            f"DERFISH_MASTER_KEY muss nach Base64-Dekodierung 32 Bytes ergeben "
            f"(ist {len(key)} Bytes)."
        )

    _cached_key = key
    _cached_key_b64 = b64
    return key


# ─── Public API ───────────────────────────────────────────────────────────────

def encrypt_value(plaintext: str) -> tuple[bytes, bytes]:
    """
    Verschlüsselt einen API-Key für die Datenbank.

    Mit DERFISH_MASTER_KEY:
        AES-256-GCM, 12-Byte-Nonce, ciphertext+tag in encrypted_value.

    Ohne DERFISH_MASTER_KEY (Entwicklung):
        Klartext-Bytes + 16-Null-Bytes-IV (kein echtes Geheimnis).

    Returns:
        (encrypted_value_bytes, iv_bytes)
    """
    master_key_b64 = os.environ.get("DERFISH_MASTER_KEY", "")
    if not master_key_b64:
        return plaintext.encode("utf-8"), b"\x00" * 16

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _get_master_key()
    iv = os.urandom(12)
    ciphertext_with_tag = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)
    return ciphertext_with_tag, iv


def decrypt_value(encrypted_value: bytes, iv: bytes) -> str:
    """
    Entschlüsselt einen gespeicherten API-Key.

    iv == b"\\x00" * 16  →  Legacy-Klartext (Phase 1c, Null-IV-Sentinel)
    iv == 12 Bytes       →  AES-256-GCM (benötigt DERFISH_MASTER_KEY)

    Args:
        encrypted_value: BYTEA aus der Datenbank (ciphertext+tag oder Klartext)
        iv:              Nonce (12 Bytes) oder Null-Sentinel (16 Bytes)

    Returns:
        Klartext-API-Key

    Raises:
        ValueError:  MASTER_KEY fehlt oder ist ungültig
        cryptography.exceptions.InvalidTag: Ciphertext manipuliert oder falscher Key
    """
    # Legacy-Sentinel: Null-IV = Klartext aus Phase 1c
    if iv == bytes(16):
        return encrypted_value.decode("utf-8")

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _get_master_key()
    plaintext_bytes = AESGCM(key).decrypt(iv, encrypted_value, None)
    return plaintext_bytes.decode("utf-8")


def generate_master_key() -> str:
    """
    Generiert einen neuen 32-Byte Master-Key als Base64-String.

    Nur für initiales Setup auf dem Server. Den Wert in
    DERFISH_MASTER_KEY (Env-Variable) hinterlegen und sicher aufbewahren.

    Returns:
        Base64-kodierter 32-Byte-Zufallsschlüssel
    """
    return base64.b64encode(os.urandom(32)).decode("ascii")
