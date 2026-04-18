import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "app.db"
_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, isolation_level=None)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA foreign_keys=ON")
            _init_schema(_conn)
        return _conn


def close_conn() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def _init_schema(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id         TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            topic      TEXT,
            data       TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS user_progress (
            user_id         INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            coins           INTEGER NOT NULL DEFAULT 0,
            earned_coins    INTEGER NOT NULL DEFAULT 0,
            study_seconds   INTEGER NOT NULL DEFAULT 0,
            unpaid_seconds  INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_upgrades (
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            upgrade_id TEXT NOT NULL,
            level      INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, upgrade_id)
        );

        CREATE TABLE IF NOT EXISTS spotify_connections (
            user_id         INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            spotify_user_id TEXT,
            display_name    TEXT,
            scope           TEXT NOT NULL DEFAULT '',
            token_type      TEXT NOT NULL DEFAULT 'Bearer',
            access_token    TEXT NOT NULL,
            refresh_token   TEXT,
            expires_at      TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );
        """
    )
    for col, defn in [
        ("plant_xp", "INTEGER NOT NULL DEFAULT 0"),
        ("plant_health", "INTEGER NOT NULL DEFAULT 100"),
        ("plant_skin", "TEXT NOT NULL DEFAULT 'default'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE user_progress ADD COLUMN {col} {defn}")
        except Exception:
            pass

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS user_plant_rewards (
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            level_id   TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            PRIMARY KEY (user_id, level_id)
        );
        """
    )


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    with _lock:
        return get_conn().execute(sql, params)


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with _lock:
        return get_conn().execute(sql, params).fetchone()


def query_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with _lock:
        return get_conn().execute(sql, params).fetchall()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
