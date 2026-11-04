"""
VisioExam Application Shell — updated for new UI.
"""

import logging
import sys
from datetime import datetime, timezone

from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut

from core.database import Database
from core.profile_manager import ProfileManager
from core.tts_engine import TTSEngine
from core.braille_display import BrailleDisplay
from core.exam_engine import ExamEngine
from security.encryption import ResponseEncryptor
from security.audit_logger import AuditLogger
from security.kiosk import KioskManager
from security.admin_auth import AdminAuth
from admin.admin_module import AdminModule
from resources.themes.themes import get_theme
from ui.screens.wizard import SetupWizardScreen
from ui.screens.login import CandidateLoginScreen
from ui.screens.exam import ExamScreen
from ui.screens.settings import SettingsScreen
from ui.screens.result import ResultScreen
from ui.screens.admin_login import AdminLoginScreen
from ui.screens.admin_panel import AdminPanelScreen

logger = logging.getLogger(__name__)

SCREEN_WIZARD       = "wizard"
SCREEN_LOGIN        = "login"
SCREEN_EXAM         = "exam"
SCREEN_SETTINGS     = "settings"
SCREEN_RESULT       = "result"
SCREEN_ADMIN_LOGIN  = "admin_login"
SCREEN_ADMIN_PANEL  = "admin_panel"


