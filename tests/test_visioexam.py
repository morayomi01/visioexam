"""
Unit and integration tests for VisioExam.
Run with:  pytest tests/ -v
"""

import json
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.database import Database
from core.profile_manager import CandidateProfile, ProfileManager
from core.exam_engine import ExamEngine, Question
from security.encryption import ResponseEncryptor
from security.audit_logger import AuditLogger, AuditEvent
from security.admin_auth import AdminAuth
from admin.admin_module import AdminModule


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path=db_path, passphrase="test-key", allow_plaintext=True)
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def profile_manager(tmp_db):
    return ProfileManager(tmp_db)


@pytest.fixture
def encryptor(tmp_path):
    salt = b"0123456789abcdef"
    return ResponseEncryptor(passphrase="test-enc-key", salt=salt)


@pytest.fixture
def audit(tmp_db):
    return AuditLogger(tmp_db, hmac_key="test-hmac-key")


@pytest.fixture
def admin_auth(tmp_db, audit):
    return AdminAuth(tmp_db, audit)


@pytest.fixture
def admin_module(tmp_db, admin_auth, audit):
    return AdminModule(tmp_db, admin_auth, audit)


@pytest.fixture
def exam_engine(tmp_db, encryptor):
    return ExamEngine(tmp_db, encryptor)


@pytest.fixture
def sample_profile():
    return CandidateProfile(
        id="TEST001",
        full_name="Adaeze Obi",
        language="yo",
        modality="audio",
        speech_rate=1.0,
        font_size=20,
        contrast="dark",
    )


@pytest.fixture
def sample_exam_in_db(tmp_db):
    exam_id = str(uuid.uuid4())
    tmp_db.execute(
        "INSERT INTO exams (id, title, time_limit, language) VALUES (?,?,?,?)",
        (exam_id, "Test Exam", 3600, "en"),
    )
    questions = [
        (str(uuid.uuid4()), exam_id, "mcq", "What is 2 + 2?",
         json.dumps(["3", "4", "5", "6"]), "4", "en", 1),
        (str(uuid.uuid4()), exam_id, "tf", "The sky is blue.",
         json.dumps(["True", "False"]), "True", "en", 2),
        (str(uuid.uuid4()), exam_id, "short_answer", "Name the capital of Nigeria.",
         json.dumps([]), "Abuja", "en", 3),
    ]
    tmp_db.executemany(
        "INSERT INTO questions (id, exam_id, type, body, options, correct, language, position)"
        " VALUES (?,?,?,?,?,?,?,?)",
        questions,
    )
    tmp_db.commit()
    return exam_id


# ---------------------------------------------------------------------------
# Profile Manager tests
# ---------------------------------------------------------------------------

class TestProfileManager:
    def test_create_and_retrieve(self, profile_manager, sample_profile):
        profile_manager.create(sample_profile)
        retrieved = profile_manager.get("TEST001")
        assert retrieved is not None
        assert retrieved.full_name == "Adaeze Obi"
        assert retrieved.language == "yo"

    def test_update_profile(self, profile_manager, sample_profile):
        profile_manager.create(sample_profile)
        sample_profile.speech_rate = 1.5
        profile_manager.update(sample_profile)
        updated = profile_manager.get("TEST001")
        assert updated.speech_rate == 1.5

    def test_upsert_creates_if_not_exists(self, profile_manager, sample_profile):
        profile_manager.upsert(sample_profile)
        assert profile_manager.exists("TEST001")

    def test_delete(self, profile_manager, sample_profile):
        profile_manager.create(sample_profile)
        profile_manager.delete("TEST001")
        assert not profile_manager.exists("TEST001")

    def test_invalid_language_raises(self, profile_manager):
        bad = CandidateProfile(id="X", full_name="Test", language="xx")
        with pytest.raises(ValueError):
            profile_manager.create(bad)

    def test_invalid_speech_rate_raises(self, profile_manager):
        bad = CandidateProfile(id="X", full_name="Test", speech_rate=3.0)
        with pytest.raises(ValueError):
            profile_manager.create(bad)

    def test_list_all(self, profile_manager, sample_profile):
        profile_manager.create(sample_profile)
        p2 = CandidateProfile(id="TEST002", full_name="Emmanuel Chukwu")
        profile_manager.create(p2)
        all_profiles = profile_manager.list_all()
        assert len(all_profiles) == 2


