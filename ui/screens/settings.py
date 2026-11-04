"""
Settings Screen — matches the VisionExam Accessibility Settings screenshot.
Two-column layout: Audio & Speech (left) | Visual Display (right).
Reset Defaults + Save to Candidate Profile buttons at the bottom.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QSlider, QCheckBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from core.profile_manager import SUPPORTED_LANGUAGES, MODALITIES, CONTRAST_THEMES

logger = logging.getLogger(__name__)

DARK = {
    "bg": "#0D1117", "sidebar": "#161B22", "card": "#1C2128",
    "border": "#30363D", "text": "#E6EDF3", "muted": "#8B949E",
    "accent": "#2F81F7", "success": "#3FB950",
    "input_bg": "#0D1117", "check_bg": "#2F81F7",
    "sample_bg": "#0D1117",
}
LIGHT = {
    "bg": "#F6F8FA", "sidebar": "#FFFFFF", "card": "#FFFFFF",
    "border": "#D0D7DE", "text": "#1F2328", "muted": "#656D76",
    "accent": "#0969DA", "success": "#1A7F37",
    "input_bg": "#FFFFFF", "check_bg": "#0969DA",
    "sample_bg": "#F6F8FA",
}

CONTRAST_DISPLAY = {
    "light": ("Light Mode", "#FFFFFF", "#1F2328"),
    "dark":  ("Soft Dark\n(Current)", "#1C2128", "#E6EDF3"),
    "hcyob": ("High Contrast\n(B/Y)", "#000000", "#FFFF00"),
}


class SettingsScreen(QWidget):
    def __init__(self, app_ctx):
        super().__init__()
        self._ctx = app_ctx
        self._t = DARK
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left sidebar ──────────────────────────────────────────────
        self._sidebar = QFrame()
        self._sidebar.setFixedWidth(220)
        self._sidebar.setObjectName("settingsSidebar")
        sb = QVBoxLayout(self._sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)

        # Brand
        brand_bar = QFrame()
        brand_bar.setFixedHeight(56)
        bb = QHBoxLayout(brand_bar)
        bb.setContentsMargins(16, 0, 16, 0)
        brand = QLabel("VisionExam")
        brand.setStyleSheet("font-size: 16px; font-weight: 700;")
        bb.addWidget(brand)
        sb.addWidget(brand_bar)

        # Profile
        profile_card = QFrame()
        profile_card.setObjectName("settingsProfileCard")
        pc = QVBoxLayout(profile_card)
        pc.setContentsMargins(16, 16, 16, 16)
        pc.setSpacing(4)
        avatar = QLabel("👤")
        avatar.setStyleSheet("font-size: 28px;")
        self._id_lbl = QLabel("ID: ------")
        self._id_lbl.setStyleSheet("font-size: 15px; font-weight: 700;")
        session_lbl = QLabel("Secure Session")
        session_lbl.setStyleSheet("font-size: 12px;")
        pc.addWidget(avatar)
        pc.addWidget(self._id_lbl)
        pc.addWidget(session_lbl)
        sb.addWidget(profile_card)

        # Nav
        for text, active, target in [
            ("⊞  Dashboard", False, "login"),
            ("⚙  Settings", True, "settings"),
        ]:
            btn = QPushButton(text)
            btn.setMinimumHeight(42)
            btn.setFlat(True)
            btn.setObjectName("navActive" if active else "navBtn")
            t2 = target
            btn.clicked.connect(lambda _, t=t2: self._ctx.navigate(t))
            sb.addWidget(btn)

        sb.addSpacing(8)
        tools_lbl = QLabel("  ACCESS TOOLS")
        tools_lbl.setStyleSheet("font-size: 11px; font-weight: 700; padding: 8px 16px 4px;")
        sb.addWidget(tools_lbl)

        quick_actions = [
            ("🔊  Volume", self._focus_speed_slider),
            ("◑  Contrast", self._focus_contrast_section),
            ("𝗔  Text Size", self._focus_font_slider),
        ]
        for text, handler in quick_actions:
            btn = QPushButton(text)
            btn.setMinimumHeight(40)
            btn.setFlat(True)
            btn.setObjectName("navBtn")
            btn.clicked.connect(handler)
            sb.addWidget(btn)

        sb.addStretch()
        root.addWidget(self._sidebar)

        # ── Main content ──────────────────────────────────────────────
        main_frame = QFrame()
        main_frame.setObjectName("settingsMain")
        main_layout = QVBoxLayout(main_frame)
        main_layout.setContentsMargins(40, 36, 40, 36)
        main_layout.setSpacing(24)

        # Header
        header_lbl = QLabel("Accessibility Settings")
        header_lbl.setStyleSheet("font-size: 28px; font-weight: 800;")
        sub_lbl = QLabel("Configure your examination experience for maximum legibility and comfort.")
        sub_lbl.setStyleSheet("font-size: 14px;")
        main_layout.addWidget(header_lbl)
        main_layout.addWidget(sub_lbl)

        # Two-column cards
        cols = QHBoxLayout()
        cols.setSpacing(20)

        # ── Audio & Speech card ───────────────────────────────────────
        self._audio_card = QFrame()
        self._audio_card.setObjectName("settingsCard")
        audio_layout = QVBoxLayout(self._audio_card)
        audio_layout.setContentsMargins(24, 24, 24, 24)
        audio_layout.setSpacing(18)

        audio_title_row = QHBoxLayout()
        audio_icon = QLabel("🔉")
        audio_icon.setStyleSheet("font-size: 22px;")
        audio_title = QLabel("Audio & Speech")
        audio_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        audio_title_row.addWidget(audio_icon)
        audio_title_row.addWidget(audio_title)
        audio_title_row.addStretch()
        audio_layout.addLayout(audio_title_row)

        # Output device
        audio_layout.addWidget(self._section_label("Output Device"))
        self._device_combo = QComboBox()
        self._device_combo.addItems([
            "System Default (Headphones)",
            "System Default (Speakers)",
            "Built-in Speakers",
        ])
        self._device_combo.setMinimumHeight(44)
        audio_layout.addWidget(self._device_combo)

        # Speech speed
        speed_row = QHBoxLayout()
        speed_lbl = self._section_label("Speech Speed")
        self._speed_val_lbl = QLabel("1.0x")
        self._speed_val_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
        speed_row.addWidget(speed_lbl)
        speed_row.addStretch()
        speed_row.addWidget(self._speed_val_lbl)
        audio_layout.addLayout(speed_row)

        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setMinimum(50)
        self._speed_slider.setMaximum(200)
        self._speed_slider.setValue(100)
        self._speed_slider.setMinimumHeight(32)
        self._speed_slider.valueChanged.connect(
            lambda v: self._speed_val_lbl.setText(f"{v/100:.2f}x")
        )
        audio_layout.addWidget(self._speed_slider)

        # Braille output checkbox
        self._braille_check_frame = QFrame()
        self._braille_check_frame.setObjectName("brailleCheckFrame")
        bc_layout = QHBoxLayout(self._braille_check_frame)
        bc_layout.setContentsMargins(16, 14, 16, 14)
        bc_text_col = QVBoxLayout()
        bc_title = QLabel("Braille Output")
        bc_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        bc_sub = QLabel("Send output to connected\nrefreshable Braille display.")
        bc_sub.setStyleSheet("font-size: 12px;")
        bc_text_col.addWidget(bc_title)
        bc_text_col.addWidget(bc_sub)
        self._braille_check = QPushButton("✓")
        self._braille_check.setFixedSize(28, 28)
        self._braille_check.setObjectName("brailleCheckBtn")
        self._braille_checked = True
        self._braille_check.clicked.connect(self._toggle_braille)
        bc_layout.addLayout(bc_text_col)
        bc_layout.addStretch()
        bc_layout.addWidget(self._braille_check)
        audio_layout.addWidget(self._braille_check_frame)

        audio_layout.addStretch()
        cols.addWidget(self._audio_card)

        # ── Visual Display card ───────────────────────────────────────
        self._visual_card = QFrame()
        self._visual_card.setObjectName("settingsCard")
        visual_layout = QVBoxLayout(self._visual_card)
        visual_layout.setContentsMargins(24, 24, 24, 24)
        visual_layout.setSpacing(18)

        visual_title_row = QHBoxLayout()
        visual_icon = QLabel("👁")
        visual_icon.setStyleSheet("font-size: 22px;")
        visual_title = QLabel("Visual Display")
        visual_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        visual_title_row.addWidget(visual_icon)
        visual_title_row.addWidget(visual_title)
        visual_title_row.addStretch()
        visual_layout.addLayout(visual_title_row)

        # Contrast mode tiles
        visual_layout.addWidget(self._section_label("Color Contrast Mode"))
        contrast_row = QHBoxLayout()
        contrast_row.setSpacing(10)
        self._contrast_tiles = {}
        for key, (label, tile_bg, tile_fg) in CONTRAST_DISPLAY.items():
            tile = QPushButton(label)
            tile.setMinimumHeight(72)
            tile.setObjectName(f"contrastTile_{key}")
            tile.setStyleSheet(f"""
                QPushButton {{
                    background-color: {tile_bg};
                    color: {tile_fg};
                    border: 2px solid #30363D;
                    border-radius: 8px;
                    font-size: 12px; font-weight: 600;
                    padding: 6px;
                }}
            """)
            tile_key = key
            tile.clicked.connect(lambda _, k=tile_key: self._select_contrast(k))
            contrast_row.addWidget(tile)
            self._contrast_tiles[key] = tile
        visual_layout.addLayout(contrast_row)

        # Global text scale
        scale_row = QHBoxLayout()
        scale_lbl = self._section_label("Global Text Scale")
        self._scale_val_lbl = QLabel("Large")
        self._scale_val_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
        scale_row.addWidget(scale_lbl)
        scale_row.addStretch()
        scale_row.addWidget(self._scale_val_lbl)
        visual_layout.addLayout(scale_row)

        font_row = QHBoxLayout()
        font_row.setContentsMargins(0, 0, 0, 0)
        small_a = QLabel("A")
        small_a.setStyleSheet("font-size: 13px;")
        self._font_slider = QSlider(Qt.Orientation.Horizontal)
        self._font_slider.setMinimum(14)
        self._font_slider.setMaximum(36)
        self._font_slider.setValue(20)
        self._font_slider.setMinimumHeight(32)
        self._font_slider.valueChanged.connect(self._on_font_change)
        big_a = QLabel("A")
        big_a.setStyleSheet("font-size: 22px; font-weight: 700;")
        font_row.addWidget(small_a)
        font_row.addWidget(self._font_slider)
        font_row.addWidget(big_a)
        visual_layout.addLayout(font_row)

        # Sample text preview
        self._sample_text = QLabel("Sample text: The quick brown fox\njumps over the lazy dog.")
        self._sample_text.setObjectName("sampleText")
        self._sample_text.setWordWrap(True)
        self._sample_text.setStyleSheet("font-size: 15px; padding: 12px; border-radius: 8px;")
        visual_layout.addWidget(self._sample_text)

        visual_layout.addStretch()
        cols.addWidget(self._visual_card)

        main_layout.addLayout(cols)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        self._reset_btn = QPushButton("Reset Defaults")
        self._reset_btn.setMinimumHeight(48)
        self._reset_btn.setMinimumWidth(160)
        self._reset_btn.setObjectName("resetBtn")
        self._reset_btn.clicked.connect(self._reset_defaults)

        self._save_btn = QPushButton("💾  Save to Candidate Profile")
        self._save_btn.setMinimumHeight(48)
        self._save_btn.setMinimumWidth(240)
        self._save_btn.setObjectName("saveBtn")
        self._save_btn.clicked.connect(self._save_settings)

        bottom_row.addWidget(self._reset_btn)
        bottom_row.addSpacing(12)
        bottom_row.addWidget(self._save_btn)
        main_layout.addLayout(bottom_row)

        root.addWidget(main_frame)
        self._apply_theme()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        return lbl

    def _apply_theme(self):
        t = self._t
        self.setStyleSheet(f"background-color: {t['bg']};")
        self._sidebar.setStyleSheet(f"""
            QFrame#settingsSidebar {{
                background-color: {t['sidebar']};
                border-right: 1px solid {t['border']};
            }}
            QLabel {{ color: {t['text']}; background: transparent; }}
            QPushButton#navActive {{
                background-color: {t['card']};
                color: {t['accent']};
                border-left: 3px solid {t['accent']};
                border-top: none; border-right: none; border-bottom: none;
                text-align: left; padding: 10px 16px; font-size: 14px; font-weight: 600;
            }}
            QPushButton#navBtn {{
                background-color: transparent; color: {t['muted']};
                border: none; text-align: left; padding: 10px 16px; font-size: 14px;
            }}
            QPushButton#navBtn:hover {{ color: {t['text']}; background: {t['card']}; }}
        """)
        for card in [self._audio_card, self._visual_card]:
            card.setStyleSheet(f"""
                QFrame#settingsCard {{
                    background-color: {t['card']};
                    border: 1px solid {t['border']};
                    border-radius: 12px;
                }}
                QLabel {{ color: {t['text']}; background: transparent; }}
            """)
        self._device_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {t['input_bg']}; color: {t['text']};
                border: 1px solid {t['border']}; border-radius: 8px;
                padding: 0 12px; font-size: 14px;
            }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
        """)
        self._speed_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px; background: {t['border']}; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {t['accent']}; width: 18px; height: 18px;
                margin: -7px 0; border-radius: 9px;
            }}
            QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 2px; }}
        """)
        self._font_slider.setStyleSheet(self._speed_slider.styleSheet())
        self._braille_check_frame.setStyleSheet(f"""
            QFrame#brailleCheckFrame {{
                background-color: {t['input_bg']};
                border: 1px solid {t['border']};
                border-radius: 8px;
            }}
            QLabel {{ color: {t['text']}; background: transparent; }}
        """)
        checked_bg = t['check_bg'] if self._braille_checked else t['border']
        self._braille_check.setStyleSheet(f"""
            QPushButton {{
                background-color: {checked_bg}; color: white;
                border: none; border-radius: 14px;
                font-size: 14px; font-weight: 700;
            }}
        """)
        self._sample_text.setStyleSheet(
            f"font-size: {self._font_slider.value()}px; "
            f"color: {t['text']}; background-color: {t['sample_bg']};"
            " padding: 12px; border-radius: 8px;"
        )
        self._reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {t['text']};
                border: 1px solid {t['border']}; border-radius: 8px;
                font-size: 14px; font-weight: 600;
            }}
            QPushButton:hover {{ border-color: {t['accent']}; }}
        """)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['accent']}; color: white;
                border: none; border-radius: 8px;
                font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        # Highlight active contrast tile
        profile = self._ctx._current_profile
        current_contrast = profile.contrast if profile else "dark"
        for key, tile in self._contrast_tiles.items():
            tile_bg, tile_fg = CONTRAST_DISPLAY[key][1], CONTRAST_DISPLAY[key][2]
            border = t['accent'] if key == current_contrast else t['border']
            tile.setStyleSheet(f"""
                QPushButton {{
                    background-color: {tile_bg}; color: {tile_fg};
                    border: 2.5px solid {border}; border-radius: 8px;
                    font-size: 12px; font-weight: 600; padding: 6px;
                }}
                QPushButton:hover {{ border-color: {t['accent']}; }}
            """)

    # ------------------------------------------------------------------
    # on_show
    # ------------------------------------------------------------------

    def on_show(self, **kwargs):
        profile = self._ctx._current_profile
        if profile:
            self._t = DARK if profile.contrast in ("dark", "hcyob") else LIGHT
            self._id_lbl.setText(f"ID: {profile.id}")
            self._speed_slider.setValue(int(profile.speech_rate * 100))
            self._font_slider.setValue(profile.font_size)
        self._apply_theme()
        QTimer.singleShot(400, lambda: self._ctx.tts.speak(
            "Accessibility settings. Adjust audio, speech rate, contrast, and text size.",
            language=profile.language if profile else "en",
        ))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _focus_speed_slider(self):
        self._speed_slider.setFocus()
        profile = self._ctx._current_profile
        self._ctx.tts.speak(
            "Speech rate slider. Use left and right arrow keys to adjust.",
            language=profile.language if profile else "en",
        )

    def _focus_font_slider(self):
        self._font_slider.setFocus()
        profile = self._ctx._current_profile
        self._ctx.tts.speak(
            "Text size slider. Use left and right arrow keys to adjust.",
            language=profile.language if profile else "en",
        )

    def _focus_contrast_section(self):
        profile = self._ctx._current_profile
        current = profile.contrast if profile else "dark"
        tile = self._contrast_tiles.get(current) or next(iter(self._contrast_tiles.values()), None)
        if tile:
            tile.setFocus()
        self._ctx.tts.speak(
            "Color contrast mode options. Use Tab to move between them.",
            language=profile.language if profile else "en",
        )

    def _toggle_braille(self):
        self._braille_checked = not self._braille_checked
        self._braille_check.setText("✓" if self._braille_checked else "")
        self._apply_theme()

    def _select_contrast(self, key: str):
        profile = self._ctx._current_profile
        if profile:
            profile.contrast = key
        self._t = DARK if key in ("dark", "hcyob") else LIGHT
        self._ctx.apply_theme_by_name(key)
        self._apply_theme()
        self._ctx.tts.speak(
            CONTRAST_DISPLAY[key][0].replace("\n", " "),
            language=profile.language if profile else "en",
        )

    def _on_font_change(self, value: int):
        sizes = {14: "Small", 16: "Normal", 20: "Large", 28: "X-Large", 36: "XX-Large"}
        closest = min(sizes.keys(), key=lambda k: abs(k - value))
        self._scale_val_lbl.setText(sizes.get(closest, f"{value}pt"))
        self._sample_text.setStyleSheet(
            f"font-size: {value}px; color: {self._t['text']}; "
            f"background-color: {self._t['sample_bg']}; padding: 12px; border-radius: 8px;"
        )

    def _reset_defaults(self):
        self._speed_slider.setValue(100)
        self._font_slider.setValue(18)
        self._braille_checked = True
        self._apply_theme()
        self._ctx.tts.speak("Settings reset to defaults.", language="en")

    def _save_settings(self):
        profile = self._ctx._current_profile
        if not profile:
            return
        profile.speech_rate = self._speed_slider.value() / 100
        profile.font_size = self._font_slider.value()
        self._ctx.profile_manager.update(profile)
        self._ctx.tts.speak("Settings saved to your candidate profile.", language=profile.language)
        logger.info(f"Settings saved for {profile.id}.")
        QTimer.singleShot(1000, lambda: self._ctx.navigate("login"))