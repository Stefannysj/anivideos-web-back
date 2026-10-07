from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_DUMMY_PASSWORD_HASH = '$argon2id$v=19$m=65536,t=3,p=4$TAI+GfR1p+gVOCPwBW9oHg$f87jj9sX5AazNwWNELWRqERPk9qoccem7eoPe6lhetw'
_password_hasher = PasswordHasher(time_cost=3, memory_cost=65_536, parallelism=4, hash_len=32, salt_len=16)
_CSRF_SECRET = secrets.token_bytes(32)
CSRF_HEADER_NAME = 'X-CSRF-Token'


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
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def csrf_token_for_session(session_token: str) -> str:
    return hmac.new(_CSRF_SECRET, session_token.encode('utf-8'), hashlib.sha256).hexdigest()


def verify_csrf_token(session_token: str, submitted_token: str) -> bool:
    if len(submitted_token) != 64:
        return False
    return hmac.compare_digest(csrf_token_for_session(session_token), submitted_token)


def verify_password_or_dummy(password_hash: str | None, password: str) -> bool:
    return verify_password(password_hash or _DUMMY_PASSWORD_HASH, password)
