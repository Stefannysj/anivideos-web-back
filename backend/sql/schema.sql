PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS content_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 160),
    category TEXT NOT NULL CHECK(category IN ('anime', 'k-drama', 'series', 'movie')),
    category_label TEXT NOT NULL CHECK(length(category_label) BETWEEN 1 AND 40),
    release_year INTEGER NOT NULL CHECK(release_year BETWEEN 1900 AND 2200),
    score REAL NOT NULL CHECK(score BETWEEN 0 AND 10),
    maturity TEXT NOT NULL CHECK(length(maturity) BETWEEN 1 AND 16),
    format TEXT NOT NULL CHECK(length(format) BETWEEN 1 AND 80),
    genres_json TEXT NOT NULL,
    artwork TEXT NOT NULL CHECK(artwork LIKE '/posters/%.svg'),
    display_order INTEGER NOT NULL DEFAULT 0 CHECK(display_order >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_content_items_category_order
    ON content_items(category, display_order);

CREATE TABLE IF NOT EXISTS featured_banners (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL CHECK(category IN ('Anime', 'K-Drama', 'Serie', 'Pelicula')),
    eyebrow TEXT NOT NULL CHECK(length(eyebrow) BETWEEN 1 AND 120),
    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 160),
    synopsis TEXT NOT NULL CHECK(length(synopsis) BETWEEN 1 AND 1000),
    release_year INTEGER NOT NULL CHECK(release_year BETWEEN 1900 AND 2200),
    age_rating TEXT NOT NULL CHECK(length(age_rating) BETWEEN 1 AND 16),
    format TEXT NOT NULL CHECK(length(format) BETWEEN 1 AND 80),
    genres_json TEXT NOT NULL,
    artwork TEXT NOT NULL CHECK(artwork LIKE '/banners/%.svg'),
    section_href TEXT NOT NULL CHECK(section_href LIKE '#%'),
    display_order INTEGER NOT NULL DEFAULT 0 CHECK(display_order >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(username) BETWEEN 3 AND 40),
    email TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(email) BETWEEN 5 AND 254),
    password_hash TEXT NOT NULL CHECK(length(password_hash) BETWEEN 20 AND 255),
    avatar_url TEXT CHECK(avatar_url IS NULL OR length(avatar_url) <= 500),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id INTEGER NOT NULL,
    content_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (user_id, content_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (content_id) REFERENCES content_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS banner_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    banner_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    body TEXT NOT NULL CHECK(length(trim(body)) BETWEEN 1 AND 1000),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (banner_id) REFERENCES featured_banners(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_banner_comments_banner_created
    ON banner_comments(banner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_banner_comments_user
    ON banner_comments(user_id);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY CHECK(length(token_hash) = 64),
    user_id INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
    ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires
    ON auth_sessions(expires_at);
