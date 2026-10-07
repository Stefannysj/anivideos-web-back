from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.providers.anilist import map_media
from app.providers.tmdb import map_details
from app.schemas import LibraryStatusRequest, ReviewCreateRequest, ReviewReportRequest


def test_anilist_calendar_fields_are_mapped() -> None:
    item = map_media({
        'id': 99,
        'title': {'english': 'Example'},
        'coverImage': {'large': 'https://s4.anilist.co/a.jpg'},
        'season': 'FALL',
        'seasonYear': 2026,
        'nextAiringEpisode': {'airingAt': 1791230400, 'episode': 7},
    })
    assert item['season'] == 'fall'
    assert item['season_year'] == 2026
    assert item['next_episode_number'] == 7
    assert isinstance(item['next_airing_at'], datetime)
    assert item['next_airing_at'].tzinfo == timezone.utc


def test_tmdb_next_episode_is_mapped() -> None:
    item = map_details({
        'id': 101,
        'name': 'Drama',
        'original_name': 'Drama',
        'first_air_date': '2026-10-01',
        'poster_path': '/a.jpg',
        'vote_average': 8,
        'genres': [],
        'status': 'Returning Series',
        'next_episode_to_air': {'air_date': '2026-10-08', 'episode_number': 3},
        'videos': {'results': []},
        'watch/providers': {'results': {}},
    }, category='k-drama', media_type='tv', region='PE')
    assert item['season'] == 'fall'
    assert item['next_episode_number'] == 3
    assert item['next_airing_at'] is not None


def test_library_status_contract() -> None:
    assert LibraryStatusRequest(status='watching').status == 'watching'
    assert LibraryStatusRequest(status=None).status is None
    with pytest.raises(ValidationError):
        LibraryStatusRequest(status='invalid')


def test_review_contracts_are_bounded() -> None:
    assert ReviewCreateRequest(rating=8, body='Buena serie').rating == 8
    with pytest.raises(ValidationError):
        ReviewCreateRequest(rating=11, body='No')
    with pytest.raises(ValidationError):
        ReviewCreateRequest(rating=8, body='x' * 2001)


def test_review_report_reasons_are_restricted() -> None:
    assert ReviewReportRequest(reason='spoiler', detail='Sin aviso').reason == 'spoiler'
    with pytest.raises(ValidationError):
        ReviewReportRequest(reason='copyright')
