from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _key_bytes(token_enc_key: str) -> bytes:
    try:
        decoded = base64.urlsafe_b64decode(token_enc_key)
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    raw = token_enc_key.encode("utf-8")
    if len(raw) != 32:
        raise ValueError("TOKEN_ENC_KEY must be 32 bytes or base64url encoded 32 bytes")
    return raw


def encrypt_token(plaintext: str, token_enc_key: str) -> bytes:
    nonce = os.urandom(12)
    aesgcm = AESGCM(_key_bytes(token_enc_key))
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt_token(sealed: bytes, token_enc_key: str) -> str:
    nonce = sealed[:12]
    ciphertext = sealed[12:]
    aesgcm = AESGCM(_key_bytes(token_enc_key))
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")