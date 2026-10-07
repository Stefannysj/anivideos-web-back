"""v17 accounts, discovery, reviews and calendar features.

Revision ID: 002_v17_accounts_features
Revises: 001_v16_postgresql
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '002_v17_accounts_features'
down_revision = '001_v16_postgresql'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL-native fuzzy search used by autocomplete and tolerant catalog search.
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    op.add_column('content_items', sa.Column('season', sa.String(12), nullable=True))
    op.add_column('content_items', sa.Column('season_year', sa.Integer(), nullable=True))
    op.add_column('content_items', sa.Column('next_airing_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('content_items', sa.Column('next_episode_number', sa.Integer(), nullable=True))
    op.create_index('ix_content_next_airing', 'content_items', ['next_airing_at'])
    op.create_index('ix_content_season_year', 'content_items', ['season', 'season_year'])
    op.execute('CREATE INDEX ix_content_title_trgm ON content_items USING gin (title gin_trgm_ops)')
    op.execute("CREATE INDEX ix_content_original_title_trgm ON content_items USING gin ((COALESCE(original_title, '')) gin_trgm_ops)")

    op.create_table(
        'user_library',
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('content_id', sa.String(120), sa.ForeignKey('content_items.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('progress_status', sa.String(16), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "progress_status IS NULL OR progress_status IN ('watching','completed','planned')",
            name='ck_user_library_progress_status',
        ),
        sa.CheckConstraint(
            'is_favorite OR progress_status IS NOT NULL',
            name='ck_user_library_has_state',
        ),
    )
    op.create_index('ix_user_library_user_updated', 'user_library', ['user_id', 'updated_at'])
    op.create_index('ix_user_library_content', 'user_library', ['content_id'])
    op.execute(
        """
        INSERT INTO user_library (user_id, content_id, is_favorite, progress_status, created_at, updated_at)
        SELECT user_id, content_id, TRUE, NULL, created_at, created_at
        FROM favorites
        ON CONFLICT (user_id, content_id) DO NOTHING
        """
    )
    op.drop_table('favorites')

    op.create_table(
        'reviews',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content_id', sa.String(120), sa.ForeignKey('content_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rating', sa.SmallInteger(), nullable=False),
        sa.Column('body', sa.String(2000), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('rating >= 1 AND rating <= 10', name='ck_reviews_rating'),
        sa.UniqueConstraint('user_id', 'content_id', name='uq_reviews_user_content'),
    )
    op.create_index('ix_reviews_content_updated', 'reviews', ['content_id', 'updated_at'])
    op.create_index('ix_reviews_user', 'reviews', ['user_id'])

    op.create_table(
        'review_reports',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('review_id', sa.BigInteger(), sa.ForeignKey('reviews.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reporter_user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason', sa.String(16), nullable=False),
        sa.Column('detail', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("reason IN ('spam','abuse','spoiler','other')", name='ck_review_reports_reason'),
        sa.UniqueConstraint('review_id', 'reporter_user_id', name='uq_review_reports_review_reporter'),
    )
    op.create_index('ix_review_reports_review', 'review_reports', ['review_id'])


def downgrade() -> None:
    op.drop_table('review_reports')
    op.drop_table('reviews')

    op.create_table(
        'favorites',
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('content_id', sa.String(120), sa.ForeignKey('content_items.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        """
        INSERT INTO favorites (user_id, content_id, created_at)
        SELECT user_id, content_id, created_at FROM user_library WHERE is_favorite = TRUE
        """
    )
    op.drop_table('user_library')

    op.execute('DROP INDEX IF EXISTS ix_content_original_title_trgm')
    op.execute('DROP INDEX IF EXISTS ix_content_title_trgm')
    op.drop_index('ix_content_season_year', table_name='content_items')
    op.drop_index('ix_content_next_airing', table_name='content_items')
    op.drop_column('content_items', 'next_episode_number')
    op.drop_column('content_items', 'next_airing_at')
    op.drop_column('content_items', 'season_year')
    op.drop_column('content_items', 'season')
