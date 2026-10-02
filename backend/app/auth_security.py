from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Password hashing policy is intentionally centralized so it can be upgraded without
# changing the routers or database layer.
_DUMMY_PASSWORD_HASH = '$argon2id$v=19$m=65536,t=3,p=4$TAI+GfR1p+gVOCPwBW9oHg$f87jj9sX5AazNwWNELWRqERPk9qoccem7eoPe6lhetw'
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# CSRF tokens are derived from the opaque session cookie. The process secret never
# leaves the backend and can be rotated simply by restarting the service.
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
    # The raw token is sent only through the HttpOnly cookie. SQL stores its digest.
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def csrf_token_for_session(session_token: str) -> str:
    return hmac.new(_CSRF_SECRET, session_token.encode('utf-8'), hashlib.sha256).hexdigest()


def verify_csrf_token(session_token: str, submitted_token: str) -> bool:
    if len(submitted_token) != 64:
        return False
    expected = csrf_token_for_session(session_token)
    return hmac.compare_digest(expected, submitted_token)


def verify_password_or_dummy(password_hash: str | None, password: str) -> bool:
    # A dummy hash keeps unknown-user login attempts closer to the timing profile of
    # existing-user attempts and reduces username enumeration via response timing.
    return verify_password(password_hash or _DUMMY_PASSWORD_HASH, password)
