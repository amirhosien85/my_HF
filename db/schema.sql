-- Durable state for the orchestrator. Safe to run on Supabase (free tier) or local Postgres.

CREATE TABLE IF NOT EXISTS news_items (
    url            TEXT PRIMARY KEY,
    -- Telegram callback_data is capped at 64 bytes, so buttons carry this short id.
    short_id       TEXT GENERATED ALWAYS AS (substr(md5(url), 1, 10)) STORED UNIQUE,
    title          TEXT NOT NULL,
    summary        TEXT,
    source         TEXT,
    category       TEXT NOT NULL DEFAULT 'ai',
    published_at   TIMESTAMPTZ,
    status         TEXT NOT NULL DEFAULT 'new', -- new | edited | published | skipped
    article        TEXT,
    telegram_msg_id BIGINT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS news_items_status_idx ON news_items (status, created_at DESC);

-- Telegram long-polling offset + per-update dedup (getUpdates can replay on retries).
CREATE TABLE IF NOT EXISTS telegram_updates (
    update_id  BIGINT PRIMARY KEY,
    chat_id    BIGINT,
    user_id    BIGINT,
    kind       TEXT,            -- text | voice | callback
    payload    JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS telegram_offset (
    id      INT PRIMARY KEY DEFAULT 1,
    offset_value BIGINT NOT NULL DEFAULT 0,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT telegram_offset_single_row CHECK (id = 1)
);
INSERT INTO telegram_offset (id, offset_value) VALUES (1, 0)
ON CONFLICT (id) DO NOTHING;

-- Reactions to inline buttons; drives the ghosting algorithm.
CREATE TABLE IF NOT EXISTS reactions (
    id         BIGSERIAL PRIMARY KEY,
    url        TEXT REFERENCES news_items (url) ON DELETE CASCADE,
    category   TEXT NOT NULL,
    user_id    BIGINT,
    action     TEXT NOT NULL,   -- awesome | pass | redpill
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS reactions_category_idx ON reactions (category, created_at DESC);

-- One row per (user, category): frequency + consecutive-ignore counter.
CREATE TABLE IF NOT EXISTS category_prefs (
    user_id          BIGINT NOT NULL,
    category         TEXT NOT NULL,
    ignore_streak    INT NOT NULL DEFAULT 0,
    frequency_hours  INT NOT NULL DEFAULT 1,
    muted            BOOLEAN NOT NULL DEFAULT false,
    suggested_at     TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, category)
);

-- Ideas mirrored from ChromaDB so the vector store can be rebuilt after a Space restart.
CREATE TABLE IF NOT EXISTS ideas (
    id         TEXT PRIMARY KEY,
    user_id    BIGINT,
    text       TEXT NOT NULL,
    source     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
