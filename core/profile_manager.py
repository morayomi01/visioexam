"""
ProfileManager — CRUD for candidate profiles.
Profiles persist across sessions: language, modality, speech rate, font, contrast.
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from core.database import Database

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "en": "English",
    "yo": "Yoruba",
    "ha": "Hausa",
    "ig": "Igbo",
}

MODALITIES = ("audio", "braille", "both")
CONTRAST_THEMES = ("light", "dark", "hcyob")   # hcyob = high-contrast yellow-on-black
MIN_FONT = 14
MAX_FONT = 36
MIN_RATE = 0.5
MAX_RATE = 2.0


@dataclass
class CandidateProfile:
    id: str
    full_name: str
    language: str = "en"
    modality: str = "audio"
    speech_rate: float = 1.0
    font_size: int = 18
    contrast: str = "light"
    created_at: str = ""
    updated_at: str = ""

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def validate(self):
        errors = []
        if not self.id.strip():
            errors.append("Candidate ID must not be empty.")
        if not self.full_name.strip():
            errors.append("Full name must not be empty.")
        if self.language not in SUPPORTED_LANGUAGES:
            errors.append(f"Unsupported language '{self.language}'.")
        if self.modality not in MODALITIES:
            errors.append(f"Invalid modality '{self.modality}'.")
        if not (MIN_RATE <= self.speech_rate <= MAX_RATE):
            errors.append(f"Speech rate must be between {MIN_RATE} and {MAX_RATE}.")
        if not (MIN_FONT <= self.font_size <= MAX_FONT):
            errors.append(f"Font size must be between {MIN_FONT}pt and {MAX_FONT}pt.")
        if self.contrast not in CONTRAST_THEMES:
            errors.append(f"Invalid contrast theme '{self.contrast}'.")
        return errors


class ProfileManager:
    """Create, retrieve, and update candidate profiles in the database."""

    def __init__(self, db: Database):
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, candidate_id: str) -> CandidateProfile | None:
        row = self._db.fetchone(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        )
        if row is None:
            return None
        return self._row_to_profile(row)

    def list_all(self) -> list[CandidateProfile]:
        rows = self._db.fetchall("SELECT * FROM candidates ORDER BY full_name")
        return [self._row_to_profile(r) for r in rows]

    def create(self, profile: CandidateProfile) -> CandidateProfile:
        errors = profile.validate()
        if errors:
            raise ValueError("; ".join(errors))

        now = datetime.now(timezone.utc).isoformat()
        profile.created_at = now
        profile.updated_at = now

        self._db.execute(
            """
            INSERT INTO candidates (id, full_name, language, modality, speech_rate,
                                    font_size, contrast, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.id, profile.full_name, profile.language, profile.modality,
                profile.speech_rate, profile.font_size, profile.contrast,
                profile.created_at, profile.updated_at,
            ),
        )
        self._db.commit()
        logger.info(f"Profile created for candidate {profile.id}.")
        return profile

    def update(self, profile: CandidateProfile) -> CandidateProfile:
        errors = profile.validate()
        if errors:
            raise ValueError("; ".join(errors))

        profile.updated_at = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            """
            UPDATE candidates
            SET full_name=?, language=?, modality=?, speech_rate=?,
                font_size=?, contrast=?, updated_at=?
            WHERE id=?
            """,
            (
                profile.full_name, profile.language, profile.modality,
                profile.speech_rate, profile.font_size, profile.contrast,
                profile.updated_at, profile.id,
            ),
        )
        self._db.commit()
        logger.info(f"Profile updated for candidate {profile.id}.")
        return profile

    def upsert(self, profile: CandidateProfile) -> CandidateProfile:
        existing = self.get(profile.id)
        if existing:
            return self.update(profile)
        return self.create(profile)

    def delete(self, candidate_id: str):
        self._db.execute("DELETE FROM candidates WHERE id=?", (candidate_id,))
        self._db.commit()
        logger.info(f"Profile deleted for candidate {candidate_id}.")

    def exists(self, candidate_id: str) -> bool:
        return self.get(candidate_id) is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_profile(row) -> CandidateProfile:
        return CandidateProfile(
            id=row["id"],
            full_name=row["full_name"],
            language=row["language"],
            modality=row["modality"],
            speech_rate=row["speech_rate"],
            font_size=row["font_size"],
            contrast=row["contrast"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
