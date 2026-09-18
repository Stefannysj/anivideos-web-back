from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Argon2id is intentionally configured in one place so password storage policy can evolve later.

_DUMMY_PASSWORD_HASH = '$argon2id$v=19$m=65536,t=3,p=4$TAI+GfR1p+gVOCPwBW9oHg$f87jj9sX5AazNwWNELWRqERPk9qoccem7eoPe6lhetw'

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def generate_session_token() -> str:
    # The browser receives the opaque token; only its SHA-256 digest is persisted in SQL.
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def verify_password_or_dummy(password_hash: str | None, password: str) -> bool:
    return verify_password(password_hash or _DUMMY_PASSWORD_HASH, password)
