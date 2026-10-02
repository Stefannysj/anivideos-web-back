from pathlib import Path

from tests.test_api import build_client


def test_public_catalog_supports_conditional_cache(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        first = client.get('/api/catalog')
        assert first.status_code == 200
        assert first.headers['cache-control'].startswith('public, max-age=120')
        etag = first.headers.get('etag')
        assert etag

        second = client.get('/api/catalog', headers={'If-None-Match': etag})
        assert second.status_code == 304
        assert second.content == b''
        assert second.headers.get('etag') == etag


def test_public_banners_are_compressed_when_requested(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        response = client.get('/api/banners', headers={'Accept-Encoding': 'gzip'})
        assert response.status_code == 200
        assert response.headers['cache-control'].startswith('public, max-age=300')
        assert response.headers.get('content-encoding') == 'gzip'
        assert 'Accept-Encoding' in response.headers.get('vary', '')


def test_private_health_endpoint_remains_no_store(monkeypatch, tmp_path: Path) -> None:
    with build_client(monkeypatch, tmp_path) as client:
        response = client.get('/api/health')
        assert response.status_code == 200
        assert response.headers.get('cache-control') == 'no-store'
