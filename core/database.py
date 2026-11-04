"""
Database module for VisioExam.
Uses SQLCipher for the application database. Plain SQLite is available only
when explicitly requested for isolated test databases.
"""

import sqlite3
import logging
import os
import threading
from pathlib import Path

from core.app_paths import get_or_create_database_key, is_frozen, user_data_dir

logger = logging.getLogger(__name__)

DB_PATH = (
    user_data_dir() / "data" / "visioexam.db"
    if is_frozen()
    else Path(__file__).parent.parent / "data" / "visioexam.db"
)


class Database:
    """
    Manages the local SQLite database for VisioExam.
    All persistent application data — profiles, questions, sessions, responses,
    and audit entries — is stored here.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        passphrase: str | None = None,
        *,
        allow_plaintext: bool = False,
    ):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._passphrase = (
            passphrase
            or os.environ.get("VISIOEXAM_DB_KEY")
            or (get_or_create_database_key() if is_frozen() else None)
        )
        self._allow_plaintext = allow_plaintext or (
            os.environ.get("VISIOEXAM_ALLOW_PLAINTEXT_DB", "0") == "1"
        )
        # Give each worker thread its own SQLCipher/SQLite connection. Python's
        # sqlite drivers reject sharing a connection across the exam autosave
        # thread and the GUI thread by default.
        self._thread_state = threading.local()
        self._connections: list = []
        self._connections_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open (or return existing) database connection."""
        conn = getattr(self._thread_state, "connection", None)
        if conn is not None:
            return conn
        try:
            from pysqlcipher3 import dbapi2 as sqlcipher  # type: ignore
        except ImportError as exc:
            # Windows wheels are also distributed under the sqlcipher3 module
            # name. Keep pysqlcipher3 compatibility for existing environments.
            try:
                from sqlcipher3 import dbapi2 as sqlcipher  # type: ignore
            except ImportError:
                if not self._allow_plaintext:
                    raise RuntimeError(
                        "SQLCipher is required for the application database. "
                        "Install the SQLCipher Python binding. For an isolated "
                        "development database only, explicitly construct "
                        "Database(..., allow_plaintext=True)."
                ) from exc
                logger.warning("Explicit plaintext SQLite mode enabled for this database.")
                conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
                conn.row_factory = sqlite3.Row
            else:
                conn = self._connect_sqlcipher(sqlcipher)
        else:
            conn = self._connect_sqlcipher(sqlcipher)

        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        self._thread_state.connection = conn
        with self._connections_lock:
            self._connections.append(conn)
        return conn

    def _connect_sqlcipher(self, sqlcipher):
        """Open SQLCipher and verify its key before returning the connection."""
        if not self._passphrase:
            raise RuntimeError(
                "VISIOEXAM_DB_KEY must contain a strong database passphrase."
            )
        conn = sqlcipher.connect(str(self.db_path), check_same_thread=False)
        # sqlite3.Row cannot wrap SQLCipher cursors. Use the Row factory
        # exported by the same DB-API driver that created this connection.
        conn.row_factory = sqlcipher.Row
        escaped_key = self._passphrase.replace("'", "''")
        conn.execute(f"PRAGMA key='{escaped_key}'")
        try:
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except Exception as exc:
            conn.close()
            raise RuntimeError(
                "Could not open the database with SQLCipher. The key may be "
                "wrong, or this may be an existing plaintext SQLite database. "
                "The file was left untouched; migrate it explicitly before use."
            ) from exc
        logger.info("Using SQLCipher encrypted database.")
        return conn

    def get_connection(self) -> sqlite3.Connection:
        return self._connect()

    def close(self):
        with self._connections_lock:
            connections, self._connections = self._connections, []
        for conn in connections:
            try:
                conn.close()
            except Exception as exc:
                logger.warning("Could not close a database connection cleanly: %s", exc)
        self._thread_state.connection = None

    # ------------------------------------------------------------------
    # Schema initialization
    # ------------------------------------------------------------------

    def initialize(self):
        """Create all tables if they do not already exist."""
        conn = self._connect()
        cur = conn.cursor()

        # Candidate profiles
        cur.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id          TEXT PRIMARY KEY,
                full_name   TEXT NOT NULL,
                language    TEXT NOT NULL DEFAULT 'en',
                modality    TEXT NOT NULL DEFAULT 'audio',
                speech_rate REAL NOT NULL DEFAULT 1.0,
                font_size   INTEGER NOT NULL DEFAULT 18,
                contrast    TEXT NOT NULL DEFAULT 'light',
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Administrator accounts
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Exam sessions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id             TEXT PRIMARY KEY,
                candidate_id   TEXT NOT NULL,
                exam_id        TEXT NOT NULL,
                started_at     TEXT,
                ended_at       TEXT,
                status         TEXT NOT NULL DEFAULT 'pending',
                score          REAL,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id)
            )
        """)

        # Exams (metadata)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id           TEXT PRIMARY KEY,
                title        TEXT NOT NULL,
                time_limit   INTEGER NOT NULL DEFAULT 3600,
                language     TEXT NOT NULL DEFAULT 'en',
                created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                created_by   TEXT
            )
        """)

        # Questions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id           TEXT PRIMARY KEY,
                exam_id      TEXT NOT NULL,
                type         TEXT NOT NULL,
                body         TEXT NOT NULL,
                options      TEXT,
                correct      TEXT NOT NULL,
                language     TEXT NOT NULL DEFAULT 'en',
                position     INTEGER,
                FOREIGN KEY (exam_id) REFERENCES exams(id)
            )
        """)

        # Candidate responses (encrypted blobs stored as hex)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id           TEXT PRIMARY KEY,
                session_id   TEXT NOT NULL,
                question_id  TEXT NOT NULL,
                answer_enc   TEXT NOT NULL,
                answered_at  TEXT NOT NULL DEFAULT (datetime('now')),
                flagged      INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
        """)

        # Audit log (append-only; HMAC per entry stored separately)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT,
                event_type  TEXT NOT NULL,
                detail      TEXT,
                hmac        TEXT NOT NULL,
                logged_at   TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        conn.commit()
        logger.info("Database schema initialized.")

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._connect().execute(sql, params)

    def executemany(self, sql: str, params_list) -> sqlite3.Cursor:
        return self._connect().executemany(sql, params_list)

    def commit(self):
        self._connect().commit()

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.execute(sql, params).fetchall()