# ---------------------------------------------------------------------------
# Encryption tests
# ---------------------------------------------------------------------------

class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self, encryptor):
        plaintext = "Option B"
        token = encryptor.encrypt(plaintext)
        assert encryptor.decrypt(token) == plaintext

    def test_ciphertext_differs_from_plaintext(self, encryptor):
        token = encryptor.encrypt("Option A")
        assert "Option A" not in token

    def test_each_encrypt_produces_different_ciphertext(self, encryptor):
        t1 = encryptor.encrypt("same text")
        t2 = encryptor.encrypt("same text")
        assert t1 != t2   # different nonces

    def test_tampered_ciphertext_raises(self, encryptor):
        import base64
        token = encryptor.encrypt("hello")
        raw = bytearray(base64.b64decode(token))
        raw[-1] ^= 0xFF   # flip last byte
        bad_token = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(Exception):
            encryptor.decrypt(bad_token)


# ---------------------------------------------------------------------------
# Audit Logger tests
# ---------------------------------------------------------------------------

class TestAuditLogger:
    def test_log_and_retrieve(self, audit):
        audit.log(AuditEvent.EXAM_START, "exam=abc", "session-1")
        entries = audit.export_log("session-1")
        assert len(entries) == 1
        assert entries[0]["event_type"] == AuditEvent.EXAM_START

    def test_hmac_verification_passes_on_clean_log(self, audit):
        audit.log(AuditEvent.ADMIN_LOGIN, "admin=test")
        tampered = audit.verify_log()
        assert tampered == []

    def test_hmac_verification_detects_tampering(self, tmp_db, audit):
        audit.log(AuditEvent.EXAM_START, "detail=test", "session-x")
        # Manually corrupt the hmac
        tmp_db.execute("UPDATE audit_log SET hmac='deadbeef' WHERE id=1")
        tmp_db.commit()
        tampered = audit.verify_log()
        assert len(tampered) == 1
        assert tampered[0]["reason"] == "HMAC mismatch"


# ---------------------------------------------------------------------------
# Admin Auth tests
# ---------------------------------------------------------------------------

class TestAdminAuth:
    def test_create_and_login(self, admin_auth):
        admin_auth.create_admin("admin", "SecurePass123!")
        assert admin_auth.login("admin", "SecurePass123!")
        assert admin_auth.is_logged_in()

    def test_wrong_password_rejected(self, admin_auth):
        admin_auth.create_admin("admin2", "RealPass")
        assert not admin_auth.login("admin2", "WrongPass")

    def test_logout(self, admin_auth):
        admin_auth.create_admin("admin3", "Pass")
        admin_auth.login("admin3", "Pass")
        admin_auth.logout()
        assert not admin_auth.is_logged_in()

    def test_duplicate_admin_rejected(self, admin_auth):
        admin_auth.create_admin("dup", "pass")
        assert not admin_auth.create_admin("dup", "pass2")


# ---------------------------------------------------------------------------
# Exam Engine tests
# ---------------------------------------------------------------------------

