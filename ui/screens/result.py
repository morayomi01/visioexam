"""
Result Screen — shown after exam submission.
Matches the 'Exam Successfully Submitted' screenshot exactly.
"""

import logging
from datetime import datetime, timezone
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

logger = logging.getLogger(__name__)

DARK = {
    "bg": "#0D1117", "card": "#161B22", "border": "#30363D",
    "text": "#E6EDF3", "muted": "#8B949E", "accent": "#00D9FF",
    "success": "#3FB950", "summary_bg": "#0D1117", "summary_border": "#30363D",
    "btn_bg": "#2F81F7", "btn_text": "#FFFFFF",
}
LIGHT = {
    "bg": "#F6F8FA", "card": "#FFFFFF", "border": "#D0D7DE",
    "text": "#1F2328", "muted": "#656D76", "accent": "#0969DA",
    "success": "#1A7F37", "summary_bg": "#F6F8FA", "summary_border": "#D0D7DE",
    "btn_bg": "#0969DA", "btn_text": "#FFFFFF",
}


class ResultScreen(QWidget):
    def __init__(self, app_ctx):
        super().__init__()
        self._ctx = app_ctx
        self._t = DARK
        self._start_time = None
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setContentsMargins(0, 0, 0, 0)

        # Top bar
        self._topbar = QFrame()
        self._topbar.setFixedHeight(52)
        self._topbar.setObjectName("resultTopBar")
        tb = QHBoxLayout(self._topbar)
        tb.setContentsMargins(24, 0, 24, 0)
        brand = QLabel("VisionExam")
        brand.setStyleSheet("font-size: 16px; font-weight: 700;")
        self._lang_lbl = QLabel("EN")
        self._lang_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; padding: 4px 12px;"
            " border-radius: 14px; background: #30363D; color: #E6EDF3;"
        )
        tb.addWidget(brand)
        tb.addStretch()
        tb.addWidget(self._lang_lbl)
        tb.addSpacing(8)
        for icon in ["🔊", "🔒"]:
            lbl = QLabel(icon)
            lbl.setStyleSheet("font-size: 18px; padding: 0 6px;")
            tb.addWidget(lbl)
        outer.addWidget(self._topbar)

        # Card
        self._card = QFrame()
        self._card.setFixedWidth(680)
        self._card.setObjectName("resultCard")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 90))
        self._card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(56, 48, 56, 48)
        card_layout.setSpacing(20)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Checkmark circle
        check_circle = QLabel("✓")
        check_circle.setFixedSize(80, 80)
        check_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        check_circle.setStyleSheet("""
            QLabel {
                background-color: #00D9FF;
                color: #0D1117;
                font-size: 36px; font-weight: 900;
                border-radius: 40px;
            }
        """)
        circle_row = QHBoxLayout()
        circle_row.addStretch()
        circle_row.addWidget(check_circle)
        circle_row.addStretch()
        card_layout.addLayout(circle_row)

        # Title
        title = QLabel("Exam Successfully\nSubmitted")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 32px; font-weight: 800; line-height: 1.3;")
        card_layout.addWidget(title)

        subtitle = QLabel("Your responses have been securely uploaded and recorded. You\nmay now safely exit the examination environment.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 14px; line-height: 1.5;")
        card_layout.addWidget(subtitle)

        # Summary box
        self._summary_box = QFrame()
        self._summary_box.setObjectName("summaryBox")
        summary_layout = QVBoxLayout(self._summary_box)
        summary_layout.setContentsMargins(24, 20, 24, 20)
        summary_layout.setSpacing(16)

        summary_title = QLabel("Submission Summary")
        summary_title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: #2F81F7;"
        )
        summary_layout.addWidget(summary_title)

        stats_row = QHBoxLayout()
        self._exam_id_col = self._make_stat_col("Exam ID", "------")
        self._time_col = self._make_stat_col("Time Taken", "--:--:--")
        self._answers_col = self._make_stat_col("Questions\nAnswered", "- / -")
        stats_row.addWidget(self._exam_id_col)
        stats_row.addWidget(self._time_col)
        stats_row.addWidget(self._answers_col)
        summary_layout.addLayout(stats_row)
        card_layout.addWidget(self._summary_box)

        # Logout button
        self._logout_btn = QPushButton("⎋  Logout & Secure Exit")
        self._logout_btn.setMinimumHeight(52)
        self._logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #2F81F7; color: white;
                font-size: 15px; font-weight: 700;
                border: none; border-radius: 10px;
            }
            QPushButton:hover { background-color: #388BFD; }
        """)
        self._logout_btn.clicked.connect(self._logout)
        card_layout.addWidget(self._logout_btn)

        outer.addWidget(self._card)
        self._apply_theme()

    def _make_stat_col(self, label: str, value: str) -> QFrame:
        col = QFrame()
        col_layout = QVBoxLayout(col)
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_layout.setSpacing(4)
        lbl = QLabel(label)
        lbl.setObjectName("statLabel")
        lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        val = QLabel(value)
        val.setObjectName("statValue")
        val.setStyleSheet("font-size: 20px; font-weight: 800;")
        col_layout.addWidget(lbl)
        col_layout.addWidget(val)
        col._value_label = val
        col._key_label = lbl
        return col

    def _apply_theme(self):
        t = self._t
        self.setStyleSheet(f"background-color: {t['bg']};")
        self._topbar.setStyleSheet(f"""
            QFrame#resultTopBar {{
                background-color: {t['card']};
                border-bottom: 1px solid {t['border']};
            }}
            QLabel {{ color: {t['text']}; background: transparent; }}
        """)
        self._card.setStyleSheet(f"""
            QFrame#resultCard {{
                background-color: {t['card']};
                border: 1px solid {t['border']};
                border-radius: 16px;
            }}
            QLabel {{ color: {t['text']}; background: transparent; }}
        """)
        self._summary_box.setStyleSheet(f"""
            QFrame#summaryBox {{
                background-color: {t['summary_bg']};
                border: 1px solid {t['summary_border']};
                border-radius: 10px;
            }}
            QLabel {{ color: {t['text']}; background: transparent; }}
        """)

    def on_show(self, results: dict = None, **kwargs):
        if not results:
            results = {"session_id": "------", "answered": 0, "total": 0, "score": 0}

        # Sync theme
        profile = self._ctx._current_profile
        if profile:
            self._t = DARK if profile.contrast in ("dark", "hcyob") else LIGHT
            self._apply_theme()
            lang = profile.language
            rate = profile.speech_rate
        else:
            lang, rate = "en", 1.0

        # Update summary
        sid = results.get("session_id", "------")[:12].upper()
        answered = results.get("answered", 0)
        total = results.get("total", 0)

        # Calculate time taken
        elapsed = "N/A"
        if hasattr(self._ctx, "_exam_start_time") and self._ctx._exam_start_time:
            delta = datetime.now(timezone.utc) - self._ctx._exam_start_time
            h, rem = divmod(int(delta.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            elapsed = f"{h:02d}:{m:02d}:{s:02d}"

        self._exam_id_col._value_label.setText(sid)
        self._time_col._value_label.setText(elapsed)
        self._answers_col._value_label.setText(f"{answered} / {total}")

        msg = (
            f"Exam successfully submitted. "
            f"You answered {answered} of {total} questions. "
            "Your responses have been securely recorded. "
            "Press the logout button to exit."
        )
        QTimer.singleShot(600, lambda: self._ctx.tts.speak(msg, language=lang, rate=rate))

    def _logout(self):
        self._ctx.tts.speak("Logging out. Goodbye.", language="en")
        QTimer.singleShot(1200, lambda: self._ctx.navigate("login"))