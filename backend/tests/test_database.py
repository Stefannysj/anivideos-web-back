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


def test_initialize_database_migrates_stage07_users_table(tmp_path: Path) -> None:
    import sqlite3
    from app.database import initialize_database

    db_path = tmp_path / 'stage07.db'
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                avatar_url TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()

    initialize_database(db_path)
    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
    assert {'display_name', 'bio'} <= columns


def test_catalog_database_filters_are_composable(tmp_path: Path) -> None:
    database = tmp_path / 'filters.db'
    initialize_database(database)

    rows = list_content(
        category='movie',
        database_path=database,
        year=2026,
        min_score=8.5,
        sort='score-desc',
    )
    assert [row['title'] for row in rows] == ['Crimson Orbit', 'Final Frame', 'Last Ember']

    assert [row['title'] for row in list_content(database_path=database, search='winter')] == ['Winter Letter']
    assert len(list_content(database_path=database, genre='Misterio')) == 5
    assert list_content(database_path=database, search='%') == []
