"""v16 PostgreSQL baseline and real-content schema.

Revision ID: 001_v16_postgresql
Revises: None
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_v16_postgresql'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'content_items',
        sa.Column('id', sa.String(120), primary_key=True),
        sa.Column('source', sa.String(16), nullable=False),
        sa.Column('external_id', sa.String(64), nullable=False),
        sa.Column('category', sa.String(24), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('original_title', sa.String(200), nullable=True),
        sa.Column('synopsis', sa.Text(), nullable=False, server_default=''),
        sa.Column('genres', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('cover_url', sa.Text(), nullable=False),
        sa.Column('backdrop_url', sa.Text(), nullable=True),
        sa.Column('studio', sa.String(160), nullable=True),
        sa.Column('episodes', sa.Integer(), nullable=True),
        sa.Column('score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('release_year', sa.Integer(), nullable=True),
        sa.Column('maturity', sa.String(24), nullable=False, server_default='NR'),
        sa.Column('format', sa.String(32), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('origin', sa.String(80), nullable=False, server_default=''),
        sa.Column('trailer_youtube_id', sa.String(32), nullable=True),
        sa.Column('official_url', sa.Text(), nullable=True),
        sa.Column('platform_links', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('provider_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source IN ('anilist','tmdb')", name='ck_content_source'),
        sa.CheckConstraint("category IN ('anime','k-drama','j-drama','donghua','movie','ova')", name='ck_content_category'),
        sa.CheckConstraint('score >= 0 AND score <= 10', name='ck_content_score'),
        sa.UniqueConstraint('source', 'external_id', name='uq_content_provider_id'),
    )
    op.create_index('ix_content_category_year_score', 'content_items', ['category', 'release_year', 'score'])
    op.create_index('ix_content_title', 'content_items', ['title'])

    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('username', sa.String(40), nullable=False, unique=True),
        sa.Column('email', sa.String(254), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('display_name', sa.String(60), nullable=True),
        sa.Column('bio', sa.String(280), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute('CREATE UNIQUE INDEX ix_users_username_lower ON users (lower(username))')
    op.execute('CREATE UNIQUE INDEX ix_users_email_lower ON users (lower(email))')

    op.create_table(
        'featured_banners',
        sa.Column('id', sa.String(140), primary_key=True),
        sa.Column('content_id', sa.String(120), sa.ForeignKey('content_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('eyebrow', sa.String(120), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_featured_active_order', 'featured_banners', ['is_active', 'display_order'])

    op.create_table(
        'favorites',
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('content_id', sa.String(120), sa.ForeignKey('content_items.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_favorites_user_created', 'favorites', ['user_id', 'created_at'])

    op.create_table(
        'banner_comments',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('banner_id', sa.String(140), sa.ForeignKey('featured_banners.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('body', sa.String(1000), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_banner_comments_banner_created', 'banner_comments', ['banner_id', 'created_at'])
    op.create_index('ix_banner_comments_user', 'banner_comments', ['user_id'])

    op.create_table(
        'auth_sessions',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expires_at', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_auth_sessions_user', 'auth_sessions', ['user_id'])
    op.create_index('ix_auth_sessions_expires', 'auth_sessions', ['expires_at'])


def downgrade() -> None:
    op.drop_table('auth_sessions')
    op.drop_table('banner_comments')
    op.drop_table('favorites')
    op.drop_table('featured_banners')
    op.drop_table('users')
    op.drop_table('content_items')
