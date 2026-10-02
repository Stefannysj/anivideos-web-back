from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from app.auth_security import hash_password
from app.config import load_settings
from app.database import create_auth_session, create_user, initialize_database
from tests.test_api import build_client, mutation_headers

ORIGIN = 'http://127.0.0.1:5173'
REGISTER = {
    'username': 'security_user',
    'email': 'security@example.com',
    'password': 'AniVideos2026',
}


def test_security_headers_and_minimal_health_payload(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        response = client.get('/api/health')
        assert response.status_code == 200
        assert response.json() == {'status': 'ok', 'service': 'anivideos-api'}
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['x-frame-options'] == 'DENY'
        assert response.headers['referrer-policy'] == 'no-referrer'
        assert "default-src 'none'" in response.headers['content-security-policy']
        assert response.headers['cache-control'] == 'no-store'
        assert len(response.headers['x-request-id']) == 24


def test_csrf_is_required_for_authenticated_writes(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.post('/api/auth/register', json=REGISTER).status_code == 201

        missing = client.put('/api/favorites/anime-skybound-echo', headers={'Origin': ORIGIN})
        assert missing.status_code == 403
        assert missing.json()['error']['code'] == 'REQUEST_REJECTED'

        invalid = client.put(
            '/api/favorites/anime-skybound-echo',
            headers={'Origin': ORIGIN, 'X-CSRF-Token': '0' * 64},
        )
        assert invalid.status_code == 403

        accepted = client.put('/api/favorites/anime-skybound-echo', headers=mutation_headers(client))
        assert accepted.status_code == 200


def test_cross_site_origin_and_fetch_metadata_are_rejected(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        evil_origin = client.post(
            '/api/auth/register',
            json=REGISTER,
            headers={'Origin': 'https://evil.example'},
        )
        assert evil_origin.status_code == 403

        cross_site = client.post(
            '/api/auth/register',
            json=REGISTER,
            headers={'Sec-Fetch-Site': 'cross-site'},
        )
        assert cross_site.status_code == 403


def test_json_endpoints_reject_wrong_content_type(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        response = client.post(
            '/api/auth/login',
            content='identifier=a&password=b',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        assert response.status_code == 415
        assert response.json()['error']['code'] == 'UNSUPPORTED_MEDIA_TYPE'


def test_unknown_request_fields_are_rejected(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        payload = {**REGISTER, 'isAdmin': True}
        response = client.post('/api/auth/register', json=payload)
        assert response.status_code == 422
        assert 'isAdmin' in response.text
        assert REGISTER['password'] not in response.text


def test_request_body_limit_rejects_oversized_payload(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        response = client.post(
            '/api/auth/register',
            content=b'x' * 300_000,
            headers={'Content-Type': 'application/json'},
        )
        assert response.status_code == 413
        assert response.json()['error']['code'] == 'PAYLOAD_TOO_LARGE'


def test_plain_text_fields_reject_control_characters(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.post('/api/auth/register', json=REGISTER).status_code == 201
        response = client.patch(
            '/api/profile',
            json={'bio': 'texto\u202econ control'},
            headers=mutation_headers(client),
        )
        assert response.status_code == 422


def test_session_store_enforces_per_user_cap(tmp_path: Path) -> None:
    database = tmp_path / 'sessions.db'
    initialize_database(database)
    user = create_user('session_user', 'session@example.com', hash_password('AniVideos2026'), database)
    expires = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())

    for index in range(4):
        create_auth_session(int(user['id']), f'{index:064x}', expires, database, max_sessions=2)

    with sqlite3.connect(database) as conn:
        rows = conn.execute('SELECT token_hash FROM auth_sessions WHERE user_id = ?', (user['id'],)).fetchall()
    assert len(rows) == 2
    assert {row[0] for row in rows} == {f'{2:064x}', f'{3:064x}'}


def test_production_configuration_rejects_insecure_cookie(monkeypatch) -> None:
    monkeypatch.setenv('ANIVIDEOS_ENV', 'production')
    monkeypatch.setenv('ANIVIDEOS_COOKIE_SECURE', '0')
    monkeypatch.setenv('ANIVIDEOS_ALLOWED_ORIGINS', 'https://app.example.com')
    with pytest.raises(RuntimeError, match='COOKIE_SECURE'):
        load_settings()
