from app.auth_security import generate_session_token, hash_password, hash_session_token, verify_password


def test_opaque_sessions_and_argon2_are_preserved() -> None:
    password_hash = hash_password('AniVideos2026')
    assert password_hash.startswith('$argon2id$')
    assert verify_password(password_hash, 'AniVideos2026')
    token = generate_session_token()
    assert token not in hash_session_token(token)
    assert len(hash_session_token(token)) == 64
