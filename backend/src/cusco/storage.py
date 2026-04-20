"""Thin SQLite wrapper for bulk-data persistence.

Historically the bulk sources (contracts, IMPIC entities, PRR) parsed
their downloads into large in-memory dicts keyed by NIF — roughly 1.2 GB
of resident memory and a 1–2 minute cold start. This module replaces
those dicts with SQLite tables so the data survives restarts and isn't
held in process memory.

Design notes:

- Not an ORM. Each bulk table stores `(nif, payload_json)` rows — the
  source that owns the table knows how to decode the payload. That keeps
  us out of the business of maintaining per-source SQL schemas while
  data shapes evolve upstream.
- WAL journal mode so many readers (HTTP requests) don't block the
  single writer (startup ingest).
- Connections are per-call, not shared. `sqlite3.Connection` is not
  safe to share across threads/tasks by default, and our read paths run
  from `asyncio.to_thread` which picks arbitrary worker threads.
- The DB lives in a user-scoped persistent location (`~/.cusco/cache/`)
  so it survives /tmp cleanup and restarts (closes #13 for bulk data).
  Override via `CUSCO_DB_PATH`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Iterable

# Table names are hardcoded today but `_ensure_schema` interpolates them
# into `CREATE TABLE` DDL. Validate eagerly in __init__ so a future
# refactor that feeds user input here can't become a SQL injection.
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

logger = logging.getLogger(__name__)

# Default: same user-scoped persistent location as the AI overview cache,
# with an env override. Bulk DB survives restarts (closes #13).
DB_PATH = Path(
    os.environ.get("CUSCO_DB_PATH")
    or (Path.home() / ".cusco" / "cache" / "cusco.db")
)


def get_connection() -> sqlite3.Connection:
    """Return a new sqlite3 connection with sane pragmas for our workload.

    Uses autocommit / manual transaction control (`isolation_level=None`)
    so `replace_all` can wrap its delete+insert in an explicit
    `BEGIN`/`COMMIT` pair. Readers don't need transactions — each
    `SELECT` is implicitly atomic in WAL mode.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    # WAL for reader/writer concurrency (we're single-writer but many readers)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    # `timeout=30.0` above guards lock acquisition on connect; this covers
    # in-transaction SQLITE_BUSY (a reader landing mid-replace_all).
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _escape_like(query: str) -> str:
    """Escape SQL LIKE metacharacters (``%``, ``_``, ``\\``) so a user
    searching for ``50%`` gets literal matches, not a wildcard hunt.
    Pair with ``ESCAPE '\\'`` in the query."""
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _ensure_meta(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _meta (
            name TEXT PRIMARY KEY,
            loaded_at REAL NOT NULL,
            row_count INTEGER NOT NULL
        )
        """
    )


class BulkTable:
    """A table keyed by NIF, storing one JSON-encoded row per record.

    Schema (created idempotently on first use):

        CREATE TABLE "{name}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nif TEXT NOT NULL,
            payload TEXT NOT NULL  -- JSON dict
        );
        CREATE INDEX "{name}_nif_idx" ON "{name}"(nif);

    A shared `_meta` table tracks per-table freshness (loaded_at, row_count).

    Usage:
        table = BulkTable("contracts_supplier")
        fresh = await asyncio.to_thread(table.is_fresh, 24 * 3600)
        if not fresh:
            await asyncio.to_thread(table.replace_all, rows)  # (nif, dict) iterable
        rows = await asyncio.to_thread(table.get_by_nif, "500697256")

    All methods are blocking — wrap them in `asyncio.to_thread` at the
    call site.
    """

    def __init__(self, name: str):
        if not _TABLE_NAME_RE.match(name):
            # Defence-in-depth: identifiers can't be bound as parameters in
            # sqlite3, so `_ensure_schema` interpolates `self.name`
            # directly. All current call sites pass hardcoded constants,
            # but this assertion makes sure a future refactor that
            # accidentally pipes user input here crashes loudly instead
            # of enabling SQL injection via crafted table names.
            raise ValueError(f"Invalid SQLite table name: {name!r}")
        self.name = name

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        # Identifiers quoted defensively — table names are validated in
        # __init__, but quoting guards against SQLite keyword collisions
        # for any future additions.
        conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{self.name}" ('
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "nif TEXT NOT NULL,"
            "payload TEXT NOT NULL)"
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS "{self.name}_nif_idx" '
            f'ON "{self.name}"(nif)'
        )
        _ensure_meta(conn)

    def is_fresh(self, max_age_seconds: float) -> bool:
        """True if the table has been loaded within max_age_seconds."""
        try:
            with closing(get_connection()) as conn:
                self._ensure_schema(conn)
                cur = conn.execute(
                    "SELECT loaded_at FROM _meta WHERE name = ?", (self.name,)
                )
                row = cur.fetchone()
                if row is None:
                    return False
                return (time.time() - row["loaded_at"]) < max_age_seconds
        except sqlite3.Error as e:
            logger.warning(f"SQLite is_fresh({self.name}) failed: {e}")
            return False

    def row_count(self) -> int:
        try:
            with closing(get_connection()) as conn:
                self._ensure_schema(conn)
                cur = conn.execute(
                    "SELECT row_count FROM _meta WHERE name = ?", (self.name,)
                )
                row = cur.fetchone()
                return row["row_count"] if row else 0
        except sqlite3.Error as e:
            logger.warning(f"SQLite row_count({self.name}) failed: {e}")
            return 0

    def replace_all(self, rows: Iterable[tuple[str, dict]]) -> int:
        """Atomic replace: wipe + reinsert + update meta. Returns inserted count.

        The entire operation runs inside an explicit transaction; on any
        error we `ROLLBACK` so a partial write never leaves the table in
        an inconsistent state.
        """
        count = 0
        with closing(get_connection()) as conn:
            self._ensure_schema(conn)
            conn.execute("BEGIN")
            try:
                conn.execute(f'DELETE FROM "{self.name}"')
                conn.executemany(
                    f'INSERT INTO "{self.name}"(nif, payload) VALUES (?, ?)',
                    (
                        (
                            str(nif),
                            json.dumps(payload, ensure_ascii=False, default=str),
                        )
                        for nif, payload in rows
                    ),
                )
                cur = conn.execute(f'SELECT COUNT(*) AS c FROM "{self.name}"')
                count = cur.fetchone()["c"]
                conn.execute(
                    "INSERT OR REPLACE INTO _meta(name, loaded_at, row_count) "
                    "VALUES (?, ?, ?)",
                    (self.name, time.time(), count),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        logger.info(f"SQLite table '{self.name}': replaced with {count} rows")
        return count

    def get_by_nif(self, nif: str) -> list[dict]:
        """Look up all payloads for a given NIF. Returns [] on any error.

        `_ensure_schema` is called here too so a query that lands before
        any `replace_all` has run (e.g. a cold DB wiped out of band)
        doesn't fall through to an `OperationalError: no such table`
        that gets silently swallowed as "0 hits". With the schema
        guaranteed, a bare `[]` means "NIF truly not in dataset."
        """
        try:
            with closing(get_connection()) as conn:
                self._ensure_schema(conn)
                cur = conn.execute(
                    f'SELECT payload FROM "{self.name}" WHERE nif = ?', (nif,)
                )
                return [json.loads(row["payload"]) for row in cur.fetchall()]
        except sqlite3.Error as e:
            logger.warning(f"SQLite get_by_nif({self.name}, {nif}) failed: {e}")
            return []


class NameIndexTable:
    """A small (name_lower, nif) lookup table for substring name search.

    Sits alongside a BulkTable for the same source — the bulk table holds
    the payloads keyed by NIF, this one lets `search_by_name` find NIFs
    by a lowercase-substring match on the name. Kept as its own class
    (rather than bolted onto `BulkTable`) because only `EntitiesSource`
    needs it.
    """

    def __init__(self, name: str):
        if not _TABLE_NAME_RE.match(name):
            raise ValueError(f"Invalid SQLite table name: {name!r}")
        self.name = name

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{self.name}" ('
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "name_lower TEXT NOT NULL,"
            "nif TEXT NOT NULL)"
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS "{self.name}_name_idx" '
            f'ON "{self.name}"(name_lower)'
        )
        _ensure_meta(conn)

    def is_fresh(self, max_age_seconds: float) -> bool:
        """True if the table has been loaded within max_age_seconds."""
        try:
            with closing(get_connection()) as conn:
                self._ensure_schema(conn)
                cur = conn.execute(
                    "SELECT loaded_at FROM _meta WHERE name = ?", (self.name,)
                )
                row = cur.fetchone()
                if row is None:
                    return False
                return (time.time() - row["loaded_at"]) < max_age_seconds
        except sqlite3.Error as e:
            logger.warning(f"SQLite is_fresh({self.name}) failed: {e}")
            return False

    def replace_all(self, rows: Iterable[tuple[str, str]]) -> int:
        """Wipe + reinsert (name_lower, nif) pairs in a single transaction."""
        count = 0
        with closing(get_connection()) as conn:
            self._ensure_schema(conn)
            conn.execute("BEGIN")
            try:
                conn.execute(f'DELETE FROM "{self.name}"')
                conn.executemany(
                    f'INSERT INTO "{self.name}"(name_lower, nif) VALUES (?, ?)',
                    ((str(name), str(nif)) for name, nif in rows),
                )
                cur = conn.execute(f'SELECT COUNT(*) AS c FROM "{self.name}"')
                count = cur.fetchone()["c"]
                conn.execute(
                    "INSERT OR REPLACE INTO _meta(name, loaded_at, row_count) "
                    "VALUES (?, ?, ?)",
                    (self.name, time.time(), count),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        logger.info(f"SQLite name index '{self.name}': replaced with {count} rows")
        return count

    def search_nifs_by_substring(self, query: str, limit: int = 100) -> list[str]:
        """Return up to `limit` distinct NIFs whose name_lower contains query.

        Exact matches (`name_lower = query`) come first, then substring
        hits, so the caller can preserve the "exact-first" ordering.
        """
        q = query.lower().strip()
        if not q:
            return []
        try:
            with closing(get_connection()) as conn:
                self._ensure_schema(conn)
                # Exact hits first
                exact = [
                    row["nif"]
                    for row in conn.execute(
                        f'SELECT DISTINCT nif FROM "{self.name}" '
                        "WHERE name_lower = ? LIMIT ?",
                        (q, limit),
                    )
                ]
                if len(exact) >= limit:
                    return exact[:limit]

                remaining = limit - len(exact)
                # Escape `%`/`_`/`\` so a user searching for "50%" or
                # "foo_bar" gets literal matches, not wildcard hunts.
                like = f"%{_escape_like(q)}%"
                partial = [
                    row["nif"]
                    for row in conn.execute(
                        f'SELECT DISTINCT nif FROM "{self.name}" '
                        "WHERE name_lower LIKE ? ESCAPE '\\' "
                        "AND name_lower != ? LIMIT ?",
                        (like, q, remaining),
                    )
                ]
                # Preserve order: exact first, then partial, de-duped
                seen: set[str] = set()
                out: list[str] = []
                for nif in exact + partial:
                    if nif in seen:
                        continue
                    seen.add(nif)
                    out.append(nif)
                return out
        except sqlite3.Error as e:
            logger.warning(
                f"SQLite search_nifs_by_substring({self.name}) failed: {e}"
            )
            return []
