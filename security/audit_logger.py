"""
Audit Logger — tamper-evident session event logging.
Each entry is written with an HMAC-SHA256 checksum over the entry content
so any offline modification is detectable.
Append-only semantics: entries are never updated or deleted.
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone

from core.database import Database

logger = logging.getLogger(__name__)

_HMAC_KEY_ENV = "VISIOEXAM_AUDIT_KEY"
_DEFAULT_HMAC_KEY = "visioexam_audit_hmac_key"

# Recognized event types
class AuditEvent:
    EXAM_START         = "EXAM_START"
    EXAM_END           = "EXAM_END"
    QUESTION_NAV       = "QUESTION_NAV"
    ANSWER_SAVED       = "ANSWER_SAVED"
    FLAG_SET           = "FLAG_SET"
    FLAG_CLEARED       = "FLAG_CLEARED"
    AUTOSAVE           = "AUTOSAVE"
    KIOSK_ENTER        = "KIOSK_ENTER"
    KIOSK_EXIT         = "KIOSK_EXIT"
    SUSPICIOUS_KEY     = "SUSPICIOUS_KEY"
    SCREEN_READER_ATTACH = "SCREEN_READER_ATTACH"
    SYSTEM_ALERT       = "SYSTEM_ALERT"
    ADMIN_LOGIN        = "ADMIN_LOGIN"
    ADMIN_LOGOUT       = "ADMIN_LOGOUT"
    ADMIN_CREDENTIAL_RESET = "ADMIN_CREDENTIAL_RESET"
    EXAM_UPLOAD        = "EXAM_UPLOAD"
    CANDIDATE_REGISTER = "CANDIDATE_REGISTER"


class AuditLogger:
    """
    Writes signed audit entries to the database audit_log table.
    Provides verify_log() to detect any tampering.
    """

    def __init__(self, db: Database, hmac_key: str | None = None):
        self._db = db
        self._hmac_key = (hmac_key or os.environ.get(_HMAC_KEY_ENV, _DEFAULT_HMAC_KEY)).encode()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(self, event_type: str, detail: str = "", session_id: str | None = None):
        """Append a signed audit entry."""
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({
            "session_id": session_id,
            "event_type": event_type,
            "detail": detail,
            "logged_at": now,
        }, sort_keys=True)
        mac = self._sign(payload)
        try:
            self._db.execute(
                """
                INSERT INTO audit_log (session_id, event_type, detail, hmac, logged_at)
                VALUES (?,?,?,?,?)
                """,
                (session_id, event_type, detail, mac, now),
            )
            self._db.commit()
        except Exception as exc:
            # Audit failures must never crash the exam
            logger.error(f"Audit log write failed: {exc}")

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_log(self) -> list[dict]:
        """
        Verify every entry's HMAC.
        Returns a list of dicts describing any tampered or invalid entries.
        """
        rows = self._db.fetchall("SELECT * FROM audit_log ORDER BY id")
        tampered = []
        for row in rows:
            payload = json.dumps({
                "session_id": row["session_id"],
                "event_type": row["event_type"],
                "detail": row["detail"],
                "logged_at": row["logged_at"],
            }, sort_keys=True)
            expected = self._sign(payload)
            if not hmac.compare_digest(expected, row["hmac"]):
                tampered.append({
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "logged_at": row["logged_at"],
                    "reason": "HMAC mismatch",
                })
        return tampered

    def export_log(self, session_id: str | None = None) -> list[dict]:
        """Return all log entries (optionally filtered by session_id)."""
        if session_id:
            rows = self._db.fetchall(
                "SELECT * FROM audit_log WHERE session_id=? ORDER BY id",
                (session_id,),
            )
        else:
            rows = self._db.fetchall("SELECT * FROM audit_log ORDER BY id")
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _sign(self, payload: str) -> str:
        return hmac.new(self._hmac_key, payload.encode(), hashlib.sha256).hexdigest()
