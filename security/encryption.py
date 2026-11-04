"""
Response Encryption Module.
AES-256-GCM authenticated encryption for candidate responses stored at rest.
Uses the Python `cryptography` library (NIST-approved AES-GCM).

Key derivation: PBKDF2-HMAC-SHA256 from a passphrase stored in the local
keyring or environment variable (VISIOEXAM_ENCRYPT_KEY).
Write time per answer target: ≤ 200ms.
"""

import os
import base64
import logging
from functools import cached_property

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# PBKDF2 parameters
_SALT_ENV = "VISIOEXAM_KEY_SALT"
_PASSPHRASE_ENV = "VISIOEXAM_ENCRYPT_KEY"
_PBKDF2_ITERATIONS = 260_000
_KEY_LENGTH = 32        # 256 bits
_NONCE_LENGTH = 12      # 96-bit GCM nonce


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_LENGTH,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode())


class ResponseEncryptor:
    """
    Encrypts and decrypts short strings (exam answers) using AES-256-GCM.
    Ciphertext format: base64( nonce[12] || ciphertext || tag[16] )
    """

    def __init__(self, passphrase: str | None = None, salt: bytes | None = None):
        self._passphrase = passphrase or os.environ.get(_PASSPHRASE_ENV, "visioexam_enc_default")
        env_salt = os.environ.get(_SALT_ENV)
        if salt:
            self._salt = salt
        elif env_salt:
            self._salt = base64.b64decode(env_salt)
        else:
            # Generate a random salt on first use and persist it
            self._salt = self._load_or_create_salt()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        Returns a base64-encoded string safe for database storage.
        """
        nonce = os.urandom(_NONCE_LENGTH)
        ct = self._aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ct).decode()

    def decrypt(self, token: str) -> str:
        """
        Decrypt a base64-encoded ciphertext produced by encrypt().
        Raises ValueError on authentication failure (tampered data).
        """
        raw = base64.b64decode(token)
        nonce = raw[:_NONCE_LENGTH]
        ct = raw[_NONCE_LENGTH:]
        plaintext = self._aesgcm.decrypt(nonce, ct, None)
        return plaintext.decode()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @cached_property
    def _aesgcm(self) -> AESGCM:
        key = _derive_key(self._passphrase, self._salt)
        return AESGCM(key)

    @staticmethod
    def _salt_path():
        from pathlib import Path
        p = Path(__file__).parent.parent / "data" / ".salt"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load_or_create_salt(self) -> bytes:
        path = self._salt_path()
        if path.exists():
            return base64.b64decode(path.read_text().strip())
        salt = os.urandom(16)
        path.write_text(base64.b64encode(salt).decode())
        logger.info("Generated new encryption salt.")
        return salt
