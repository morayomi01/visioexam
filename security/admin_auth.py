"""
Admin Authentication.
Password hashing with bcrypt (cost factor ≥ 12) as required by NFR-7.3.
Admin credentials are separate from candidate login.
"""

import logging
import os

import bcrypt

from core.database import Database
from security.audit_logger import AuditLogger, AuditEvent

logger = logging.getLogger(__name__)

BCRYPT_COST = 12


class AdminAuth:
    """Handles admin account creation, login, and session management."""

    def __init__(self, db: Database, audit: AuditLogger):
        self._db = db
        self._audit = audit
        self._current_admin: str | None = None

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------

    def create_admin(self, username: str, password: str) -> bool:
        """
        Create a new admin account. Returns False if username already exists.
        Should be called once during initial setup.
        """
        existing = self._db.fetchone(
            "SELECT id FROM admins WHERE username=?", (username,)
        )
        if existing:
            logger.warning(f"Admin '{username}' already exists.")
            return False

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_COST))
        self._db.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?,?)",
            (username, pw_hash.decode()),
        )
        self._db.commit()
        logger.info(f"Admin account created: {username}")
        return True

    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        if not self.login(username, old_password):
            return False
        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(rounds=BCRYPT_COST))
        self._db.execute(
            "UPDATE admins SET password_hash=? WHERE username=?",
            (new_hash.decode(), username),
        )
        self._db.commit()
        logger.info(f"Password changed for admin: {username}")
        return True

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> bool:
        row = self._db.fetchone(
            "SELECT password_hash FROM admins WHERE username=?", (username,)
        )
        if not row:
            logger.warning(f"Login attempt for unknown admin '{username}'.")
            return False
        ok = bcrypt.checkpw(password.encode(), row["password_hash"].encode())
        if ok:
            self._current_admin = username
            self._audit.log(AuditEvent.ADMIN_LOGIN, f"admin={username}")
            logger.info(f"Admin '{username}' logged in.")
        else:
            logger.warning(f"Failed login attempt for admin '{username}'.")
        return ok

    def logout(self):
        if self._current_admin:
            self._audit.log(AuditEvent.ADMIN_LOGOUT, f"admin={self._current_admin}")
            logger.info(f"Admin '{self._current_admin}' logged out.")
        self._current_admin = None

    def is_logged_in(self) -> bool:
        return self._current_admin is not None

    def require_login(self):
        if not self.is_logged_in():
            raise PermissionError("Admin authentication required.")

    @property
    def current_admin(self) -> str | None:
        return self._current_admin
