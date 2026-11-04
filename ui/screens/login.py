"""
Candidate Login Screen — matches the VisionExam dark UI design.
Features: Candidate ID input, Voice-Assisted Login button,
language toggles (EN/YO/HA/IG), Text Size and Contrast quick buttons.
Supports both dark and light mode.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QGraphicsDropShadowEffect, QMenu,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont, QKeySequence

logger = logging.getLogger(__name__)

LANGUAGE_LABELS = {
    "en": "English",
    "yo": "Yoruba",
    "ha": "Hausa",
    "ig": "Igbo",
}
LANGUAGE_CONFIRMATIONS = {
    "en": "English selected.",
    "yo": "Ẹ káàbọ̀. A ti yan èdè Yorùbá.",
    "ha": "Sannu. An zaɓi harshen Hausa.",
    "ig": "Ndewo. A họpụtara asụsụ Igbo.",
}

DARK = {
    "bg": "#0D1117",
    "card": "#161B22",
    "border": "#30363D",
    "text": "#E6EDF3",
    "muted": "#8B949E",
    "accent": "#2F81F7",
    "accent_hover": "#388BFD",
    "secondary_btn": "#21262D",
    "secondary_border": "#30363D",
    "input_bg": "#0D1117",
    "secure_bg": "#1C2128",
    "secure_border": "#2EA043",
    "secure_text": "#3FB950",
}

LIGHT = {
    "bg": "#F6F8FA",
    "card": "#FFFFFF",
    "border": "#D0D7DE",
    "text": "#1F2328",
    "muted": "#656D76",
    "accent": "#0969DA",
    "accent_hover": "#0860CA",
    "secondary_btn": "#F6F8FA",
    "secondary_border": "#D0D7DE",
    "input_bg": "#FFFFFF",
    "secure_bg": "#DAFBE1",
    "secure_border": "#2DA44E",
    "secure_text": "#1A7F37",
}


class CandidateLoginScreen(QWidget):
    def __init__(self, app_ctx):
        super().__init__()
        self._ctx = app_ctx
        self._theme = DARK
        self._selected_language = "en"
        self._language_override = None
        self._build_ui()

    def _build_ui(self):
        self._outer = QVBoxLayout(self)
        self._outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._outer.setContentsMargins(0, 0, 0, 0)

        # Card
        self._card = QFrame()
        self._card.setFixedWidth(620)
        self._card.setObjectName("loginCard")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self._card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(48, 40, 48, 40)
        card_layout.setSpacing(24)

        # Header row: VisionExam title + Secure Session badge
        header = QHBoxLayout()
        title = QLabel("VisionExam")
        title.setStyleSheet("font-size: 28px; font-weight: 700; letter-spacing: -0.5px;")
        self._secure_badge = QLabel("🔒  Secure Session")
        self._secure_badge.setObjectName("secureBadge")
        self._secure_badge.setStyleSheet("""
            QLabel {
                font-size: 13px; font-weight: 600;
                padding: 6px 14px; border-radius: 20px;
            }
        """)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._secure_badge)
        card_layout.addLayout(header)

        # Candidate ID label + input
        id_label = QLabel("Candidate ID")
        id_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        card_layout.addWidget(id_label)

        self._id_input = QLineEdit()
        self._id_input.setPlaceholderText("🪪   Enter ID...")
        self._id_input.setMinimumHeight(52)
        self._id_input.setObjectName("idInput")
        self._id_input.setStyleSheet("""
            QLineEdit {
                font-size: 16px; border-radius: 8px;
                padding: 0 16px; border: 1.5px solid;
            }
        """)
        self._id_input.returnPressed.connect(self._attempt_login)
        card_layout.addWidget(self._id_input)

        # Error label
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("font-size: 13px; color: #F85149;")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._error_label)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._enter_btn = QPushButton("Enter System  →")
        self._enter_btn.setMinimumHeight(52)
        self._enter_btn.setObjectName("enterBtn")
        self._enter_btn.setStyleSheet("""
            QPushButton {
                font-size: 15px; font-weight: 700;
                border-radius: 8px; border: none;
            }
        """)
        self._enter_btn.clicked.connect(self._attempt_login)

        self._voice_btn = QPushButton("▶▌  Voice-Assisted Login")
        self._voice_btn.setMinimumHeight(52)
        self._voice_btn.setObjectName("voiceBtn")
        self._voice_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px; font-weight: 600;
                border-radius: 8px; border: 1.5px solid;
            }
        """)
        self._voice_btn.clicked.connect(self._voice_login)

        btn_row.addWidget(self._enter_btn, 2)
        btn_row.addWidget(self._voice_btn, 2)
        card_layout.addLayout(btn_row)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setObjectName("divider")
        card_layout.addWidget(divider)

        # Quick access buttons: EN, YO, Text Size, Contrast
        quick_row = QHBoxLayout()
        quick_row.setSpacing(10)

        self._lang_btns = {}
        for code, name in [("EN", "English"), ("YO", "Yoruba")]:
            btn = QPushButton()
            btn.setObjectName(f"lang_{code}")
            btn.setText(f"{code}\n{name}")
            btn.setMinimumHeight(70)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 13px; font-weight: 600;
                    border-radius: 8px; border: 1.5px solid;
                    padding: 8px;
                }
            """)
            lang_capture = code.lower()
            btn.clicked.connect(lambda _, l=lang_capture: self._set_language(l))
            quick_row.addWidget(btn)
            self._lang_btns[code] = btn

        self._other_language_btn = QPushButton("Other\nlanguage ▾")
        self._other_language_btn.setMinimumHeight(70)
        self._other_language_btn.setObjectName("otherLanguageBtn")
        self._other_language_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px; font-weight: 600;
                border-radius: 8px; border: 1.5px solid; padding: 8px;
            }
        """)
        self._other_language_btn.setAccessibleName("Other language: Hausa or Igbo")
        self._other_language_menu = QMenu(self)
        for lang, label in (("ha", "Hausa"), ("ig", "Igbo")):
            action = self._other_language_menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, selected=lang: self._set_language(selected)
            )
        self._other_language_btn.clicked.connect(self._show_other_languages)
        quick_row.addWidget(self._other_language_btn)

        self._text_size_btn = QPushButton("𝗧𝗧\nText Size")
        self._text_size_btn.setMinimumHeight(70)
        self._text_size_btn.setObjectName("quickBtn")
        self._text_size_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px; font-weight: 600;
                border-radius: 8px; border: 1.5px solid; padding: 8px;
            }
        """)
        self._text_size_btn.clicked.connect(self._cycle_text_size)
        quick_row.addWidget(self._text_size_btn)

        self._contrast_btn = QPushButton("◑\nContrast")
        self._contrast_btn.setMinimumHeight(70)
        self._contrast_btn.setObjectName("quickBtn")
        self._contrast_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px; font-weight: 600;
                border-radius: 8px; border: 1.5px solid; padding: 8px;
            }
        """)
        self._contrast_btn.clicked.connect(self._toggle_dark_mode)
        quick_row.addWidget(self._contrast_btn)

        card_layout.addLayout(quick_row)

        self._outer.addWidget(self._card)
        self._apply_colors()

    def _apply_colors(self):
        t = self._theme
        self.setStyleSheet(f"background-color: {t['bg']};")
        self._card.setStyleSheet(f"""
            QFrame#loginCard {{
                background-color: {t['card']};
                border: 1px solid {t['border']};
                border-radius: 16px;
            }}
            QLabel {{ color: {t['text']}; background: transparent; }}
        """)
        self._secure_badge.setStyleSheet(f"""
            QLabel {{
                color: {t['secure_text']};
                background-color: {t['secure_bg']};
                border: 1px solid {t['secure_border']};
                font-size: 13px; font-weight: 600;
                padding: 6px 14px; border-radius: 20px;
            }}
        """)
        self._id_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t['input_bg']};
                color: {t['text']};
                border: 1.5px solid {t['border']};
                font-size: 16px; border-radius: 8px; padding: 0 16px;
            }}
            QLineEdit:focus {{ border-color: {t['accent']}; }}
        """)
        self._enter_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['accent']};
                color: white;
                font-size: 15px; font-weight: 700;
                border-radius: 8px; border: none;
            }}
            QPushButton:hover {{ background-color: {t['accent_hover']}; }}
        """)
        self._voice_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['secondary_btn']};
                color: {t['text']};
                border: 1.5px solid {t['secondary_border']};
                font-size: 14px; font-weight: 600; border-radius: 8px;
            }}
            QPushButton:hover {{ border-color: {t['accent']}; }}
        """)
        for btn in self._lang_btns.values():
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t['secondary_btn']};
                    color: {t['text']};
                    border: 1.5px solid {t['secondary_border']};
                    font-size: 13px; font-weight: 600;
                    border-radius: 8px; padding: 8px;
                }}
                QPushButton:hover {{ border-color: {t['accent']}; }}
            """)
        for btn in [self._other_language_btn, self._text_size_btn, self._contrast_btn]:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t['secondary_btn']};
                    color: {t['text']};
                    border: 1.5px solid {t['secondary_border']};
                    font-size: 13px; font-weight: 600;
                    border-radius: 8px; padding: 8px;
                }}
                QPushButton:hover {{ border-color: {t['accent']}; }}
            """)
        # find divider child and style it
        for i in range(self._card.layout().count()):
            item = self._card.layout().itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QFrame):
                item.widget().setStyleSheet(f"background-color: {t['border']};")
        self._update_language_buttons()

    # ------------------------------------------------------------------
    # on_show
    # ------------------------------------------------------------------

    def on_show(self, **kwargs):
        self._id_input.setFocus()
        self._id_input.clear()
        self._error_label.setText("")
        # Start the login screen in English each time so one candidate's
        # language choice does not carry over to the next candidate.
        self._selected_language = "en"
        self._language_override = None
        self._update_language_buttons()
        QTimer.singleShot(500, lambda: self._ctx.tts.speak(
            "VisionExam. Candidate login. Please enter your candidate ID and press Enter.",
            language=self._selected_language,
        ))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _attempt_login(self):
        candidate_id = self._id_input.text().strip()
        if not candidate_id:
            self._set_error("Please enter your candidate ID.")
            return
        profile = self._ctx.profile_manager.get(candidate_id)
        if profile is None:
            self._set_error(f"ID '{candidate_id}' not found. Contact your administrator.")
            return
        if self._language_override:
            # Apply the login-page choice to this session before the exam
            # screen and its TTS/Braille routing are initialized.
            profile.language = self._language_override
        self._ctx.apply_theme_by_name(profile.contrast)
        self._ctx._current_profile = profile
        self._ctx.tts.speak(
            f"Welcome, {profile.full_name}. Loading your exam.",
            language=profile.language, rate=profile.speech_rate,
        )
        logger.info(f"Candidate {candidate_id} logged in.")
        self._ctx.navigate("exam", candidate_id=candidate_id)

    def _voice_login(self):
        self._ctx.tts.speak(
            "Voice login. Please say your candidate ID clearly after the tone.",
            language=self._selected_language,
        )
        self._set_error("Voice login: speak your ID (feature preview)")

    def _set_error(self, message: str):
        self._error_label.setText(message)
        self._ctx.tts.speak(message, language=self._selected_language)

    def _set_language(self, lang: str):
        if lang not in LANGUAGE_LABELS:
            return
        self._selected_language = lang
        self._language_override = lang
        self._update_language_buttons()
        if lang == "ig" and not self._ctx.tts.is_language_available("ig"):
            # Igbo model initialization and CPU synthesis are much slower than
            # the other voices. Give immediate feedback while its sample queues.
            self._ctx.tts.speak(
                "The Igbo voice is starting. Preparing each spoken response can take about a minute on this computer.",
                language="en",
            )
            self._ctx.tts.speak(
                LANGUAGE_CONFIRMATIONS[lang], language=lang, interrupt=False
            )
        else:
            self._ctx.tts.speak(LANGUAGE_CONFIRMATIONS[lang], language=lang)

    def _show_other_languages(self):
        self._other_language_menu.popup(
            self._other_language_btn.mapToGlobal(
                self._other_language_btn.rect().bottomLeft()
            )
        )

    def _update_language_buttons(self):
        selected_code = self._selected_language.upper()
        for code, button in self._lang_btns.items():
            is_selected = code == selected_code
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self._theme['accent'] if is_selected else self._theme['secondary_btn']};
                    color: {'white' if is_selected else self._theme['text']};
                    border: 1.5px solid {self._theme['accent'] if is_selected else self._theme['secondary_border']};
                    font-size: 13px; font-weight: 600;
                    border-radius: 8px; padding: 8px;
                }}
            """)
        other_selected = self._selected_language in ("ha", "ig")
        self._other_language_btn.setText(
            f"{LANGUAGE_LABELS[self._selected_language]}\nOther language ▾"
            if other_selected else "Other\nlanguage ▾"
        )
        self._other_language_btn.setAccessibleName(
            f"Other language choices; selected {LANGUAGE_LABELS[self._selected_language]}"
        )

    def _cycle_text_size(self):
        self._ctx.tts.speak("Text size options available in settings.", language=self._selected_language)
        self._ctx.navigate("settings")

    def _toggle_dark_mode(self):
        if self._theme is DARK:
            self._theme = LIGHT
            self._ctx.apply_theme_by_name("light")
        else:
            self._theme = DARK
            self._ctx.apply_theme_by_name("dark")
        self._apply_colors()
        self._ctx.tts.speak(
            "Dark mode" if self._theme is DARK else "Light mode",
            language=self._selected_language,
        )