class TestExamEngine:
    def test_load_exam_creates_session(self, exam_engine, sample_exam_in_db, profile_manager, sample_profile):
        profile_manager.create(sample_profile)
        session = exam_engine.load_exam(sample_exam_in_db, "TEST001")
        assert session is not None
        assert len(session.questions) == 3

    def test_question_randomization(self, exam_engine, sample_exam_in_db, profile_manager, sample_profile):
        profile_manager.create(sample_profile)
        orders = set()
        for _ in range(10):
            eng2 = ExamEngine.__new__(ExamEngine)
            eng2._db = exam_engine._db
            eng2._encryptor = exam_engine._encryptor
            eng2._session = None
            eng2._stop_event = __import__("threading").Event()
            eng2._timer_thread = None
            eng2._autosave_thread = None
            eng2._on_countdown = None
            eng2._on_time_up = None
            eng2._on_autosave = None
            sess = eng2.load_exam(sample_exam_in_db, "TEST001")
            orders.add(tuple(q.id for q in sess.questions))
        # With 3 questions and 10 runs, very likely to have > 1 order
        assert len(orders) > 1

    def test_answer_and_unanswered_count(self, exam_engine, sample_exam_in_db, profile_manager, sample_profile):
        profile_manager.create(sample_profile)
        exam_engine.load_exam(sample_exam_in_db, "TEST001")
        assert exam_engine.unanswered_count() == 3
        q = exam_engine.current_question()
        exam_engine.answer(q.id, "4")
        assert exam_engine.unanswered_count() == 2

    def test_flag_and_unflag(self, exam_engine, sample_exam_in_db, profile_manager, sample_profile):
        profile_manager.create(sample_profile)
        exam_engine.load_exam(sample_exam_in_db, "TEST001")
        q = exam_engine.current_question()
        exam_engine.flag(q.id)
        assert exam_engine.is_flagged(q.id)
        exam_engine.unflag(q.id)
        assert not exam_engine.is_flagged(q.id)

    def test_navigation(self, exam_engine, sample_exam_in_db, profile_manager, sample_profile):
        profile_manager.create(sample_profile)
        exam_engine.load_exam(sample_exam_in_db, "TEST001")
        q0 = exam_engine.current_question()
        exam_engine.next_question()
        q1 = exam_engine.current_question()
        assert q0.id != q1.id
        exam_engine.prev_question()
        assert exam_engine.current_question().id == q0.id

    def test_submit_returns_results(self, exam_engine, sample_exam_in_db, profile_manager, sample_profile):
        profile_manager.create(sample_profile)
        session = exam_engine.load_exam(sample_exam_in_db, "TEST001")
        # Answer correctly
        for q in session.questions:
            exam_engine.answer(q.id, q.correct)
        exam_engine._stop_event.set()   # suppress timer threads
        results = exam_engine.submit()
        assert results["answered"] == 3
        assert results["total"] == 3


# ---------------------------------------------------------------------------
# Admin Module tests
# ---------------------------------------------------------------------------

class TestAdminModule:
    def _login(self, admin_auth):
        admin_auth.create_admin("testadmin", "AdminPass!")
        admin_auth.login("testadmin", "AdminPass!")

    def test_create_exam(self, admin_module, admin_auth):
        self._login(admin_auth)
        eid = admin_module.create_exam("Maths Paper 1", time_limit=1800)
        assert eid

    def test_import_csv(self, admin_module, admin_auth, tmp_db, tmp_path):
        self._login(admin_auth)
        eid = admin_module.create_exam("CSV Test Exam")
        csv_content = (
            "id,exam_id,type,body,option_a,option_b,option_c,option_d,correct,language,position\n"
            f"{uuid.uuid4()},{eid},mcq,What colour is grass?,Red,Green,Blue,Yellow,Green,en,1\n"
            f"{uuid.uuid4()},{eid},tf,Water is wet.,True,False,,,True,en,2\n"
        )
        csv_path = tmp_path / "questions.csv"
        csv_path.write_text(csv_content)
        n = admin_module.import_questions_csv(str(csv_path), eid)
        assert n == 2

    def test_register_candidate(self, admin_module, admin_auth):
        self._login(admin_auth)
        ok = admin_module.register_candidate("CAND001", "Test Student", "en", "audio")
        assert ok

    def test_export_results_csv(self, admin_module, admin_auth):
        self._login(admin_auth)
        csv_data = admin_module.export_results_csv()
        assert "candidate_id" in csv_data

    def test_requires_login(self, admin_module):
        with pytest.raises(PermissionError):
            admin_module.create_exam("No Auth Exam")
