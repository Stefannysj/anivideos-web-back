from pathlib import Path


def test_v17_migration_adds_library_reviews_search_and_calendar() -> None:
    migration = (Path(__file__).parents[1] / 'alembic' / 'versions' / '002_v17_accounts_features.py').read_text(encoding='utf-8')
    for expected in ('pg_trgm', 'user_library', 'reviews', 'review_reports', 'next_airing_at', 'season_year'):
        assert expected in migration
    assert 'favorites' in migration  # existing favorites are migrated before the table is removed
