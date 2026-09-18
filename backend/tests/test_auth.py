from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

from tests.test_api import build_client


REGISTER = {
    'username': 'stefa_test',
    'email': 'stefa@example.com',
    'password': 'AniVideos2026',
}


def test_register_sets_http_only_session_and_me_works(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'api.db'
    with build_client(monkeypatch, tmp_path) as client:
        response = client.post('/api/auth/register', json=REGISTER)
        assert response.status_code == 201
        assert response.json()['user']['username'] == 'stefa_test'
        assert 'password' not in response.text

        set_cookie = response.headers['set-cookie'].lower()
        assert 'httponly' in set_cookie
        assert 'samesite=lax' in set_cookie
        assert 'anivideos_session=' in set_cookie

        me = client.get('/api/auth/me')
        assert me.status_code == 200
        assert me.json()['user']['email'] == 'stefa@example.com'

    with sqlite3.connect(db_path) as conn:
        row = conn.execute('SELECT password_hash FROM users WHERE email = ?', ('stefa@example.com',)).fetchone()
        assert row is not None
        assert row[0] != REGISTER['password']
        assert row[0].startswith('$argon2id$')


def test_session_database_stores_digest_not_cookie_token(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'api.db'
    with build_client(monkeypatch, tmp_path) as client:
        response = client.post('/api/auth/register', json=REGISTER)
        assert response.status_code == 201
        raw_token = client.cookies.get('anivideos_session')
        assert raw_token

    with sqlite3.connect(db_path) as conn:
        row = conn.execute('SELECT token_hash FROM auth_sessions').fetchone()
        assert row is not None
        assert row[0] != raw_token
        assert row[0] == hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def test_login_logout_and_duplicate_registration(monkeypatch, tmp_path: Path) -> None:
    origin = 'http://127.0.0.1:5173'
    with build_client(monkeypatch, tmp_path) as client:
        created = client.post('/api/auth/register', json=REGISTER)
        assert created.status_code == 201

        duplicate = client.post('/api/auth/register', json=REGISTER, headers={'Origin': origin})
        assert duplicate.status_code == 409

        logout = client.post('/api/auth/logout', headers={'Origin': origin})
        assert logout.status_code == 200
        assert client.get('/api/auth/me').status_code == 401

        invalid = client.post('/api/auth/login', json={'identifier': REGISTER['email'], 'password': 'WrongPassword1'})
        assert invalid.status_code == 401

        valid = client.post('/api/auth/login', json={'identifier': REGISTER['email'], 'password': REGISTER['password']})
        assert valid.status_code == 200
        assert valid.json()['user']['username'] == REGISTER['username']


def test_validation_does_not_echo_password(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        response = client.post('/api/auth/register', json={
            'username': 'ok_user',
            'email': 'valid@example.com',
            'password': 'secret123',
        })
        assert response.status_code == 422
        assert 'secret123' not in response.text
