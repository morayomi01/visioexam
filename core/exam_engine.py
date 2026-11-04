"""
Exam Engine.
Handles question delivery, session state, timer, flagging, randomization,
and auto-save every 60 seconds. All candidate responses are encrypted before
persistence (AES-256-GCM via the security module).
"""

import json
import logging
import random
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from core.database import Database
from security.encryption import ResponseEncryptor

logger = logging.getLogger(__name__)

AUTO_SAVE_INTERVAL = 60   # seconds
COUNTDOWN_MARKS = {15 * 60, 5 * 60, 60}   # seconds remaining when alert fires


@dataclass
class Question:
    id: str
    exam_id: str
    type: str          # "mcq" only
    body: str
    options: list[str] = field(default_factory=list)   # MCQ/TF options
    correct: str = ""
    language: str = "en"
    position: int = 0


@dataclass
class ExamSession:
    id: str
    candidate_id: str
    exam_id: str
    questions: list[Question]
    time_limit: int                        # seconds
    started_at: datetime | None = None
    ended_at: datetime | None = None
    status: str = "pending"               # pending | active | completed | aborted
    responses: dict[str, str] = field(default_factory=dict)   # question_id -> plaintext answer
    flagged: set[str] = field(default_factory=set)
    current_index: int = 0


class ExamEngine:
    """
    Core examination logic. The UI layer calls into this engine and registers
    callbacks for timer events and auto-save confirmations.
    """

    def __init__(self, db: Database, encryptor: ResponseEncryptor):
        self._db = db
        self._encryptor = encryptor
        self._session: ExamSession | None = None
        self._timer_thread: threading.Thread | None = None
        self._autosave_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Callbacks registered by the UI
        self._on_countdown: Callable[[int], None] | None = None   # seconds remaining
        self._on_time_up: Callable[[], None] | None = None
        self._on_autosave: Callable[[], None] | None = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def load_exam(self, exam_id: str, candidate_id: str) -> ExamSession:
        """Load an exam from the database, randomize questions, and create a session."""
        exam_row = self._db.fetchone("SELECT * FROM exams WHERE id=?", (exam_id,))
        if not exam_row:
            raise ValueError(f"Exam '{exam_id}' not found.")

        q_rows = self._db.fetchall(
            "SELECT * FROM questions WHERE exam_id=? AND lower(type)='mcq' "
            "ORDER BY position", (exam_id,)
        )
        if not q_rows:
            raise ValueError(
                "This exam has no multiple-choice questions. Import MCQ items first."
            )
        questions = [self._row_to_question(r) for r in q_rows]
        random.shuffle(questions)

        # Randomize MCQ option order per question
        for q in questions:
            if len(q.options) > 1:
                random.shuffle(q.options)

        session = ExamSession(
            id=str(uuid.uuid4()),
            candidate_id=candidate_id,
            exam_id=exam_id,
            questions=questions,
            time_limit=exam_row["time_limit"],
        )
        self._session = session

        # Persist session row
        self._db.execute(
            "INSERT INTO sessions (id, candidate_id, exam_id, status) VALUES (?,?,?,?)",
            (session.id, candidate_id, exam_id, "pending"),
        )
        self._db.commit()
        return session

    def start(self):
        """Mark the session active and begin timer + auto-save threads."""
        if self._session is None:
            raise RuntimeError("No session loaded. Call load_exam() first.")
        self._session.started_at = datetime.now(timezone.utc)
        self._session.status = "active"
        self._db.execute(
            "UPDATE sessions SET status='active', started_at=? WHERE id=?",
            (self._session.started_at.isoformat(), self._session.id),
        )
        self._db.commit()

        self._stop_event.clear()
        self._timer_thread = threading.Thread(target=self._run_timer, daemon=True)
        self._autosave_thread = threading.Thread(target=self._run_autosave, daemon=True)
        self._timer_thread.start()
        self._autosave_thread.start()
        logger.info(f"Exam session {self._session.id} started.")

    def submit(self) -> dict:
        """Finalize the session, encrypt and persist all responses, return results."""
        if self._session is None:
            raise RuntimeError("No active session.")
        self._stop_event.set()
        self._session.ended_at = datetime.now(timezone.utc)
        self._session.status = "completed"

        self._save_responses()

        score = self._calculate_score()
        self._session.status = "completed"
        self._db.execute(
            "UPDATE sessions SET status='completed', ended_at=?, score=? WHERE id=?",
            (self._session.ended_at.isoformat(), score, self._session.id),
        )
        self._db.commit()
        logger.info(f"Session {self._session.id} submitted. Score: {score:.1f}%")
        return {
            "session_id": self._session.id,
            "score": score,
            "answered": len(self._session.responses),
            "total": len(self._session.questions),
            "unanswered": len(self._session.questions) - len(self._session.responses),
        }

    def abort(self):
        """Abort session (e.g., on time-up or admin force-end); auto-saves first."""
        if self._session:
            self._stop_event.set()
            self._save_responses()
            self._session.status = "aborted"
            self._db.execute(
                "UPDATE sessions SET status='aborted', ended_at=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), self._session.id),
            )
            self._db.commit()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def current_question(self) -> Question | None:
        if self._session and 0 <= self._session.current_index < len(self._session.questions):
            return self._session.questions[self._session.current_index]
        return None

    def next_question(self) -> Question | None:
        if self._session and self._session.current_index < len(self._session.questions) - 1:
            self._session.current_index += 1
        return self.current_question()

    def prev_question(self) -> Question | None:
        if self._session and self._session.current_index > 0:
            self._session.current_index -= 1
        return self.current_question()

    def goto_question(self, index: int) -> Question | None:
        if self._session and 0 <= index < len(self._session.questions):
            self._session.current_index = index
        return self.current_question()

    # ------------------------------------------------------------------
    # Responses & flagging
    # ------------------------------------------------------------------

    def answer(self, question_id: str, answer: str):
        if self._session:
            self._session.responses[question_id] = answer

    def flag(self, question_id: str):
        if self._session:
            self._session.flagged.add(question_id)

    def unflag(self, question_id: str):
        if self._session:
            self._session.flagged.discard(question_id)

    def is_flagged(self, question_id: str) -> bool:
        return self._session is not None and question_id in self._session.flagged

    def unanswered_count(self) -> int:
        if not self._session:
            return 0
        return len(self._session.questions) - len(self._session.responses)

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def on_countdown(self, callback: Callable[[int], None]):
        self._on_countdown = callback

    def on_time_up(self, callback: Callable[[], None]):
        self._on_time_up = callback

    def on_autosave(self, callback: Callable[[], None]):
        self._on_autosave = callback

    # ------------------------------------------------------------------
    # Timer thread
    # ------------------------------------------------------------------

    def _run_timer(self):
        import time
        elapsed = 0
        fired = set()
        limit = self._session.time_limit if self._session else 0

        while not self._stop_event.is_set():
            time.sleep(1)
            elapsed += 1
            remaining = max(0, limit - elapsed)

            if remaining in COUNTDOWN_MARKS and remaining not in fired:
                fired.add(remaining)
                if self._on_countdown:
                    self._on_countdown(remaining)

            if elapsed >= limit:
                logger.info("Time limit reached.")
                if self._on_time_up:
                    self._on_time_up()
                break

    # ------------------------------------------------------------------
    # Auto-save thread
    # ------------------------------------------------------------------

    def _run_autosave(self):
        import time
        while not self._stop_event.is_set():
            time.sleep(AUTO_SAVE_INTERVAL)
            if self._stop_event.is_set():
                break
            self._save_responses()
            if self._on_autosave:
                self._on_autosave()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _save_responses(self):
        if not self._session:
            return
        for q_id, answer in self._session.responses.items():
            enc = self._encryptor.encrypt(answer)
            flagged = 1 if q_id in self._session.flagged else 0
            resp_id = str(uuid.uuid4())
            try:
                # responses has no unique (session, question) constraint in
                # databases created by earlier versions. Replace old rows
                # explicitly so repeated autosaves do not duplicate answers.
                self._db.execute(
                    "DELETE FROM responses WHERE session_id=? AND question_id=?",
                    (self._session.id, q_id),
                )
                self._db.execute(
                    """
                    INSERT OR REPLACE INTO responses
                        (id, session_id, question_id, answer_enc, answered_at, flagged)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (
                        resp_id, self._session.id, q_id, enc,
                        datetime.now(timezone.utc).isoformat(), flagged,
                    ),
                )
            except Exception as exc:
                logger.error(f"Failed to save response for question {q_id}: {exc}")
        self._db.commit()
        logger.debug(f"Auto-saved {len(self._session.responses)} responses.")

    def _calculate_score(self) -> float:
        if not self._session or not self._session.questions:
            return 0.0
        correct = 0
        for q in self._session.questions:
            answer = self._session.responses.get(q.id, "")
            if answer.strip().lower() == q.correct.strip().lower():
                correct += 1
        total = len(self._session.questions)
        return round((correct / total) * 100, 2) if total else 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_question(row) -> Question:
        options = json.loads(row["options"]) if row["options"] else []
        return Question(
            id=row["id"],
            exam_id=row["exam_id"],
            type=row["type"],
            body=row["body"],
            options=options,
            correct=row["correct"],
            language=row["language"],
            position=row["position"] or 0,
        )
