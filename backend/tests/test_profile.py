from __future__ import annotations

from tests.test_api import build_client


REGISTER = {
    'username': 'profile_user',
    'email': 'profile@example.com',
    'password': 'AniVideos2026',
}
ORIGIN = 'http://127.0.0.1:5173'


def test_profile_requires_authentication(monkeypatch, tmp_path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.get('/api/profile').status_code == 401
        assert client.patch('/api/profile', json={'displayName': 'Stefa'}, headers={'Origin': ORIGIN}).status_code == 401


def test_profile_can_update_public_fields(monkeypatch, tmp_path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.post('/api/auth/register', json=REGISTER).status_code == 201
        response = client.patch(
            '/api/profile',
            json={'displayName': 'Stefanny S.', 'bio': 'Anime, dramas y cine para una buena noche.'},
            headers={'Origin': ORIGIN},
        )
        assert response.status_code == 200
        user = response.json()['user']
        assert user['displayName'] == 'Stefanny S.'
        assert user['bio'] == 'Anime, dramas y cine para una buena noche.'

        persisted = client.get('/api/profile')
        assert persisted.status_code == 200
        assert persisted.json()['user']['displayName'] == 'Stefanny S.'


def test_identity_change_requires_current_password(monkeypatch, tmp_path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.post('/api/auth/register', json=REGISTER).status_code == 201

        missing_password = client.patch(
            '/api/profile',
            json={'username': 'new_profile_user'},
            headers={'Origin': ORIGIN},
        )
        assert missing_password.status_code == 403

        wrong_password = client.patch(
            '/api/profile',
            json={'email': 'new@example.com', 'currentPassword': 'WrongPassword1'},
            headers={'Origin': ORIGIN},
        )
        assert wrong_password.status_code == 403

        changed = client.patch(
            '/api/profile',
            json={
                'username': 'new_profile_user',
                'email': 'new@example.com',
                'currentPassword': REGISTER['password'],
            },
            headers={'Origin': ORIGIN},
        )
        assert changed.status_code == 200
        assert changed.json()['user']['username'] == 'new_profile_user'
        assert changed.json()['user']['email'] == 'new@example.com'


def test_profile_rejects_duplicate_identity(monkeypatch, tmp_path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.post('/api/auth/register', json=REGISTER).status_code == 201
        assert client.post('/api/auth/logout', headers={'Origin': ORIGIN}).status_code == 200
        assert client.post('/api/auth/register', json={
            'username': 'other_user',
            'email': 'other@example.com',
            'password': 'OtherPass2026',
        }).status_code == 201

        conflict = client.patch(
            '/api/profile',
            json={'username': REGISTER['username'], 'currentPassword': 'OtherPass2026'},
            headers={'Origin': ORIGIN},
        )
        assert conflict.status_code == 409


def test_profile_validation_limits_bio(monkeypatch, tmp_path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.post('/api/auth/register', json=REGISTER).status_code == 201
        response = client.patch(
            '/api/profile',
            json={'bio': 'a' * 281},
            headers={'Origin': ORIGIN},
        )
        assert response.status_code == 422


def test_profile_rejects_null_identity_fields(monkeypatch, tmp_path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.post('/api/auth/register', json=REGISTER).status_code == 201
        response = client.patch(
            '/api/profile',
            json={'username': None},
            headers={'Origin': ORIGIN},
        )
        assert response.status_code == 422
