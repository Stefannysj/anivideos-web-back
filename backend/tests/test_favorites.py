from __future__ import annotations

from pathlib import Path

from tests.test_api import build_client


REGISTER = {
    'username': 'favorite_user',
    'email': 'favorite@example.com',
    'password': 'AniVideos2026',
}
ORIGIN = 'http://127.0.0.1:5173'
CONTENT_ID = 'anime-skybound-echo'


def test_favorites_require_authentication(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.get('/api/favorites').status_code == 401
        assert client.put(f'/api/favorites/{CONTENT_ID}').status_code == 401


def test_user_can_add_list_and_remove_favorite(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        created = client.post('/api/auth/register', json=REGISTER)
        assert created.status_code == 201

        empty = client.get('/api/favorites')
        assert empty.status_code == 200
        assert empty.json()['items'] == []

        saved = client.put(f'/api/favorites/{CONTENT_ID}', headers={'Origin': ORIGIN})
        assert saved.status_code == 200
        assert saved.json() == {'contentId': CONTENT_ID, 'isFavorite': True}

        duplicate = client.put(f'/api/favorites/{CONTENT_ID}', headers={'Origin': ORIGIN})
        assert duplicate.status_code == 200

        listing = client.get('/api/favorites')
        assert listing.status_code == 200
        assert [item['id'] for item in listing.json()['items']] == [CONTENT_ID]

        removed = client.delete(f'/api/favorites/{CONTENT_ID}', headers={'Origin': ORIGIN})
        assert removed.status_code == 200
        assert removed.json() == {'contentId': CONTENT_ID, 'isFavorite': False}
        assert client.get('/api/favorites').json()['items'] == []


def test_favorites_are_isolated_per_user(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as first:
        assert first.post('/api/auth/register', json=REGISTER).status_code == 201
        assert first.put(f'/api/favorites/{CONTENT_ID}', headers={'Origin': ORIGIN}).status_code == 200

    second_register = {
        'username': 'second_user',
        'email': 'second@example.com',
        'password': 'AniVideos2026',
    }
    with build_client(monkeypatch, tmp_path) as second:
        assert second.post('/api/auth/login', json={
            'identifier': second_register['email'],
            'password': second_register['password'],
        }).status_code == 401
        assert second.post('/api/auth/register', json=second_register).status_code == 201
        assert second.get('/api/favorites').json()['items'] == []


def test_unknown_content_cannot_be_favorited(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.post('/api/auth/register', json=REGISTER).status_code == 201
        response = client.put('/api/favorites/not-in-catalog', headers={'Origin': ORIGIN})
        assert response.status_code == 404
