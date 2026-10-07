from pathlib import Path


def test_v16_migration_defines_postgresql_categories() -> None:
    migration = (Path(__file__).parents[1] / 'alembic' / 'versions' / '001_v16_postgresql.py').read_text(encoding='utf-8')
    for category in ('anime','k-drama','j-drama','donghua','movie','ova'):
        assert category in migration
    assert 'sqlite' not in migration.lower()