class VisioExamApp:
    def __init__(self, db: Database, profile_manager: ProfileManager):
        self._db = db
        self._profile_manager = profile_manager

        self._tts = TTSEngine()
        self._braille = BrailleDisplay()
        self._encryptor = ResponseEncryptor()
        self._audit = AuditLogger(db)
        self._auth = AdminAuth(db, self._audit)
        self._admin = AdminModule(db, self._auth, self._audit)

        self._qt_app = QApplication.instance() or QApplication(sys.argv)
        self._qt_app.setApplicationName("VisioExam")
        self._qt_app.aboutToQuit.connect(self.shutdown)

        self._window = QMainWindow()
        self._window.setWindowTitle("VisioExam")
        self._stack = QStackedWidget()
        self._window.setCentralWidget(self._stack)

        self._screens: dict = {}
        self._current_profile = None
        self._kiosk: KioskManager | None = None
        self._exam_start_time = None

        self._tts.set_silent_mode_callback(self._on_tts_unavailable)
        self._build_screens()
        self._apply_theme("dark")   # default dark mode

        admin_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), self._window)
        admin_shortcut.activated.connect(lambda: self.navigate(SCREEN_ADMIN_LOGIN))

        # Keep an emergency way to leave fullscreen kiosk mode. ApplicationShortcut
        # makes this work even when a child widget (for example, an answer field)
        # currently has keyboard focus.
        escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self._window)
        escape_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        escape_shortcut.setAutoRepeat(False)
        escape_shortcut.activated.connect(self._exit_kiosk_on_escape)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self):
        profiles = self._profile_manager.list_all()
        self.navigate(SCREEN_WIZARD if not profiles else SCREEN_LOGIN)
        self._window.showMaximized()
        sys.exit(self._qt_app.exec())

    def shutdown(self):
        if self._kiosk:
            self._kiosk.exit()
            self._kiosk = None
        exam_screen = self._screens.get(SCREEN_EXAM)
        engine = getattr(exam_screen, "_engine", None) if exam_screen else None
        session = getattr(engine, "_session", None) if engine else None
        if session and session.status in ("pending", "active"):
            try:
                engine.abort()
            except Exception as exc:
                logger.error("Could not save exam state during shutdown: %s", exc)
        self._tts.shutdown()
        self._braille.disconnect()
        self._db.close()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, screen_name: str, **kwargs):
        screen = self._screens.get(screen_name)
        if screen is None:
            logger.error(f"Unknown screen: {screen_name}")
            return
        if hasattr(screen, "on_show"):
            screen.on_show(**kwargs)
        self._stack.setCurrentWidget(screen)
        logger.debug(f"Navigated to: {screen_name}")

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self, theme_name: str):
        theme = get_theme(theme_name)
        # Minimal base stylesheet — screens manage their own detailed styles
        self._qt_app.setStyleSheet(f"""
            QMainWindow, QStackedWidget {{ background-color: {theme.bg}; }}
            QMessageBox {{ background-color: {theme.bg}; color: {theme.fg}; }}
            QMessageBox QLabel {{ color: {theme.fg}; }}
            QPushButton {{ font-family: {theme.font_family}; }}
            QLabel {{ font-family: {theme.font_family}; }}
            QLineEdit {{ font-family: {theme.font_family}; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: #30363D; border-radius: 3px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

    def apply_theme_by_name(self, theme_name: str):
        self._apply_theme(theme_name)

    # ------------------------------------------------------------------
    # Kiosk
    # ------------------------------------------------------------------

    def enter_kiosk(self, session_id: str):
        self._exam_start_time = datetime.now(timezone.utc)
        self._kiosk = KioskManager(self._audit, session_id)
        self._kiosk.on_screen_reader_detected(self._on_external_screen_reader)
        self._kiosk.enter()
        self._window.setWindowFlags(Qt.WindowType.Window)
        self._window.showFullScreen()

    def exit_kiosk(self):
        if self._kiosk:
            self._kiosk.exit()
            self._kiosk = None
        self._window.setWindowFlags(Qt.WindowType.Window)
        self._window.showMaximized()

    def _exit_kiosk_on_escape(self):
        """Leave fullscreen kiosk mode while keeping the current screen open."""
        if self._kiosk is not None:
            logger.info("Escape pressed; leaving fullscreen kiosk mode")
            self.exit_kiosk()

    # ------------------------------------------------------------------
    # Screens
    # ------------------------------------------------------------------

    def _build_screens(self):
        ctx = self
        screens = {
            SCREEN_WIZARD:      SetupWizardScreen(ctx),
            SCREEN_LOGIN:       CandidateLoginScreen(ctx),
            SCREEN_EXAM:        ExamScreen(ctx),
            SCREEN_SETTINGS:    SettingsScreen(ctx),
            SCREEN_RESULT:      ResultScreen(ctx),
            SCREEN_ADMIN_LOGIN: AdminLoginScreen(ctx),
            SCREEN_ADMIN_PANEL: AdminPanelScreen(ctx),
        }
        for name, screen in screens.items():
            self._stack.addWidget(screen)
            self._screens[name] = screen

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_tts_unavailable(self, message: str):
        exam_screen = self._screens.get(SCREEN_EXAM)
        if exam_screen and hasattr(exam_screen, "show_status_message"):
            exam_screen.show_status_message(message)

    def _on_external_screen_reader(self, proc_name: str):
        exam_screen = self._screens.get(SCREEN_EXAM)
        if exam_screen and hasattr(exam_screen, "show_status_message"):
            exam_screen.show_status_message(
                f"External screen reader detected: {proc_name}"
            )

    # ------------------------------------------------------------------
    # Service accessors
    # ------------------------------------------------------------------

    @property
    def tts(self) -> TTSEngine:
        return self._tts

    @property
    def braille(self) -> BrailleDisplay:
        return self._braille

    @property
    def db(self) -> Database:
        return self._db

    @property
    def profile_manager(self) -> ProfileManager:
        return self._profile_manager

    @property
    def audit(self) -> AuditLogger:
        return self._audit

    @property
    def auth(self) -> AdminAuth:
        return self._auth

    @property
    def admin(self) -> AdminModule:
        return self._admin

    @property
    def encryptor(self) -> ResponseEncryptor:
        return self._encryptor

    def make_exam_engine(self) -> ExamEngine:
        """Always return a fresh engine — never reuse a stopped one."""
        return ExamEngine(self._db, self._encryptor)
