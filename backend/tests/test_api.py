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
    import app.routers.catalog as catalog
    import app.routers.banners as banners
    import app.routers.auth as auth
    import app.main as main

    importlib.reload(config)
    importlib.reload(database)
    importlib.reload(health)
    importlib.reload(catalog)
    importlib.reload(banners)
    importlib.reload(auth)
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
