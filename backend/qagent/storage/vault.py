"""Saved sign-in details are stored encrypted (Fernet). The key comes from CREDENTIALS_KEY, or is derived from AUTH_SECRET."""
import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from qagent.config import settings


def _fernet() -> Fernet:
    seed = settings.credentials_key or settings.auth_secret
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(f"qagent-credentials:{seed}".encode()).digest()))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> Optional[str]:
    """None when the value cannot be read (the key changed): treated as not set."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None
