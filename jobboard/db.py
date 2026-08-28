"""SQLite schema and connection handling.

Two tables that deliberately never merge:
  boards  -- the registry. Discovery writes here, pollers only read/annotate.
  jobs    -- the feed. Only the reconciler writes here.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS boards (
    ats                  TEXT    NOT NULL,
    slug                 TEXT    NOT NULL,
    company_name         TEXT,
    -- unvalidated: discovered but never probed
    -- active: probe returned postings
    -- empty: probe succeeded but board has zero listings (still poll, may fill)
    -- dead: probe returned a permanent 404/410, or too many failures
    status               TEXT    NOT NULL DEFAULT 'unvalidated',
    tier                 INTEGER NOT NULL DEFAULT 1,
    job_count            INTEGER,
    next_poll_at         INTEGER,
    last_polled_at       INTEGER,
    last_ok_at           INTEGER,
    last_new_at          INTEGER,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_error           TEXT,
    first_seen_at        INTEGER NOT NULL,
    PRIMARY KEY (ats, slug)
);
CREATE INDEX IF NOT EXISTS idx_boards_due    ON boards(status, next_poll_at);
CREATE INDEX IF NOT EXISTS idx_boards_ats    ON boards(ats, status);

-- Provenance is many-to-one: the same board is typically found by several
-- sources. Keeping this separate lets us measure which sources actually earn
-- their runtime instead of guessing.
CREATE TABLE IF NOT EXISTS board_sources (
    ats           TEXT    NOT NULL,
    slug          TEXT    NOT NULL,
    source        TEXT    NOT NULL,
    first_seen_at INTEGER NOT NULL,
    detail        TEXT,
    PRIMARY KEY (ats, slug, source)
);

CREATE TABLE IF NOT EXISTS jobs (
    ats               TEXT    NOT NULL,
    slug              TEXT    NOT NULL,
    external_id       TEXT    NOT NULL,
    title             TEXT,
    location          TEXT,
    locations_json    TEXT,
    department        TEXT,
    team              TEXT,
    employment_type   TEXT,
    workplace_type    TEXT,
    is_remote         INTEGER,
    url               TEXT,
    apply_url         TEXT,
    compensation_json TEXT,
    posted_at         INTEGER,
    first_seen_at     INTEGER NOT NULL,
    last_seen_at      INTEGER NOT NULL,
    closed_at         INTEGER,
    status            TEXT    NOT NULL DEFAULT 'open',
    missing_polls     INTEGER NOT NULL DEFAULT 0,
    content_hash      TEXT,
    source            TEXT,
    raw_json          TEXT,
    PRIMARY KEY (ats, slug, external_id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_board_open  ON jobs(ats, slug, status);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen  ON jobs(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status_seen ON jobs(status, last_seen_at);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          INTEGER NOT NULL,
    type        TEXT    NOT NULL,   -- new | edited | closed | reopened
    ats         TEXT,
    slug        TEXT,
    external_id TEXT,
    title       TEXT,
    url         TEXT,
    detail_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);

CREATE TABLE IF NOT EXISTS poll_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    INTEGER,
    finished_at   INTEGER,
    boards_polled INTEGER DEFAULT 0,
    boards_failed INTEGER DEFAULT 0,
    new_jobs      INTEGER DEFAULT 0,
    edited_jobs   INTEGER DEFAULT 0,
    closed_jobs   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db(path: Path | None = None) -> sqlite3.Connection:
    conn = connect(path)
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    return conn
