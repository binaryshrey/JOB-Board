"""Writes to the `jobs` table. Owned by the reconciler; seeding is the one
exception, and seeded rows are tagged so they can be told apart from polled
ones until a real poll confirms them.
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Iterable

from .models import Posting


def now() -> int:
    return int(time.time())


def _row(p: Posting, ts: int, source: str) -> tuple:
    return (
        p.ats, p.slug, p.external_id, p.title, p.location,
        json.dumps(p.locations) if p.locations else None,
        p.department, p.team, p.employment_type, p.workplace_type,
        None if p.is_remote is None else int(bool(p.is_remote)),
        p.url, p.apply_url,
        json.dumps(p.compensation) if p.compensation else None,
        p.posted_at, ts, ts, p.content_hash(), source,
        json.dumps(p.raw, default=str) if p.raw else None,
    )


INSERT = """
INSERT INTO jobs (ats, slug, external_id, title, location, locations_json,
                  department, team, employment_type, workplace_type, is_remote,
                  url, apply_url, compensation_json, posted_at,
                  first_seen_at, last_seen_at, content_hash, source, raw_json)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""


def seed(conn: sqlite3.Connection, postings: Iterable[Posting], source: str) -> int:
    """Insert postings we learned about from a discovery source.

    Existing rows are left completely alone: a polled row is always more
    trustworthy than a seeded one, and re-seeding must never reset last_seen_at
    or it would keep a dead posting alive forever.
    """
    ts = now()
    added = 0
    cur = conn.cursor()
    cur.execute("BEGIN")
    try:
        for p in postings:
            cur.execute(INSERT.replace("INSERT INTO", "INSERT OR IGNORE INTO"),
                        _row(p, ts, source))
            added += cur.rowcount
        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        raise
    return added


def open_ids(conn: sqlite3.Connection, ats: str, slug: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        """SELECT external_id, content_hash, status, missing_polls
           FROM jobs WHERE ats=? AND slug=? AND status='open'""",
        (ats, slug),
    ).fetchall()
    return {r["external_id"]: r for r in rows}


def record_event(conn: sqlite3.Connection, kind: str, p_ats: str, p_slug: str,
                 ext: str | None, title: str | None, url: str | None,
                 detail: dict | None = None) -> None:
    conn.execute(
        """INSERT INTO events (ts, type, ats, slug, external_id, title, url, detail_json)
           VALUES (?,?,?,?,?,?,?,?)""",
        (now(), kind, p_ats, p_slug, ext, title, url,
         json.dumps(detail) if detail else None),
    )
