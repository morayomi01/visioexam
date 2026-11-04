"""
Exam Screen — matches VisionExam dark UI design from screenshots.
Left sidebar: candidate info + nav links + access tools.
Main area: question counter, replay button, question body, MCQ options.
Right sidebar: Exam Progress grid with colour-coded question status.
Top bar: language switcher + TTS + lock + profile icons.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QFrame, QScrollArea, QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QFont

from core.exam_engine import ExamEngine
from core.math_speech import math_to_speech
from security.audit_logger import AuditEvent

logger = logging.getLogger(__name__)

DARK = {
    "bg": "#0D1117", "sidebar": "#161B22", "card": "#1C2128",
    "border": "#30363D", "text": "#E6EDF3", "muted": "#8B949E",
    "accent": "#2F81F7", "accent_text": "#FFFFFF",
    "success": "#3FB950", "warning": "#D29922", "danger": "#F85149",
    "opt_bg": "#1C2128", "opt_border": "#30363D",
    "opt_selected_bg": "#1C2128", "opt_selected_border": "#2F81F7",
    "opt_selected_check": "#2F81F7",
    "nav_active": "#1C2128", "nav_active_border": "#2F81F7",
    "progress_current": "#2F81F7", "progress_answered": "#30363D",
    "progress_unanswered": "#0D1117", "progress_flagged": "#D29922",
    "btn_prev": "#21262D", "btn_next": "#2F81F7",
}

LIGHT = {
    "bg": "#F6F8FA", "sidebar": "#FFFFFF", "card": "#FFFFFF",
    "border": "#D0D7DE", "text": "#1F2328", "muted": "#656D76",
    "accent": "#0969DA", "accent_text": "#FFFFFF",
    "success": "#1A7F37", "warning": "#9A6700", "danger": "#CF222E",
    "opt_bg": "#FFFFFF", "opt_border": "#D0D7DE",
    "opt_selected_bg": "#F0F6FF", "opt_selected_border": "#0969DA",
    "opt_selected_check": "#0969DA",
    "nav_active": "#F0F6FF", "nav_active_border": "#0969DA",
    "progress_current": "#0969DA", "progress_answered": "#D0D7DE",
    "progress_unanswered": "#F6F8FA", "progress_flagged": "#9A6700",
    "btn_prev": "#F6F8FA", "btn_next": "#0969DA",
}


def _opt_style(t, selected=False):
    if selected:
        return f"""
            QPushButton {{
                background-color: {t['opt_selected_bg']};
                color: {t['text']};
                border: 2px solid {t['opt_selected_border']};
                border-radius: 10px; padding: 14px 16px;
                font-size: 15px; text-align: left;
            }}
        """
    return f"""
        QPushButton {{
            background-color: {t['opt_bg']};
            color: {t['text']};
            border: 1px solid {t['opt_border']};
            border-radius: 10px; padding: 14px 16px;
            font-size: 15px; text-align: left;
        }}
        QPushButton:hover {{ border-color: {t['accent']}; }}
    """


class ExamScreen(QWidget):
    _countdown_signal = pyqtSignal(int)
    _time_up_signal = pyqtSignal()
    _autosave_signal = pyqtSignal()

    def __init__(self, app_ctx):
        super().__init__()
        # The engine's timer/autosave callbacks run on Python worker threads.
        # Qt signals queue these UI updates safely onto the GUI thread.
        self._countdown_signal.connect(self._on_countdown)
        self._time_up_signal.connect(self._on_time_up)
        self._autosave_signal.connect(
            lambda: self.show_status_message("Progress saved.")
        )
        self._ctx = app_ctx
        self._engine: ExamEngine | None = None
        self._option_widgets: list[QPushButton] = []
        self._progress_btns: list[QPushButton] = []
        self._first_question_pending = False
        self._selected_option: int = -1
        self._display_question_body = ""
        self._display_options: list[str] = []
        self._display_language = "en"
        self._first_question_pending = False
        self._t = DARK
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left sidebar ──────────────────────────────────────────────
        self._sidebar = QFrame()
        self._sidebar.setFixedWidth(220)
        self._sidebar.setObjectName("sidebar")
        sb_layout = QVBoxLayout(self._sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        # Top bar inside sidebar
        top_bar = QFrame()
        top_bar.setFixedHeight(56)
        top_bar.setObjectName("topBar")
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        brand = QLabel("VisionExam")
        brand.setStyleSheet("font-size: 16px; font-weight: 700;")
        tb_layout.addWidget(brand)
        sb_layout.addWidget(top_bar)

        # Profile card
        profile_card = QFrame()
        profile_card.setObjectName("profileCard")
        pc_layout = QVBoxLayout(profile_card)
        pc_layout.setContentsMargins(16, 16, 16, 16)
        pc_layout.setSpacing(4)
        avatar = QLabel("👤")
        avatar.setStyleSheet("font-size: 28px;")
        self._candidate_id_lbl = QLabel("ID: ------")
        self._candidate_id_lbl.setStyleSheet("font-size: 15px; font-weight: 700;")
        self._session_lbl = QLabel("● Secure Session")
        self._session_lbl.setStyleSheet("font-size: 12px; color: #3FB950;")
        pc_layout.addWidget(avatar)
        pc_layout.addWidget(self._candidate_id_lbl)
        pc_layout.addWidget(self._session_lbl)
        sb_layout.addWidget(profile_card)

        # Nav items
        self._nav_dashboard = self._make_nav_btn("⊞  Dashboard", False)
        self._nav_current   = self._make_nav_btn("▣  Current Exam", True)
        self._nav_settings  = self._make_nav_btn("⚙  Settings", False)
        self._nav_dashboard.clicked.connect(lambda: self._ctx.navigate("login"))
        self._nav_settings.clicked.connect(lambda: self._ctx.navigate("settings"))
        sb_layout.addWidget(self._nav_dashboard)
        sb_layout.addWidget(self._nav_current)
        sb_layout.addWidget(self._nav_settings)

        # Access tools section
        tools_header = QLabel("  ACCESS TOOLS")
        tools_header.setStyleSheet("font-size: 11px; font-weight: 700; padding: 16px 16px 4px;")
        sb_layout.addWidget(tools_header)

        self._vol_btn = self._make_nav_btn("🔊  Volume", False)
        self._con_btn = self._make_nav_btn("◑  Contrast", False)
        self._txt_btn = self._make_nav_btn("𝗔  Text Size", False)
        self._vol_btn.clicked.connect(self._toggle_volume)
        self._con_btn.clicked.connect(self._toggle_contrast)
        self._txt_btn.clicked.connect(self._cycle_text_size)
        sb_layout.addWidget(self._vol_btn)
        sb_layout.addWidget(self._con_btn)
        sb_layout.addWidget(self._txt_btn)

        sb_layout.addStretch()

        # Proctor active badge
        proctor_badge = QLabel("  Proctor Active")
        proctor_badge.setObjectName("proctorBadge")
        proctor_badge.setStyleSheet("""
            font-size: 13px; font-weight: 700;
            color: #3FB950; padding: 12px 16px;
        """)
        sb_layout.addWidget(proctor_badge)

        root.addWidget(self._sidebar)

        # ── Main content area ─────────────────────────────────────────
        main_frame = QFrame()
        main_frame.setObjectName("mainFrame")
        main_layout = QVBoxLayout(main_frame)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar (language + icons)
        self._topbar = QFrame()
        self._topbar.setFixedHeight(56)
        self._topbar.setObjectName("mainTopBar")
        tb2 = QHBoxLayout(self._topbar)
        tb2.setContentsMargins(24, 0, 24, 0)
        self._exit_fullscreen_btn = QPushButton("Exit full screen  (Esc)")
        self._exit_fullscreen_btn.setMinimumHeight(36)
        self._exit_fullscreen_btn.setToolTip("Leave full-screen mode; the exam remains open")
        self._exit_fullscreen_btn.clicked.connect(self._ctx.exit_kiosk)
        self._exit_fullscreen_btn.setStyleSheet(
            "QPushButton { background:#21262D; color:#F0F6FC; border:1px solid #6E7681; "
            "border-radius:7px; padding:5px 12px; font-weight:600; } "
            "QPushButton:hover { background:#30363D; }"
        )
        tb2.addWidget(self._exit_fullscreen_btn)
        tb2.addStretch()
        self._lang_row = QHBoxLayout()
        self._lang_row.setSpacing(4)
        self._lang_toggle_btns = {}
        for code in ["EN", "YO", "HA", "IG"]:
            btn = QPushButton(code)
            btn.setFixedSize(40, 32)
            btn.setObjectName(f"langToggle_{code}")
            lang_capture = code.lower()
            btn.clicked.connect(lambda _, l=lang_capture: self._switch_lang(l))
            self._lang_row.addWidget(btn)
            self._lang_toggle_btns[code] = btn
        tb2.addLayout(self._lang_row)
        tb2.addSpacing(16)
        tts_btn = QPushButton("🔊")
        tts_btn.setFixedSize(36, 36)
        tts_btn.setToolTip("Toggle TTS")
        tts_btn.clicked.connect(self._replay_audio)
        tb2.addWidget(tts_btn)
        lock_btn = QPushButton("🔒")
        lock_btn.setFixedSize(36, 36)
        lock_btn.setObjectName("lockBtn")
        lock_btn.setToolTip("Kiosk lock status")
        lock_btn.clicked.connect(self._show_lock_status)
        tb2.addWidget(lock_btn)
        profile_btn = QPushButton("👤")
        profile_btn.setFixedSize(36, 36)
        profile_btn.setToolTip("Candidate profile")
        profile_btn.clicked.connect(self._show_profile_info)
        tb2.addWidget(profile_btn)
        main_layout.addWidget(self._topbar)

        # Content row: question area + right panel
        content_row = QHBoxLayout()
        content_row.setContentsMargins(14, 10, 14, 10)
        content_row.setSpacing(12)

        # Question panel
        q_panel = QFrame()
        q_panel.setObjectName("qPanel")
        q_layout = QVBoxLayout(q_panel)
        q_layout.setContentsMargins(20, 16, 20, 16)
        q_layout.setSpacing(10)

        # Counter row
        counter_row = QHBoxLayout()
        self._counter_label = QLabel("Question 1 of 1")
        self._counter_label.setObjectName("counterLabel")
        self._counter_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        self._replay_btn = QPushButton("↻  Replay Question")
        self._replay_btn.setObjectName("replayBtn")
        self._replay_btn.setMinimumHeight(36)
        self._replay_btn.clicked.connect(self._replay_audio)
        counter_row.addWidget(self._counter_label)
        counter_row.addStretch()
        counter_row.addWidget(self._replay_btn)
        q_layout.addLayout(counter_row)

        # Status bar
        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        q_layout.addWidget(self._status_label)

        # Question body card
        self._q_card = QFrame()
        self._q_card.setObjectName("qCard")
        q_card_layout = QVBoxLayout(self._q_card)
        q_card_layout.setContentsMargins(24, 20, 24, 20)
        q_card_layout.setSpacing(10)
        self._question_label = QLabel("")
        self._question_label.setWordWrap(True)
        self._question_label.setObjectName("questionLabel")
        self._question_label.setStyleSheet("font-size: 20px; font-weight: 700; line-height: 1.4;")
        self._instruction_label = QLabel("Select the most appropriate answer from the choices below. Use the keyboard shortcuts indicated for faster selection.")
        self._instruction_label.setWordWrap(True)
        self._instruction_label.setObjectName("instructionLabel")
        self._instruction_label.setStyleSheet("font-size: 13px;")
        q_card_layout.addWidget(self._question_label)
        q_card_layout.addWidget(self._instruction_label)
        q_layout.addWidget(self._q_card)

        # Options area
        self._options_area = QVBoxLayout()
        self._options_area.setSpacing(10)
        q_layout.addLayout(self._options_area)

        q_layout.addStretch()

        # Timer
        self._timer_label = QLabel("Time: --:--")
        self._timer_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        q_layout.addWidget(self._timer_label)

        # Navigation buttons
        nav_row = QHBoxLayout()
        self._btn_prev = QPushButton("←  Previous")
        self._btn_prev.setMinimumHeight(48)
        self._btn_prev.setObjectName("prevBtn")
        self._btn_prev.clicked.connect(self._go_prev)
        self._btn_next = QPushButton("Next Question  →")
        self._btn_next.setMinimumHeight(48)
        self._btn_next.setObjectName("nextBtn")
        self._btn_next.clicked.connect(self._go_next)
        nav_row.addWidget(self._btn_prev)
        nav_row.addStretch()
        nav_row.addWidget(self._btn_next)
        q_layout.addLayout(nav_row)

        content_row.addWidget(q_panel, 3)

        # ── Right panel: Exam Progress ────────────────────────────────
        self._right_panel = QFrame()
        self._right_panel.setFixedWidth(220)
        self._right_panel.setObjectName("rightPanel")
        rp_layout = QVBoxLayout(self._right_panel)
        rp_layout.setContentsMargins(16, 16, 16, 16)
        rp_layout.setSpacing(12)

        progress_title = QLabel("Exam Progress")
        progress_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        rp_layout.addWidget(progress_title)

        self._progress_grid = QGridLayout()
        self._progress_grid.setSpacing(6)
        progress_container = QWidget()
        progress_container.setLayout(self._progress_grid)
        scroll = QScrollArea()
        scroll.setWidget(progress_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        rp_layout.addWidget(scroll)

        # Legend
        legend_layout = QVBoxLayout()
        legend_layout.setSpacing(4)
        for label, color in [
            ("Current", "#2F81F7"),
            ("Answered", "#30363D"),
            ("Unanswered", "#0D1117"),
            ("Flagged for review", "#D29922"),
        ]:
            row = QHBoxLayout()
            dot = QFrame()
            dot.setFixedSize(14, 14)
            dot.setStyleSheet(f"background:{color}; border-radius:3px;")
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 12px;")
            row.addWidget(dot)
            row.addWidget(lbl)
            row.addStretch()
            legend_layout.addLayout(row)
        rp_layout.addLayout(legend_layout)

        # Flag + Submit
        self._flag_btn = QPushButton("⚑  Flag for Review  (F)")
        self._flag_btn.setMinimumHeight(40)
        self._flag_btn.setObjectName("flagBtn")
        self._flag_btn.clicked.connect(self._toggle_flag)
        rp_layout.addWidget(self._flag_btn)

        self._submit_btn = QPushButton("Submit Exam")
        self._submit_btn.setMinimumHeight(44)
        self._submit_btn.setObjectName("submitBtn")
        self._submit_btn.clicked.connect(self._prompt_submit)
        rp_layout.addWidget(self._submit_btn)

        content_row.addWidget(self._right_panel)
        content_widget = QWidget()
        content_widget.setLayout(content_row)
        self._content_scroll = QScrollArea()
        self._content_scroll.setObjectName("examContentScroll")
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content_scroll.setWidget(content_widget)
        main_layout.addWidget(self._content_scroll, 1)
        root.addWidget(main_frame, 1)

        # Timer
        self._display_timer = QTimer(self)
        self._display_timer.setInterval(1000)
        self._display_timer.timeout.connect(self._tick_display)
        self._remaining_seconds = 0

        self._apply_theme()

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self):
        t = self._t
        self.setStyleSheet(f"background-color: {t['bg']};")
        self._content_scroll.setStyleSheet(f"""
            QScrollArea#examContentScroll {{ background-color: {t['bg']}; border: none; }}
            QScrollBar:vertical {{ background: {t['sidebar']}; width: 14px; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: {t['border']}; min-height: 36px; border-radius: 6px; }}
            QScrollBar::handle:vertical:hover {{ background: {t['muted']}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar:horizontal {{ background: {t['sidebar']}; height: 14px; margin: 2px; }}
            QScrollBar::handle:horizontal {{ background: {t['border']}; min-width: 36px; border-radius: 6px; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        """)

        self._sidebar.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {t['sidebar']};
                border-right: 1px solid {t['border']};
            }}
            QLabel {{ color: {t['text']}; background: transparent; }}
        """)
        self._topbar.setStyleSheet(f"""
            QFrame#mainTopBar {{
                background-color: {t['sidebar']};
                border-bottom: 1px solid {t['border']};
            }}
        """)

        # Language toggle buttons in topbar
        for code, btn in self._lang_toggle_btns.items():
            is_en = code == "EN"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {"#30363D" if is_en else "transparent"};
                    color: {t['text']};
                    border: {"1px solid "+t['accent'] if is_en else "none"};
                    border-radius: 16px; font-size: 12px; font-weight: 600;
                }}
                QPushButton:hover {{ background-color: {t['card']}; }}
            """)

        self._right_panel.setStyleSheet(f"""
            QFrame#rightPanel {{
                background-color: {t['sidebar']};
                border-left: 1px solid {t['border']};
            }}
            QLabel {{ color: {t['text']}; background: transparent; }}
            QScrollArea {{ background: transparent; }}
            QWidget {{ background: transparent; }}
        """)

        self._q_card.setStyleSheet(f"""
            QFrame#qCard {{
                background-color: {t['card']};
                border: 1px solid {t['border']};
                border-radius: 10px;
            }}
            QLabel {{ color: {t['text']}; background: transparent; }}
        """)

        self._question_label.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {t['text']};"
        )
        self._instruction_label.setStyleSheet(
            f"font-size: 13px; color: {t['muted']};"
        )
        self._counter_label.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {t['text']};"
            f" background: {t['card']}; border: 1px solid {t['border']};"
            f" border-radius: 8px; padding: 4px 12px;"
        )
        self._replay_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['card']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px; font-size: 13px; padding: 4px 14px;
            }}
            QPushButton:hover {{ border-color: {t['accent']}; }}
        """)
        self._status_label.setStyleSheet(f"font-size: 13px; color: {t['warning']};")
        self._timer_label.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {t['muted']};"
        )
        self._btn_prev.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['btn_prev']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px; font-size: 14px; font-weight: 600; padding: 0 20px;
            }}
            QPushButton:hover {{ border-color: {t['accent']}; }}
        """)
        self._btn_next.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['btn_next']};
                color: white;
                border: none; border-radius: 8px;
                font-size: 14px; font-weight: 700; padding: 0 20px;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        self._flag_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t['warning']};
                border: 1px solid {t['warning']};
                border-radius: 8px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {t['card']}; }}
        """)
        self._submit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['success']};
                color: white; border: none;
                border-radius: 8px; font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        # Nav buttons
        for btn, active in [
            (self._nav_dashboard, False),
            (self._nav_current, True),
            (self._nav_settings, False),
            (self._vol_btn, False),
            (self._con_btn, False),
            (self._txt_btn, False),
        ]:
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {t['nav_active']};
                        color: {t['accent']};
                        border-left: 3px solid {t['accent']};
                        border-top: none; border-right: none; border-bottom: none;
                        text-align: left; padding: 10px 16px; font-size: 14px;
                        font-weight: 600;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {t['muted']};
                        border: none; text-align: left;
                        padding: 10px 16px; font-size: 14px;
                    }}
                    QPushButton:hover {{ color: {t['text']}; background-color: {t['card']}; }}
                """)

    def _make_nav_btn(self, text: str, active: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumHeight(40)
        btn.setFlat(True)
        return btn

    # ------------------------------------------------------------------
    # on_show
    # ------------------------------------------------------------------

    def on_show(self, candidate_id: str = "", **kwargs):
        if not candidate_id:
            return
        profile = self._ctx.profile_manager.get(candidate_id)
        if not profile:
            return

        # Sync theme with profile contrast
        self._t = DARK if profile.contrast in ("dark", "hcyob") else LIGHT
        self._apply_theme()

        self._candidate_id_lbl.setText(f"ID: {candidate_id}")

        exam_row = self._ctx.db.fetchone("SELECT id FROM exams LIMIT 1")
        if not exam_row:
            self.show_status_message("No exam available. Contact administrator.")
            return

        self._engine = self._ctx.make_exam_engine()
        session = self._engine.load_exam(exam_row["id"], candidate_id)

        self._engine.on_countdown(self._countdown_signal.emit)
        self._engine.on_time_up(self._time_up_signal.emit)
        self._engine.on_autosave(self._autosave_signal.emit)

        self._ctx.enter_kiosk(session.id)
        self._ctx.audit.log(AuditEvent.EXAM_START, f"exam={exam_row['id']}", session.id)

        # Build progress grid
        self._build_progress_grid(len(session.questions))

        self._engine.start()
        self._remaining_seconds = session.time_limit
        self._display_timer.start()
        self._first_question_pending = True

        QTimer.singleShot(800, self._render_current_question)

    # ------------------------------------------------------------------
    # Progress grid
    # ------------------------------------------------------------------

    def _build_progress_grid(self, total: int):
        while self._progress_grid.count():
            item = self._progress_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._progress_btns.clear()

        cols = 4
        for i in range(total):
            btn = QPushButton(str(i + 1))
            btn.setFixedSize(44, 44)
            btn.setStyleSheet(self._progress_btn_style(i, "unanswered"))
            idx = i
            btn.clicked.connect(lambda _, x=idx: self._goto_question(x))
            self._progress_grid.addWidget(btn, i // cols, i % cols)
            self._progress_btns.append(btn)

    def _progress_btn_style(self, idx: int, state: str) -> str:
        t = self._t
        if state == "current":
            bg, fg, border = t['progress_current'], "#FFFFFF", t['progress_current']
        elif state == "answered":
            bg, fg, border = t['progress_answered'], t['text'], t['border']
        elif state == "flagged":
            bg, fg, border = "transparent", t['warning'], t['warning']
        else:
            bg, fg, border = t['progress_unanswered'], t['muted'], t['border']
        return f"""
            QPushButton {{
                background-color: {bg}; color: {fg};
                border: 1.5px solid {border}; border-radius: 6px;
                font-size: 13px; font-weight: 600;
            }}
        """

    def _update_progress_grid(self):
        if not self._engine or not self._engine._session:
            return
        session = self._engine._session
        for i, q in enumerate(session.questions):
            if i >= len(self._progress_btns):
                break
            if i == session.current_index:
                state = "current"
            elif q.id in self._engine._session.flagged:
                state = "flagged"
            elif q.id in session.responses:
                state = "answered"
            else:
                state = "unanswered"
            self._progress_btns[i].setStyleSheet(self._progress_btn_style(i, state))

    def _goto_question(self, index: int):
        if self._engine:
            self._engine.goto_question(index)
            self._render_current_question()

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render_current_question(self):
        if not self._engine:
            return
        q = self._engine.current_question()
        if q is None:
            return

        session = self._engine._session
        idx = session.current_index
        total = len(session.questions)
        profile = self._ctx._current_profile
        t = self._t

        selected_language = profile.language if profile else "en"
        # Keep question text and choices exactly as entered by the examiner.
        # The candidate's language preference selects only the speech backend.
        self._display_question_body = q.body
        self._display_options = list(q.options)
        self._display_language = selected_language

        self._counter_label.setText(f"Question {idx + 1} of {total}")
        self._status_label.clear()
        self._question_label.setText(self._display_question_body)
        self._flag_btn.setText(
            "★  Flagged  (F)" if self._engine.is_flagged(q.id) else "⚑  Flag for Review  (F)"
        )

        # Clear options
        while self._options_area.count():
            item = self._options_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._option_widgets.clear()
        self._selected_option = -1

        if q.type == "mcq":
            existing = session.responses.get(q.id, "")
            for i, opt in enumerate(self._display_options):
                selected = (i < len(q.options) and existing == q.options[i])
                letter = chr(65 + i)

                row = QHBoxLayout()
                row.setSpacing(0)

                # Letter badge
                badge_frame = QFrame()
                badge_frame.setFixedSize(36, 36)
                badge_frame.setStyleSheet(
                    f"background-color: {t['accent'] if selected else t['card']};"
                    f"border-radius: 6px; border: 1px solid {t['border']};"
                )
                badge_lbl = QLabel(letter, badge_frame)
                badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge_lbl.setGeometry(0, 0, 36, 36)
                badge_lbl.setStyleSheet(
                    f"color: {'white' if selected else t['text']}; font-weight: 700;"
                    " font-size: 14px; background: transparent;"
                )

                # Option button
                btn = QPushButton(f"  {letter}.  {opt}")
                btn.setMinimumHeight(56)
                btn.setStyleSheet(_opt_style(t, selected))
                if selected:
                    self._selected_option = i

                # Shortcut hint label
                hint = QLabel(f"Press '{letter}'")
                hint.setStyleSheet(
                    f"font-size: 11px; color: {t['muted']}; padding: 2px 8px;"
                    f" background: {t['card']}; border: 1px solid {t['border']};"
                    " border-radius: 4px;"
                )
                hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                # Checkmark if selected
                check_lbl = QLabel("✓" if selected else "○")
                check_lbl.setFixedWidth(24)
                check_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                check_lbl.setStyleSheet(
                    f"color: {t['opt_selected_check'] if selected else t['muted']};"
                    " font-size: 16px; background: transparent;"
                )

                ii = i
                btn.clicked.connect(lambda _, x=ii: self._select_option(x))
                self._options_area.addWidget(btn)
                self._option_widgets.append(btn)
        self._update_progress_grid()

        lang = self._display_language
        rate = profile.speech_rate if profile else 1.0
        speech = f"Question {idx + 1} of {total}. {math_to_speech(self._display_question_body)}"
        for i, opt in enumerate(self._display_options):
            speech += f". Option {chr(65+i)}: {math_to_speech(opt)}"
        if self._first_question_pending:
            self._first_question_pending = False
            if lang in ("yo", "ha", "ig"):
                self._ctx.tts.speak(
                    "Please wait while I prepare the first question audio. "
                    "Speech in this language can take about a minute on this computer.",
                    language="en",
                    interrupt=False,
                )
            # Queue the question after the login welcome/progress notice;
            # interrupting them during neural synthesis made the exam seem silent.
            self._ctx.tts.speak(speech, language=lang, rate=rate, interrupt=False)
        else:
            self._ctx.tts.speak(speech, language=lang, rate=rate)
        self._ctx.braille.display(
            f"Q{idx+1}/{total}: {self._display_question_body}", language=lang
        )
        self._ctx.audit.log(
            AuditEvent.QUESTION_NAV, f"q_index={idx}",
            session.id if session else None,
        )

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            self._go_next()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self._go_prev()
        elif key == Qt.Key.Key_R:
            self._replay_audio()
        elif key == Qt.Key.Key_F:
            self._toggle_flag()
        elif key == Qt.Key.Key_S:
            self._prompt_submit()
        elif key == Qt.Key.Key_Up and self._option_widgets:
            self._select_option(max(0, self._selected_option - 1))
        elif key == Qt.Key.Key_Down and self._option_widgets:
            self._select_option(min(len(self._option_widgets) - 1, self._selected_option + 1))
        elif Qt.Key.Key_1 <= key <= Qt.Key.Key_4 and self._option_widgets:
            i = key - Qt.Key.Key_1
            if i < len(self._option_widgets):
                self._select_option(i)
        elif Qt.Key.Key_A <= key <= Qt.Key.Key_D and self._option_widgets:
            i = key - Qt.Key.Key_A
            if i < len(self._option_widgets):
                self._select_option(i)
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _go_next(self):
        if self._engine:
            self._engine.next_question()
            self._render_current_question()

    def _go_prev(self):
        if self._engine:
            self._engine.prev_question()
            self._render_current_question()

    def _select_option(self, index: int):
        if not self._engine or not self._option_widgets:
            return
        if index < 0 or index >= len(self._option_widgets):
            return
        t = self._t
        for btn in self._option_widgets:
            btn.setStyleSheet(_opt_style(t, False))
        self._selected_option = index
        self._option_widgets[index].setStyleSheet(_opt_style(t, True))
        q = self._engine.current_question()
        if q:
            chosen = q.options[index]
            display_choice = (
                self._display_options[index]
                if index < len(self._display_options) else chosen
            )
            self._engine.answer(q.id, chosen)
            self._update_progress_grid()
            profile = self._ctx._current_profile
            lang = self._display_language
            rate = profile.speech_rate if profile else 1.0
            self._ctx.tts.speak(
                f"Option {chr(65+index)} selected. {math_to_speech(display_choice)}",
                language=lang, rate=rate,
            )
            self._ctx.audit.log(
                AuditEvent.ANSWER_SAVED, f"q={q.id};opt={chr(65+index)}",
                self._engine._session.id if self._engine._session else None,
            )

    def _toggle_flag(self):
        if not self._engine:
            return
        q = self._engine.current_question()
        if not q:
            return
        if self._engine.is_flagged(q.id):
            self._engine.unflag(q.id)
            msg = "Flag removed."
            self._flag_btn.setText("⚑  Flag for Review  (F)")
            self._ctx.audit.log(AuditEvent.FLAG_CLEARED, f"q={q.id}")
        else:
            self._engine.flag(q.id)
            msg = "Question flagged for review."
            self._flag_btn.setText("★  Flagged  (F)")
            self._ctx.audit.log(AuditEvent.FLAG_SET, f"q={q.id}")
        self._update_progress_grid()
        profile = self._ctx._current_profile
        self._ctx.tts.speak(msg, language=profile.language if profile else "en")

    def _replay_audio(self):
        if not self._engine:
            return
        q = self._engine.current_question()
        if not q:
            return
        session = self._engine._session
        idx = session.current_index if session else 0
        total = len(session.questions) if session else 1
        profile = self._ctx._current_profile
        lang = self._display_language
        rate = profile.speech_rate if profile else 1.0
        speech = (
            f"Replay. Question {idx+1} of {total}. "
            f"{math_to_speech(self._display_question_body or q.body)}"
        )
        display_options = self._display_options or q.options
        for i, opt in enumerate(display_options):
            speech += f". Option {chr(65+i)}: {math_to_speech(opt)}"
        self._ctx.tts.speak(speech, language=lang, rate=rate, interrupt=True)

    def _toggle_volume(self):
        self._ctx.tts.speak("Volume control. Use system volume keys.", language="en")

    def _toggle_contrast(self):
        self._t = LIGHT if self._t is DARK else DARK
        self._apply_theme()
        self._ctx.tts.speak(
            "Dark mode" if self._t is DARK else "Light mode", language="en"
        )

    def _cycle_text_size(self):
        self._ctx.tts.speak("Text size. Adjust in settings.", language="en")

    def _show_lock_status(self):
        profile = self._ctx._current_profile
        lang = profile.language if profile else "en"
        active = bool(self._ctx._kiosk and self._ctx._kiosk.is_active())
        msg = (
            "Kiosk lock is active. Alt+Tab and the Windows key are disabled "
            "for the rest of this exam."
            if active else
            "Kiosk lock is not active."
        )
        self._ctx.tts.speak(msg, language=lang)
        QMessageBox.information(self, "Exam Lock", msg)

    def _show_profile_info(self):
        profile = self._ctx._current_profile
        if not profile:
            return
        msg = (
            f"Candidate: {profile.full_name}\n"
            f"Language: {profile.language}\n"
            f"Modality: {profile.modality}"
        )
        self._ctx.tts.speak(f"Profile. {profile.full_name}.", language=profile.language)
        QMessageBox.information(self, "Candidate Profile", msg)

    def _switch_lang(self, lang: str):
        if self._ctx._current_profile:
            self._ctx._current_profile.language = lang
        self._render_current_question()

    def _prompt_submit(self):
        if not self._engine:
            return
        unanswered = self._engine.unanswered_count()
        profile = self._ctx._current_profile
        lang = profile.language if profile else "en"
        rate = profile.speech_rate if profile else 1.0
        msg = (
            f"You have {unanswered} unanswered question(s). "
            "Are you sure you want to submit?"
        )
        self._ctx.tts.speak(msg, language=lang, rate=rate)
        reply = QMessageBox.question(
            self, "Submit Exam", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._do_submit()

    def _do_submit(self):
        self._display_timer.stop()
        results = self._engine.submit()
        self._ctx.exit_kiosk()
        profile = self._ctx._current_profile
        lang = profile.language if profile else "en"
        rate = profile.speech_rate if profile else 1.0
        self._ctx.tts.speak(
            f"Exam submitted. You answered {results['answered']} of {results['total']} questions.",
            language=lang, rate=rate,
        )
        self._ctx.navigate("result", results=results)

    # ------------------------------------------------------------------
    # Timer
    # ------------------------------------------------------------------

    def _tick_display(self):
        if self._remaining_seconds > 0:
            self._remaining_seconds -= 1
        m, s = divmod(self._remaining_seconds, 60)
        self._timer_label.setText(f"⏱  {m:02d}:{s:02d}")

    def _on_countdown(self, seconds_remaining: int):
        mins = seconds_remaining // 60
        profile = self._ctx._current_profile
        lang = profile.language if profile else "en"
        rate = profile.speech_rate if profile else 1.0
        msg = f"Warning: {mins} minute{'s' if mins != 1 else ''} remaining."
        self._ctx.tts.speak(msg, language=lang, rate=rate)
        self.show_status_message(msg)

    def _on_time_up(self):
        self._display_timer.stop()
        profile = self._ctx._current_profile
        lang = profile.language if profile else "en"
        self._ctx.tts.speak("Time is up. Submitting now.", language=lang)
        self._do_submit()

    def show_status_message(self, message: str, duration_ms: int = 4000):
        self._status_label.setText(message)
        QTimer.singleShot(duration_ms, lambda: self._status_label.setText(""))
