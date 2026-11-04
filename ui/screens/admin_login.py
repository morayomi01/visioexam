"""
Administrator sign-in screen.
"""

import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class AdminLoginScreen(QWidget):
    def __init__(self, app_ctx):
        super().__init__()
        self._ctx = app_ctx
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)
        layout.addStretch()

        card = QFrame()
        card.setObjectName("adminLoginCard")
        card.setMaximumWidth(520)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(38, 34, 38, 34)
        card_layout.setSpacing(14)

        badge = QLabel("VISIOEXAM  /  ADMIN")
        badge.setObjectName("adminLoginBadge")
        title = QLabel("Welcome back")
        title.setObjectName("adminLoginTitle")
        subtitle = QLabel("Sign in to manage examinations and candidates.")
        subtitle.setObjectName("adminLoginSubtitle")
        subtitle.setWordWrap(True)
        card_layout.addWidget(badge)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(10)

        user_label = QLabel("Administrator username")
        user_label.setObjectName("adminFieldLabel")
        card_layout.addWidget(user_label)
        self._user_input = QLineEdit()
        self._user_input.setMinimumHeight(48)
        self._user_input.setPlaceholderText("Enter your username")
        card_layout.addWidget(self._user_input)

        password_label = QLabel("Password")
        password_label.setObjectName("adminFieldLabel")
        card_layout.addWidget(password_label)
        self._pass_input = QLineEdit()
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_input.setMinimumHeight(48)
        self._pass_input.setPlaceholderText("Enter your password")
        self._pass_input.returnPressed.connect(self._attempt_login)
        card_layout.addWidget(self._pass_input)

        self._error_label = QLabel("")
        self._error_label.setObjectName("adminLoginError")
        self._error_label.setWordWrap(True)
        card_layout.addWidget(self._error_label)

        login_btn = QPushButton("Sign in")
        login_btn.setObjectName("adminLoginPrimary")
        login_btn.setMinimumHeight(50)
        login_btn.clicked.connect(self._attempt_login)
        back_btn = QPushButton("Back to Candidate Login")
        back_btn.setObjectName("adminLoginSecondary")
        back_btn.setMinimumHeight(44)
        back_btn.clicked.connect(lambda: self._ctx.navigate("login"))
        card_layout.addWidget(login_btn)
        card_layout.addWidget(back_btn)

        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

        self.setStyleSheet("""
            QWidget { background: #0D1117; color: #E6EDF3; font-family: Arial; }
            QFrame#adminLoginCard { background: #161B22; border: 1px solid #30363D; border-radius: 16px; }
            QLabel#adminLoginBadge { color: #58A6FF; font-size: 12px; font-weight: 700; }
            QLabel#adminLoginTitle { color: #F0F6FC; font-size: 30px; font-weight: 800; }
            QLabel#adminLoginSubtitle { color: #A6B0BC; font-size: 14px; }
            QLabel#adminFieldLabel { color: #D5DDE5; font-size: 13px; font-weight: 600; }
            QLabel#adminLoginError { color: #FF7B72; font-size: 13px; }
            QLineEdit { background: #0D1117; color: #F0F6FC; border: 1px solid #484F58; border-radius: 8px; padding: 10px 12px; font-size: 14px; }
            QLineEdit:focus { border: 2px solid #2F81F7; }
            QPushButton { border-radius: 8px; padding: 10px 16px; font-size: 14px; font-weight: 700; }
            QPushButton#adminLoginPrimary { background: #2F81F7; color: white; border: 1px solid #2F81F7; }
            QPushButton#adminLoginPrimary:hover { background: #1F6FEB; }
            QPushButton#adminLoginSecondary { background: #21262D; color: #E6EDF3; border: 1px solid #484F58; }
            QPushButton#adminLoginSecondary:hover { background: #30363D; }
        """)

    def on_show(self, **kwargs):
        self._user_input.clear()
        self._pass_input.clear()
        self._error_label.setText("")
        self._user_input.setFocus()

    def _attempt_login(self):
        username = self._user_input.text().strip()
        password = self._pass_input.text()
        if not username or not password:
            self._error_label.setText("Enter your administrator username and password.")
            return
        ok = self._ctx.auth.login(username, password)
        if ok:
            self._ctx.navigate("admin_panel")
        else:
            self._error_label.setText("Invalid credentials. Check your username and password.")
            self._pass_input.clear()
