from __future__ import annotations

from pathlib import Path

from tests.test_api import build_client, mutation_headers

ORIGIN = 'http://127.0.0.1:5173'
BANNER_A = 'stellar-pulse'
BANNER_B = 'signal-zero'
FIRST = {
    'username': 'comment_owner',
    'email': 'comment-owner@example.com',
    'password': 'AniVideos2026',
}
SECOND = {
    'username': 'comment_second',
    'email': 'comment-second@example.com',
    'password': 'AniVideos2026',
}


def test_comments_are_public_but_publishing_requires_auth(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        listing = client.get(f'/api/banners/{BANNER_A}/comments')
        assert listing.status_code == 200
        assert listing.json()['items'] == []
        assert client.post(
            f'/api/banners/{BANNER_A}/comments',
            json={'body': 'Hola'},
        ).status_code == 401


def test_authenticated_user_can_publish_and_delete_own_comment(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.post('/api/auth/register', json=FIRST).status_code == 201
        created = client.post(
            f'/api/banners/{BANNER_A}/comments',
            json={'body': '  Gran banner.  '},
            headers=mutation_headers(client),
        )
        assert created.status_code == 201
        payload = created.json()
        assert payload['body'] == 'Gran banner.'
        assert payload['author']['username'] == FIRST['username']
        assert payload['isOwner'] is True

        listing = client.get(f'/api/banners/{BANNER_A}/comments')
        assert listing.status_code == 200
        assert listing.json()['items'][0]['id'] == payload['id']
        assert listing.json()['items'][0]['isOwner'] is True

        removed = client.delete(
            f"/api/banners/{BANNER_A}/comments/{payload['id']}",
            headers=mutation_headers(client),
        )
        assert removed.status_code == 200
        assert client.get(f'/api/banners/{BANNER_A}/comments').json()['items'] == []


def test_comments_belong_to_exactly_one_banner(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.post('/api/auth/register', json=FIRST).status_code == 201
        assert client.post(
            f'/api/banners/{BANNER_A}/comments',
            json={'body': 'Solo Stellar'},
            headers=mutation_headers(client),
        ).status_code == 201

        assert len(client.get(f'/api/banners/{BANNER_A}/comments').json()['items']) == 1
        assert client.get(f'/api/banners/{BANNER_B}/comments').json()['items'] == []


def test_user_cannot_delete_another_users_comment(monkeypatch, tmp_path: Path) -> None:
    db_tmp = tmp_path
    with build_client(monkeypatch, db_tmp) as owner:
        assert owner.post('/api/auth/register', json=FIRST).status_code == 201
        created = owner.post(
            f'/api/banners/{BANNER_A}/comments',
            json={'body': 'Comentario protegido'},
            headers=mutation_headers(owner),
        )
        comment_id = created.json()['id']

    with build_client(monkeypatch, db_tmp) as other:
        assert other.post('/api/auth/register', json=SECOND).status_code == 201
        denied = other.delete(
            f'/api/banners/{BANNER_A}/comments/{comment_id}',
            headers=mutation_headers(other),
        )
        assert denied.status_code == 404
        listing = other.get(f'/api/banners/{BANNER_A}/comments')
        assert listing.json()['items'][0]['isOwner'] is False


def test_comment_validation_and_unknown_banner(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.post('/api/auth/register', json=FIRST).status_code == 201
        empty = client.post(
            f'/api/banners/{BANNER_A}/comments',
            json={'body': '   '},
            headers=mutation_headers(client),
        )
        assert empty.status_code == 422

        too_long = client.post(
            f'/api/banners/{BANNER_A}/comments',
            json={'body': 'x' * 1001},
            headers=mutation_headers(client),
        )
        assert too_long.status_code == 422

        missing = client.get('/api/banners/banner-inexistente/comments')
        assert missing.status_code == 404
