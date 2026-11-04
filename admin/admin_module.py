"""
Admin Module.
Handles question import (CSV / QTI 3.0 XML), candidate registration,
and results export to CSV.

CSV question format columns:
    id, exam_id, type, body, option_a, option_b, option_c, option_d, correct, language, position

QTI 3.0 XML: parses <assessmentItem> elements following IMS Global QTI 3.0 spec.
"""

import csv
import io
import json
import logging
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from core.database import Database
from security.admin_auth import AdminAuth
from security.audit_logger import AuditLogger, AuditEvent

logger = logging.getLogger(__name__)

QTI_NS = {
    "qti": "http://www.imsglobal.org/xsd/imsqtiasi_v3p0",
    "qti3": "http://www.imsglobal.org/xsd/qti/qtiv3p0/imscp_v1p1",
}


class AdminModule:
    """
    Administrative operations. All mutating methods require prior admin login.
    """

    def __init__(self, db: Database, auth: AdminAuth, audit: AuditLogger):
        self._db = db
        self._auth = auth
        self._audit = audit

    # ------------------------------------------------------------------
    # Exam creation
    # ------------------------------------------------------------------

    def create_exam(
        self,
        title: str,
        time_limit: int = 3600,
        language: str = "en",
        exam_id: str | None = None,
    ) -> str:
        self._auth.require_login()
        eid = exam_id or str(uuid.uuid4())
        self._db.execute(
            """
            INSERT INTO exams (id, title, time_limit, language, created_by)
            VALUES (?,?,?,?,?)
            """,
            (eid, title, time_limit, language, self._auth.current_admin),
        )
        self._db.commit()
        logger.info(f"Exam created: {eid} — '{title}'")
        return eid

    # ------------------------------------------------------------------
    # Question import
    # ------------------------------------------------------------------

    def import_questions_csv(self, file_path: str | Path, exam_id: str) -> int:
        """
        Import questions from a CSV file.
        Returns the number of questions successfully imported.
        """
        self._auth.require_login()
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        count = 0
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    question_type = (row.get("type") or "").strip().lower()
                    if question_type != "mcq":
                        logger.warning(
                            "Skipping non-multiple-choice question %s (type=%s).",
                            row.get("id", ""), question_type or "missing",
                        )
                        continue
                    options = []
                    for col in ("option_a", "option_b", "option_c", "option_d"):
                        val = (row.get(col) or "").strip()
                        if val:
                            options.append(val)
                    body = (row.get("body") or "").strip()
                    correct = (row.get("correct") or "").strip()
                    if not body or len(options) < 2:
                        logger.warning("Skipping incomplete multiple-choice row: %s", row)
                        continue
                    if correct.upper() in ("A", "B", "C", "D"):
                        correct_index = ord(correct.upper()) - ord("A")
                        if correct_index >= len(options):
                            logger.warning("Skipping row with invalid correct option: %s", row)
                            continue
                        correct = options[correct_index]
                    if correct.casefold() not in {option.casefold() for option in options}:
                        logger.warning("Skipping row whose correct answer is not an option: %s", row)
                        continue
                    self._db.execute(
                        """
                        INSERT OR REPLACE INTO questions
                            (id, exam_id, type, body, options, correct, language, position)
                        VALUES (?,?,?,?,?,?,?,?)
                        """,
                        (
                            row.get("id") or str(uuid.uuid4()),
                            exam_id,
                            question_type,
                            body,
                            json.dumps(options),
                            correct,
                            row.get("language", "en").strip(),
                            int(row.get("position", 0) or 0),
                        ),
                    )
                    count += 1
                except (KeyError, ValueError) as exc:
                    logger.warning(f"Skipping malformed CSV row: {exc} — {row}")

        self._db.commit()
        self._audit.log(AuditEvent.EXAM_UPLOAD, f"csv:{path.name}:{count}q")
        logger.info(f"Imported {count} questions from {path.name} into exam {exam_id}.")
        return count

    def import_questions_qti(self, xml_path: str | Path, exam_id: str) -> int:
        """
        Import questions from a QTI 3.0 XML file.
        Returns the number of questions successfully imported.
        """
        self._auth.require_login()
        path = Path(xml_path)
        tree = ET.parse(str(path))
        root = tree.getroot()

        count = 0
        # Try both with and without namespace
        items = root.findall(".//assessmentItem") or root.findall(
            ".//{http://www.imsglobal.org/xsd/imsqtiasi_v3p0}assessmentItem"
        )

        for item in items:
            try:
                qid = item.get("identifier") or str(uuid.uuid4())
                body_el = (
                    item.find(".//itemBody/p")
                    or item.find(".//{http://www.imsglobal.org/xsd/imsqtiasi_v3p0}itemBody/p")
                )
                body = "".join(body_el.itertext()).strip() if body_el else ""

                # Detect question type
                choices = item.findall(".//simpleChoice") or item.findall(
                    ".//{http://www.imsglobal.org/xsd/imsqtiasi_v3p0}simpleChoice"
                )
                if len(choices) < 2:
                    logger.warning("Skipping QTI item without multiple choices: %s", qid)
                    continue
                qtype = "mcq"
                options = ["".join(c.itertext()).strip() for c in choices]
                if not body or any(not option for option in options):
                    logger.warning("Skipping incomplete QTI multiple-choice item: %s", qid)
                    continue

                # Correct response
                correct_el = item.find(".//correctResponse/value") or item.find(
                    ".//{http://www.imsglobal.org/xsd/imsqtiasi_v3p0}correctResponse/"
                    "{http://www.imsglobal.org/xsd/imsqtiasi_v3p0}value"
                )
                correct = "".join(correct_el.itertext()).strip() if correct_el else ""
                choice_ids = [choice.get("identifier", "") for choice in choices]
                if correct in choice_ids:
                    correct = options[choice_ids.index(correct)]
                if correct.casefold() not in {option.casefold() for option in options}:
                    logger.warning("Skipping QTI item with unsupported correct choice: %s", qid)
                    continue

                self._db.execute(
                    """
                    INSERT OR REPLACE INTO questions
                        (id, exam_id, type, body, options, correct, language)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        qid, exam_id, qtype, body,
                        json.dumps(options), correct, "en",
                    ),
                )
                count += 1
            except Exception as exc:
                logger.warning(f"Failed to parse QTI item: {exc}")

        self._db.commit()
        self._audit.log(AuditEvent.EXAM_UPLOAD, f"qti:{path.name}:{count}q")
        logger.info(f"Imported {count} QTI questions into exam {exam_id}.")
        return count

    # ------------------------------------------------------------------
    # Candidate registration
    # ------------------------------------------------------------------

    def register_candidate(
        self,
        candidate_id: str,
        full_name: str,
        language: str = "en",
        modality: str = "audio",
    ) -> bool:
        self._auth.require_login()
        try:
            self._db.execute(
                """
                INSERT INTO candidates (id, full_name, language, modality)
                VALUES (?,?,?,?)
                """,
                (candidate_id, full_name, language, modality),
            )
            self._db.commit()
            self._audit.log(
                AuditEvent.CANDIDATE_REGISTER,
                f"id={candidate_id};name={full_name}",
            )
            return True
        except Exception as exc:
            logger.error(f"Failed to register candidate {candidate_id}: {exc}")
            return False

    def register_candidates_csv(self, file_path: str | Path) -> int:
        self._auth.require_login()
        path = Path(file_path)
        count = 0
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                ok = self.register_candidate(
                    candidate_id=row["id"].strip(),
                    full_name=row["full_name"].strip(),
                    language=row.get("language", "en").strip(),
                    modality=row.get("modality", "audio").strip(),
                )
                if ok:
                    count += 1
        logger.info(f"Registered {count} candidates from {path.name}.")
        return count

    # ------------------------------------------------------------------
    # Results export
    # ------------------------------------------------------------------

    def export_results_csv(self, exam_id: str | None = None) -> str:
        """
        Export session results as a CSV string.
        Include candidate names as well as their IDs so exported rows can be
        matched to the registered candidate roster.
        """
        self._auth.require_login()
        query = """
            SELECT s.id AS session_id, s.candidate_id,
                   COALESCE(c.full_name, '') AS candidate_name,
                   s.exam_id, COALESCE(e.title, '') AS exam_title,
                   s.score, s.started_at, s.ended_at, s.status,
                   (SELECT COUNT(*) FROM responses r
                    WHERE r.session_id=s.id) AS answered
            FROM sessions s
            LEFT JOIN candidates c ON c.id=s.candidate_id
            LEFT JOIN exams e ON e.id=s.exam_id
        """
        params = ()
        if exam_id:
            query += " WHERE s.exam_id=?"
            params = (exam_id,)
        query += " ORDER BY s.started_at, s.id"
        rows = self._db.fetchall(query, params)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "candidate_id", "candidate_name", "session_id", "exam_id",
            "exam_title", "score", "started_at", "ended_at", "status",
            "answered_questions",
        ])
        for row in rows:
            writer.writerow([
                row["candidate_id"], row["candidate_name"], row["session_id"],
                row["exam_id"], row["exam_title"], row["score"],
                row["started_at"], row["ended_at"], row["status"],
                row["answered"],
            ])
        return output.getvalue()

    def save_results_csv(self, file_path: str | Path, exam_id: str | None = None):
        csv_data = self.export_results_csv(exam_id)
        Path(file_path).write_text(csv_data, encoding="utf-8")
        logger.info(f"Results exported to {file_path}.")
