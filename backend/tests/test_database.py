from pathlib import Path

from app.database import database_is_healthy, initialize_database, list_banners, list_content


def test_database_is_initialized_with_seed_data(tmp_path: Path) -> None:
    database = tmp_path / 'test.db'
    initialize_database(database)

    assert database_is_healthy(database)
    assert len(list_content(database_path=database)) == 24
    assert len(list_content('anime', database)) == 6
    assert len(list_banners(database)) == 4


def test_invalid_category_value_is_parameterized(tmp_path: Path) -> None:
    database = tmp_path / 'test.db'
    initialize_database(database)

    rows = list_content("anime' OR 1=1 --", database)
    assert rows == []
