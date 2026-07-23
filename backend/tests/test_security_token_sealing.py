"""Sealed OAuth tokens survive a cryptography upgrade (D-149 follow-up).

auth_identities.access_token_enc holds each user's GitHub OAuth token, AES-GCM
sealed by app.core.security.encrypt_token. D-149 raised cryptography from the
43.x-45.x range (what production rows were sealed with) to >=48.0.1. A
same-version round-trip cannot prove that rows sealed by the OLD library still
open under the NEW one -- and if they did not, every user with a stored OAuth
identity would be locked out at cutover.

So these GOLDEN CIPHERTEXTS were produced by the REAL encrypt_token code path
running under the OLD versions (43.0.1 and 45.0.1..45.0.7 share the wire format;
45.0.7 is the version CI resolved), captured once, and hardcoded here. The test
opens them with WHATEVER cryptography is installed now. It is permanent on
purpose: a future bump that silently broke stored credentials would fail here
instead of in production.

Framing under test (security.py): sealed = nonce(12) || AESGCM.encrypt(nonce,
plaintext, None). No AAD, no version tag -- which is exactly why it is
version-independent, but that is the thing being PROVEN, not assumed.
"""

from __future__ import annotations

import base64

import pytest
from cryptography.exceptions import InvalidTag

from app.core.security import decrypt_token, encrypt_token

# The key and plaintext the golden vectors below were sealed with. The key is a
# literal 32-byte string (not production's); the point is cross-version
# ciphertext compatibility, which does not depend on the specific key.
_KEY = "an-example-32-byte-token-enc-key"
_PLAINTEXT = "gho_ExampleGitHubOAuthAccessToken_abc123"

# base64(nonce || AESGCM ciphertext), produced by encrypt_token() running under
# each OLD cryptography version. Regenerate ONLY by sealing under that old
# version again; never by re-sealing under the current one (that would defeat
# the whole test).
_GOLDEN_SEALED = {
    "43.0.1": "CL5+qEv6of7VJNSgDQOQ+tssoqxspQllx5H0sPE/M+lv+zcYJbkmu+jx71NqPdWOxaiBe01Huo3SwKsp2Dz3EFoLRQI=",  # noqa: E501
    "45.0.7": "+hUCTe028fkDtEUYji8y6yeLP03n6BygF73cA6k/b9MozCq1+SRpDJw0yFXCGnkjE1I6xAlp+Jn2zBs8LloEcPpnKs4=",  # noqa: E501
}


@pytest.mark.parametrize("sealed_by", sorted(_GOLDEN_SEALED))
def test_tokens_sealed_by_old_cryptography_still_open(sealed_by: str) -> None:
    """A token sealed by cryptography {sealed_by} opens under the version
    installed now. This is the anti-lockout guarantee for the D-149 bump and
    every future one."""
    sealed = base64.b64decode(_GOLDEN_SEALED[sealed_by])
    assert decrypt_token(sealed, _KEY) == _PLAINTEXT


def test_the_regression_is_not_vacuous_wrong_key_is_rejected() -> None:
    """Negative (house rule): the golden ciphertext must genuinely be
    AUTHENTICATED, not merely decoded. A wrong key must raise InvalidTag rather
    than return plausible bytes -- otherwise the passing test above would prove
    nothing about integrity."""
    sealed = base64.b64decode(_GOLDEN_SEALED["45.0.7"])
    wrong_key = "a-different-32-byte-token-enckey"
    assert len(wrong_key) == 32
    with pytest.raises(InvalidTag):
        decrypt_token(sealed, wrong_key)


def test_tampered_ciphertext_is_rejected() -> None:
    """Negative: flip one byte of a golden ciphertext and it must fail the GCM
    tag, proving the test would catch a corrupted or truncated stored token."""
    sealed = bytearray(base64.b64decode(_GOLDEN_SEALED["45.0.7"]))
    sealed[-1] ^= 0x01  # corrupt the last byte of the auth tag
    with pytest.raises(InvalidTag):
        decrypt_token(bytes(sealed), _KEY)


def test_current_version_round_trip_still_works() -> None:
    """Sanity: sealing and opening under the current version is unbroken."""
    sealed = encrypt_token(_PLAINTEXT, _KEY)
    assert decrypt_token(sealed, _KEY) == _PLAINTEXT
