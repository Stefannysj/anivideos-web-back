from pathlib import Path
import importlib

from fastapi.testclient import TestClient


def build_client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv('ANIVIDEOS_DB_PATH', str(tmp_path / 'api.db'))
    monkeypatch.setenv('ANIVIDEOS_ALLOWED_HOSTS', 'testserver,127.0.0.1,localhost')
    monkeypatch.setenv('ANIVIDEOS_ALLOWED_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173')
    monkeypatch.setenv('ANIVIDEOS_COOKIE_SECURE', '0')

    import app.config as config
    import app.database as database
    import app.routers.health as health
    import app.routers.favorites as favorites
    import app.routers.comments as comments
    import app.routers.catalog as catalog
    import app.routers.banners as banners
    import app.routers.auth as auth
    import app.routers.profile as profile
    import app.main as main

    importlib.reload(config)
    importlib.reload(database)
    importlib.reload(health)
    importlib.reload(favorites)
    importlib.reload(comments)
    importlib.reload(catalog)
    importlib.reload(banners)
    importlib.reload(auth)
    importlib.reload(profile)
    main = importlib.reload(main)
    return TestClient(main.app)


def test_health_catalog_and_banners(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        health_response = client.get('/api/health')
        assert health_response.status_code == 200
        assert health_response.json()['status'] == 'ok'
        assert health_response.json()['database'] == 'ok'

        catalog_response = client.get('/api/catalog')
        assert catalog_response.status_code == 200
        assert len(catalog_response.json()['items']) == 24

        anime = client.get('/api/catalog', params={'category': 'anime'})
        assert anime.status_code == 200
        assert len(anime.json()['items']) == 6

        banners_response = client.get('/api/banners')
        assert banners_response.status_code == 200
        assert len(banners_response.json()['items']) == 4


def test_catalog_rejects_unknown_category(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        response = client.get('/api/catalog', params={'category': 'invalid'})
        assert response.status_code == 422
        assert response.json()['error']['code'] == 'VALIDATION_ERROR'


def test_catalog_search_filters_and_sorting(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        title_search = client.get('/api/catalog', params={'q': 'winter'})
        assert title_search.status_code == 200
        assert [item['title'] for item in title_search.json()['items']] == ['Winter Letter']

        filtered = client.get(
            '/api/catalog',
            params={
                'category': 'movie',
                'year': 2026,
                'minScore': 8.5,
                'sort': 'score-desc',
            },
        )
        assert filtered.status_code == 200
        items = filtered.json()['items']
        assert [item['title'] for item in items] == ['Crimson Orbit', 'Final Frame', 'Last Ember']

        genre = client.get('/api/catalog', params={'genre': 'Romance', 'sort': 'title-asc'})
        assert genre.status_code == 200
        assert [item['title'] for item in genre.json()['items']] == ['Midnight Recipe', 'Paper Hearts', 'Winter Letter']


def test_catalog_search_bounds_and_literal_wildcards(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        assert client.get('/api/catalog', params={'minScore': 11}).status_code == 422
        assert client.get('/api/catalog', params={'year': 1800}).status_code == 422
        assert client.get('/api/catalog', params={'sort': 'invalid'}).status_code == 422

        literal_wildcard = client.get('/api/catalog', params={'q': '%'})
        assert literal_wildcard.status_code == 200
        assert literal_wildcard.json()['items'] == []


def test_catalog_detail_by_id(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        response = client.get('/api/catalog/anime-skybound-echo')
        assert response.status_code == 200
        payload = response.json()
        assert payload['id'] == 'anime-skybound-echo'
        assert payload['title'] == 'Skybound Echo'
        assert payload['category'] == 'anime'
        assert payload['synopsis']
        assert payload['origin'] == 'Japon'
        assert payload['status'] == 'En emision'

        missing = client.get('/api/catalog/not-a-real-title')
        assert missing.status_code == 404

        invalid = client.get('/api/catalog/INVALID_ID')
        assert invalid.status_code == 422
