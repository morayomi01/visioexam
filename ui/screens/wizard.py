"""
Accessibility Setup Wizard — matches screenshot 8.
Two-column layout: Audio & Voice (left) | Visual Adjustments (right).
Hardware & Navigation card at the bottom. Save & Continue button.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QSlider, QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer

logger = logging.getLogger(__name__)

DARK = {
    "bg": "#0D1117", "card": "#1C2128", "border": "#30363D",
    "text": "#E6EDF3", "muted": "#8B949E", "accent": "#2F81F7",
    "input_bg": "#0D1117", "warning": "#D29922",
    "btn_bg": "#2F81F7", "btn_text": "#FFFFFF",
    "hw_card_bg": "#1C2128", "hw_card_border": "#D29922",
}
LIGHT = {
    "bg": "#F6F8FA", "card": "#FFFFFF", "border": "#D0D7DE",
    "text": "#1F2328", "muted": "#656D76", "accent": "#0969DA",
    "input_bg": "#FFFFFF", "warning": "#9A6700",
    "btn_bg": "#0969DA", "btn_text": "#FFFFFF",
    "hw_card_bg": "#FFFFFF", "hw_card_border": "#9A6700",
}


class SetupWizardScreen(QWidget):
    def __init__(self, app_ctx):
        super().__init__()
        self._ctx = app_ctx
        self._t = DARK
        self._selected_contrast = "dark"
        self._build_ui()

    def _build_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll_area = QScrollArea(self)
        scroll_area.setObjectName("setupScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        page_layout.addWidget(scroll_area)

        page_content = QWidget()
        page_content.setObjectName("setupScrollContent")
        scroll_area.setWidget(page_content)

        outer = QVBoxLayout(page_content)
        outer.setContentsMargins(40, 32, 40, 32)
        outer.setSpacing(24)

        # Header
        title_lbl = QLabel("Accessibility Setup")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(
            "font-size: 36px; font-weight: 800; color: #2F81F7; letter-spacing: -0.5px;"
        )
        subtitle = QLabel(
            "Customize your experience before beginning the examination. "
            "These settings can be changed later."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 14px; color: #8B949E;")
        outer.addWidget(title_lbl)
        outer.addWidget(subtitle)

        # Two-column cards row
        cols = QHBoxLayout()
        cols.setSpacing(20)

        # ── Audio & Voice card ────────────────────────────────────────
        self._audio_card = QFrame()
        self._audio_card.setObjectName("wizardCard")
        audio_layout = QVBoxLayout(self._audio_card)
        audio_layout.setContentsMargins(28, 24, 28, 24)
        audio_layout.setSpacing(16)

        a_title_row = QHBoxLayout()
        a_icon = QLabel("🔊")
        a_icon.setStyleSheet("font-size: 20px;")
        a_title = QLabel("Audio & Voice")
        a_title.setStyleSheet("font-size: 17px; font-weight: 700;")
        a_title_row.addWidget(a_icon)
        a_title_row.addWidget(a_title)
        a_title_row.addStretch()
        audio_layout.addLayout(a_title_row)

        # Voice selection
        audio_layout.addWidget(self._field_label("Voice Selection"))
        self._voice_combo = QComboBox()
        self._voice_combo.addItems([
            "English (US) — Default",
            "Yoruba",
            "Hausa",
            "Igbo",
        ])
        self._voice_combo.setMinimumHeight(44)
        self._voice_combo.currentIndexChanged.connect(self._on_voice_changed)
        audio_layout.addWidget(self._voice_combo)

        # Speech rate
        rate_row = QHBoxLayout()
        rate_row.addWidget(self._field_label("Speech Rate"))
        rate_row.addStretch()
        self._rate_val = QLabel("1.0x")
        self._rate_val.setStyleSheet("font-size: 14px; font-weight: 700;")
        rate_row.addWidget(self._rate_val)
        audio_layout.addLayout(rate_row)

        self._rate_slider = QSlider(Qt.Orientation.Horizontal)
        self._rate_slider.setMinimum(50)
        self._rate_slider.setMaximum(200)
        self._rate_slider.setValue(100)
        self._rate_slider.setMinimumHeight(32)
        self._rate_slider.valueChanged.connect(
            lambda v: self._rate_val.setText(f"{v/100:.1f}x")
        )
        audio_layout.addWidget(self._rate_slider)

        # Test audio button
        self._test_audio_btn = QPushButton("▶  Test Audio")
        self._test_audio_btn.setMinimumHeight(44)
        self._test_audio_btn.setObjectName("testAudioBtn")
        self._test_audio_btn.clicked.connect(self._test_audio)
        audio_layout.addWidget(self._test_audio_btn)

        audio_layout.addStretch()
        cols.addWidget(self._audio_card)

        # ── Visual Adjustments card ───────────────────────────────────
        self._visual_card = QFrame()
        self._visual_card.setObjectName("wizardCard")
        visual_layout = QVBoxLayout(self._visual_card)
        visual_layout.setContentsMargins(28, 24, 28, 24)
        visual_layout.setSpacing(16)

        v_title_row = QHBoxLayout()
        v_icon = QLabel("👁")
        v_icon.setStyleSheet("font-size: 20px;")
        v_title = QLabel("Visual Adjustments")
        v_title.setStyleSheet("font-size: 17px; font-weight: 700;")
        v_title_row.addWidget(v_icon)
        v_title_row.addWidget(v_title)
        v_title_row.addStretch()
        visual_layout.addLayout(v_title_row)

        # Text size
        ts_row = QHBoxLayout()
        ts_row.addWidget(self._field_label("Text Size"))
        ts_row.addStretch()
        self._ts_val = QLabel("100%")
        self._ts_val.setStyleSheet("font-size: 14px; font-weight: 700;")
        ts_row.addWidget(self._ts_val)
        visual_layout.addLayout(ts_row)

        self._ts_slider = QSlider(Qt.Orientation.Horizontal)
        self._ts_slider.setMinimum(80)
        self._ts_slider.setMaximum(200)
        self._ts_slider.setValue(100)
        self._ts_slider.setMinimumHeight(32)
        self._ts_slider.valueChanged.connect(
            lambda v: self._ts_val.setText(f"{v}%")
        )
        visual_layout.addWidget(self._ts_slider)

        # Sample text
        self._sample = QLabel("Sample text to preview sizing...")
        self._sample.setObjectName("wizardSample")
        self._sample.setMinimumHeight(52)
        self._sample.setStyleSheet(
            "font-size: 14px; padding: 10px 14px; border-radius: 8px;"
        )
        visual_layout.addWidget(self._sample)

        # High contrast toggle
        hc_row = QHBoxLayout()
        hc_text = QVBoxLayout()
        hc_title = QLabel("High Contrast Mode")
        hc_title.setStyleSheet("font-size: 14px; font-weight: 600;")
        hc_sub = QLabel("Enhance visual distinction")
        hc_sub.setStyleSheet("font-size: 12px;")
        hc_text.addWidget(hc_title)
        hc_text.addWidget(hc_sub)
        self._hc_toggle = QPushButton("OFF")
        self._hc_toggle.setFixedSize(52, 28)
        self._hc_toggle.setObjectName("hcToggle")
        self._hc_on = False
        self._hc_toggle.clicked.connect(self._toggle_hc)
        hc_row.addLayout(hc_text)
        hc_row.addStretch()
        hc_row.addWidget(self._hc_toggle)
        visual_layout.addLayout(hc_row)
        visual_layout.addStretch()
        cols.addWidget(self._visual_card)
        outer.addLayout(cols)

        # ── Hardware & Navigation card ────────────────────────────────
        self._hw_card = QFrame()
        self._hw_card.setObjectName("hwCard")
        hw_layout = QVBoxLayout(self._hw_card)
        hw_layout.setContentsMargins(28, 20, 28, 20)
        hw_layout.setSpacing(14)

        hw_title_row = QHBoxLayout()
        hw_icon = QLabel("⌨")
        hw_icon.setStyleSheet("font-size: 20px;")
        hw_title = QLabel("Hardware & Navigation")
        hw_title.setStyleSheet("font-size: 17px; font-weight: 700;")
        hw_title_row.addWidget(hw_icon)
        hw_title_row.addWidget(hw_title)
        hw_title_row.addStretch()
        hw_layout.addLayout(hw_title_row)

        hw_cols = QHBoxLayout()
        hw_cols.setSpacing(16)

        # Braille display row
        left_hw = QVBoxLayout()
        braille_row = QFrame()
        braille_row.setObjectName("brailleRow")
        br_layout = QHBoxLayout(braille_row)
        br_layout.setContentsMargins(12, 10, 12, 10)
        br_icon = QLabel("♿")
        br_icon.setStyleSheet("font-size: 18px;")
        br_text = QVBoxLayout()
        br_title = QLabel("Braille Display")
        br_title.setStyleSheet("font-size: 13px; font-weight: 600;")
        br_status = QLabel("Not Connected")
        br_status.setObjectName("brailleStatus")
        br_status.setStyleSheet("font-size: 12px; color: #8B949E;")
        br_status.setAccessibleName("Braille display connection status")
        self._braille_status = br_status
        br_text.addWidget(br_title)
        br_text.addWidget(br_status)
        connect_btn = QPushButton("Connect")
        connect_btn.setFixedHeight(36)
        connect_btn.setObjectName("connectBtn")
        connect_btn.clicked.connect(self._try_braille_connect)
        br_layout.addWidget(br_icon)
        br_layout.addLayout(br_text)
        br_layout.addStretch()
        br_layout.addWidget(connect_btn)
        left_hw.addWidget(braille_row)

        # Keyboard tutorial card
        tutorial_card = QFrame()
        tutorial_card.setObjectName("tutorialCard")
        tc_layout = QVBoxLayout(tutorial_card)
        tc_layout.setContentsMargins(14, 12, 14, 12)
        tc_layout.setSpacing(4)
        tc_title = QLabel("Keyboard Navigation Tutorial")
        tc_title.setStyleSheet("font-size: 13px; font-weight: 700;")
        tc_sub = QLabel("Learn essential shortcuts for seamless navigation.")
        tc_sub.setStyleSheet("font-size: 12px;")
        tc_start = QLabel("Start Tutorial")
        tc_start.setStyleSheet("font-size: 12px; font-weight: 700; color: #D29922;")
        tc_layout.addWidget(tc_title)
        tc_layout.addWidget(tc_sub)
        tc_layout.addWidget(tc_start)
        left_hw.addWidget(tutorial_card)

        hw_cols.addLayout(left_hw, 1)

        # Braille hands image placeholder
        img_frame = QFrame()
        img_frame.setMinimumHeight(120)
        img_frame.setObjectName("imgFrame")
        img_lbl = QLabel("[ Braille Display Image ]")
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet("font-size: 12px; color: #8B949E;")
        img_layout = QVBoxLayout(img_frame)
        img_layout.addWidget(img_lbl)
        hw_cols.addWidget(img_frame, 1)
        hw_layout.addLayout(hw_cols)
        outer.addWidget(self._hw_card)

        # Save & Continue button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._save_btn = QPushButton("Save & Continue  →")
        self._save_btn.setMinimumHeight(52)
        self._save_btn.setMinimumWidth(220)
        self._save_btn.setObjectName("saveContinueBtn")
        self._save_btn.clicked.connect(self._finish)
        btn_row.addWidget(self._save_btn)
        outer.addLayout(btn_row)

        self._apply_theme()

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self):
        t = self._t
        self.setStyleSheet(f"""
            QWidget#setupScrollContent {{ background-color: {t['bg']}; }}
            QScrollArea#setupScrollArea {{ background-color: {t['bg']}; border: none; }}
            QScrollArea#setupScrollArea QScrollBar:vertical {{
                background: {t['bg']}; width: 14px; margin: 2px;
            }}
            QScrollArea#setupScrollArea QScrollBar::handle:vertical {{
                background: {t['border']}; min-height: 36px; border-radius: 6px;
            }}
            QScrollArea#setupScrollArea QScrollBar::add-line:vertical,
            QScrollArea#setupScrollArea QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        for card in [self._audio_card, self._visual_card]:
            card.setStyleSheet(f"""
                QFrame#wizardCard {{
                    background-color: {t['card']};
                    border: 1px solid {t['border']};
                    border-radius: 14px;
                }}
                QLabel {{ color: {t['text']}; background: transparent; }}
            """)
        self._hw_card.setStyleSheet(f"""
            QFrame#hwCard {{
                background-color: {t['hw_card_bg']};
                border: 1px solid {t['border']};
                border-radius: 14px;
            }}
            QLabel {{ color: {t['text']}; background: transparent; }}
            QFrame#brailleRow {{
                background-color: {t['input_bg']};
                border: 1px solid {t['border']};
                border-radius: 8px;
            }}
            QFrame#tutorialCard {{
                background-color: transparent;
                border-left: 3px solid {t['warning']};
                border-top: none; border-right: none; border-bottom: none;
                padding-left: 4px;
            }}
            QFrame#imgFrame {{
                background-color: {t['input_bg']};
                border: 1px solid {t['border']};
                border-radius: 8px;
            }}
        """)
        for combo in [self._voice_combo]:
            combo.setStyleSheet(f"""
                QComboBox {{
                    background-color: {t['input_bg']}; color: {t['text']};
                    border: 1px solid {t['border']}; border-radius: 8px;
                    padding: 0 12px; font-size: 14px;
                }}
                QComboBox::drop-down {{ border: none; width: 24px; }}
                QComboBox QAbstractItemView {{
                    background-color: {t['card']}; color: {t['text']};
                    border: 1px solid {t['border']};
                }}
            """)
        slider_css = f"""
            QSlider::groove:horizontal {{
                height: 4px; background: {t['border']}; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {t['accent']}; width: 18px; height: 18px;
                margin: -7px 0; border-radius: 9px;
            }}
            QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 2px; }}
        """
        self._rate_slider.setStyleSheet(slider_css)
        self._ts_slider.setStyleSheet(slider_css)
        self._test_audio_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {t['accent']};
                border: 1.5px solid {t['accent']}; border-radius: 8px;
                font-size: 14px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {t['card']}; }}
        """)
        self._sample.setStyleSheet(f"""
            font-size: 14px; color: {t['muted']};
            background-color: {t['input_bg']};
            border: 1px solid {t['border']};
            border-radius: 8px; padding: 10px 14px;
        """)
        hc_bg = t['accent'] if self._hc_on else t['border']
        hc_fg = "#FFFFFF" if self._hc_on else t['muted']
        self._hc_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {hc_bg}; color: {hc_fg};
                border: none; border-radius: 14px;
                font-size: 11px; font-weight: 700;
            }}
        """)
        connect_btn_css = f"""
            QPushButton#connectBtn {{
                background-color: {t['input_bg']}; color: {t['text']};
                border: 1px solid {t['border']}; border-radius: 6px;
                font-size: 13px; font-weight: 600; padding: 0 14px;
            }}
            QPushButton#connectBtn:hover {{ border-color: {t['accent']}; }}
        """
        self._hw_card.setStyleSheet(self._hw_card.styleSheet() + connect_btn_css)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['btn_bg']}; color: {t['btn_text']};
                border: none; border-radius: 10px;
                font-size: 15px; font-weight: 700;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        return lbl

    # ------------------------------------------------------------------
    # on_show
    # ------------------------------------------------------------------

    def on_show(self, **kwargs):
        self._apply_theme()
        self._refresh_braille_status()
        QTimer.singleShot(400, lambda: self._ctx.tts.speak(
            "Accessibility setup. Customize your examination experience. "
            "Set your voice, speech rate, text size, and contrast, then press Save and Continue.",
            language="en",
        ))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_voice_changed(self, index: int):
        lang_map = {0: "en", 1: "yo", 2: "ha", 3: "ig"}
        lang = lang_map.get(index, "en")
        self._ctx.tts.speak("Voice selected.", language=lang)

    def _test_audio(self):
        lang_map = {0: "en", 1: "yo", 2: "ha", 3: "ig"}
        lang = lang_map.get(self._voice_combo.currentIndex(), "en")
        rate = self._rate_slider.value() / 100
        self._ctx.tts.speak(
            "This is a test. The audio output is working correctly.",
            language=lang, rate=rate,
        )

    def _toggle_hc(self):
        self._hc_on = not self._hc_on
        self._hc_toggle.setText("ON" if self._hc_on else "OFF")
        if self._hc_on:
            self._t = DARK
            self._ctx.apply_theme_by_name("hcyob")
        else:
            self._ctx.apply_theme_by_name("dark")
        self._apply_theme()

    def _try_braille_connect(self):
        self._braille_status.setText("Scanning for display…")
        connected = self._ctx.braille.reconnect()
        self._refresh_braille_status()
        message = (
            "Braille display connected."
            if connected
            else self._ctx.braille.status
        )
        self._ctx.tts.speak(message, language="en")

    def _refresh_braille_status(self):
        self._braille_status.setText(self._ctx.braille.status)

    def _finish(self):
        lang_map = {0: "en", 1: "yo", 2: "ha", 3: "ig"}
        lang = lang_map.get(self._voice_combo.currentIndex(), "en")
        rate = self._rate_slider.value() / 100
        font = max(14, min(36, int(self._ts_slider.value() * 18 / 100)))
        contrast = "hcyob" if self._hc_on else "dark"

        self._ctx._wizard_preferences = {
            "language": lang, "modality": "audio",
            "speech_rate": rate, "font_size": font, "contrast": contrast,
        }
        self._ctx.apply_theme_by_name(contrast)
        self._ctx.tts.speak("Setup complete. Please log in with your candidate ID.", language=lang)
        self._ctx.navigate("login")
