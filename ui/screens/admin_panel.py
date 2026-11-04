"""
Admin Panel Screen.
Provides exam management: create exams, upload questions (CSV/QTI),
register candidates, and export results.
"""

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QTabWidget, QTableWidget,
    QTableWidgetItem, QSpinBox, QFrame, QHeaderView, QScrollArea,
)
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class AdminPanelScreen(QWidget):
    def __init__(self, app_ctx):
        super().__init__()
        self._ctx = app_ctx
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(20)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Administrator dashboard")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Manage examinations, candidates, and results")
        subtitle.setObjectName("pageSubtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        logout_btn = QPushButton("Logout")
        logout_btn.setObjectName("logoutButton")
        logout_btn.setMinimumHeight(38)
        logout_btn.clicked.connect(self._logout)
        header.addLayout(title_block)
        header.addStretch()
        header.addWidget(logout_btn)
        layout.addLayout(header)

        tabs = QTabWidget()
        tabs.setObjectName("adminTabs")
        tabs.addTab(self._scroll_tab(self._build_exam_tab()), "Exams")
        tabs.addTab(self._scroll_tab(self._build_candidates_tab()), "Candidates")
        tabs.addTab(self._scroll_tab(self._build_results_tab()), "Results")
        layout.addWidget(tabs)

        self.setStyleSheet("""
            QWidget { background: #0D1117; color: #E6EDF3; font-family: Arial; font-size: 14px; }
            QLabel { background: transparent; }
            QLabel#pageTitle { font-size: 27px; font-weight: 800; color: #F0F6FC; }
            QLabel#pageSubtitle { color: #9DA7B3; font-size: 13px; }
            QLabel#sectionTitle { font-size: 17px; font-weight: 700; color: #F0F6FC; }
            QLabel#sectionHint { color: #A6B0BC; font-size: 12px; }
            QLabel#fieldLabel { color: #D5DDE5; font-size: 13px; font-weight: 600; }
            QLabel#statusMessage { color: #7EE787; font-weight: 600; padding: 8px 10px; }
            QFrame#sectionCard { background: #161B22; border: 1px solid #30363D; border-radius: 12px; }
            QLineEdit, QSpinBox {
                background: #0D1117; color: #F0F6FC; border: 1px solid #484F58;
                border-radius: 7px; padding: 8px 10px; selection-background-color: #2F81F7;
            }
            QLineEdit:focus, QSpinBox:focus { border: 2px solid #2F81F7; }
            QPushButton {
                background: #21262D; color: #F0F6FC; border: 1px solid #484F58;
                border-radius: 8px; padding: 9px 15px; font-weight: 600;
            }
            QPushButton:hover { background: #30363D; border-color: #6E7681; }
            QPushButton:pressed { background: #161B22; }
            QPushButton#primaryButton { background: #2F81F7; color: white; border-color: #2F81F7; }
            QPushButton#primaryButton:hover { background: #1F6FEB; }
            QPushButton#logoutButton { color: #FF7B72; border-color: #6E3B3B; }
            QTabWidget#adminTabs::pane { border: 1px solid #30363D; border-radius: 10px; top: -1px; background: #0D1117; }
            QTabBar::tab { background: #161B22; color: #A6B0BC; padding: 12px 22px; margin-right: 5px; border: 1px solid #30363D; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QTabBar::tab:selected { background: #21262D; color: #F0F6FC; border-color: #2F81F7; }
            QTableWidget { background: #0D1117; alternate-background-color: #161B22; color: #E6EDF3; border: 1px solid #30363D; border-radius: 8px; gridline-color: #30363D; }
            QHeaderView::section { background: #21262D; color: #E6EDF3; padding: 9px; border: none; border-bottom: 1px solid #30363D; font-weight: 700; }
            QScrollArea { background: #0D1117; border: none; }
            QScrollBar:vertical { background: #161B22; width: 14px; margin: 2px; border-radius: 6px; }
            QScrollBar::handle:vertical { background: #484F58; min-height: 34px; border-radius: 6px; }
            QScrollBar::handle:vertical:hover { background: #6E7681; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

    @staticmethod
    def _scroll_tab(content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _section_card(title: str, hint: str = ""):
        card = QFrame()
        card.setObjectName("sectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        if hint:
            detail = QLabel(hint)
            detail.setObjectName("sectionHint")
            detail.setWordWrap(True)
            layout.addWidget(detail)
        return card, layout

    # ------------------------------------------------------------------
    # Exams tab
    # ------------------------------------------------------------------

    def _build_exam_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        create_card, create_layout = self._section_card(
            "Create an examination", "Choose a clear title and the time allowed for candidates."
        )

        title_row = QHBoxLayout()
        title_label = QLabel("Exam title")
        title_label.setObjectName("fieldLabel")
        title_row.addWidget(title_label)
        self._exam_title_input = QLineEdit()
        self._exam_title_input.setMinimumHeight(40)
        self._exam_title_input.setPlaceholderText("e.g. Computer Science Paper 1")
        title_row.addWidget(self._exam_title_input)
        create_layout.addLayout(title_row)

        time_row = QHBoxLayout()
        time_label = QLabel("Time limit (minutes)")
        time_label.setObjectName("fieldLabel")
        time_row.addWidget(time_label)
        self._time_spin = QSpinBox()
        self._time_spin.setMinimum(5)
        self._time_spin.setMaximum(300)
        self._time_spin.setValue(60)
        self._time_spin.setSuffix(" min")
        self._time_spin.setMinimumHeight(40)
        time_row.addWidget(self._time_spin)
        time_row.addStretch()
        create_layout.addLayout(time_row)

        create_btn = QPushButton("Create Exam")
        create_btn.setObjectName("primaryButton")
        create_btn.setMinimumHeight(44)
        create_btn.clicked.connect(self._create_exam)
        create_layout.addWidget(create_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(create_card)

        saved_card, saved_layout = self._section_card(
            "Saved examinations", "Created exams stay listed here. Select one to load its ID for question imports."
        )
        self._exam_table = QTableWidget()
        self._exam_table.setColumnCount(3)
        self._exam_table.setHorizontalHeaderLabels(["Exam title", "Exam ID", "Time limit"])
        self._exam_table.setAlternatingRowColors(True)
        self._exam_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._exam_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._exam_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._exam_table.verticalHeader().setVisible(False)
        self._exam_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._exam_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._exam_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._exam_table.setMinimumHeight(150)
        self._exam_table.itemSelectionChanged.connect(self._select_exam_row)
        saved_layout.addWidget(self._exam_table)
        saved_actions = QHBoxLayout()
        use_exam_btn = QPushButton("Use selected exam for import")
        use_exam_btn.clicked.connect(self._use_selected_exam)
        copy_exam_btn = QPushButton("Copy selected exam ID")
        copy_exam_btn.clicked.connect(self._copy_selected_exam_id)
        refresh_exam_btn = QPushButton("Refresh exams")
        refresh_exam_btn.clicked.connect(self._refresh_exams)
        saved_actions.addWidget(use_exam_btn)
        saved_actions.addWidget(copy_exam_btn)
        saved_actions.addStretch()
        saved_actions.addWidget(refresh_exam_btn)
        saved_layout.addLayout(saved_actions)
        layout.addWidget(saved_card)

        import_card, import_layout = self._section_card(
            "Add questions", "Import multiple-choice questions only, using CSV or QTI 3.0 XML. Each item needs at least two choices and one correct answer."
        )
        exam_id_row = QHBoxLayout()
        exam_id_label = QLabel("Exam ID")
        exam_id_label.setObjectName("fieldLabel")
        exam_id_row.addWidget(exam_id_label)
        self._import_exam_id = QLineEdit()
        self._import_exam_id.setMinimumHeight(40)
        self._import_exam_id.setPlaceholderText("Select a saved exam above or paste its ID")
        exam_id_row.addWidget(self._import_exam_id)
        import_layout.addLayout(exam_id_row)

        import_row = QHBoxLayout()
        csv_btn = QPushButton("Import CSV")
        csv_btn.setObjectName("primaryButton")
        csv_btn.setMinimumHeight(44)
        csv_btn.clicked.connect(lambda: self._import_questions("csv"))
        qti_btn = QPushButton("Import QTI XML")
        qti_btn.setMinimumHeight(44)
        qti_btn.clicked.connect(lambda: self._import_questions("qti"))
        import_row.addWidget(csv_btn)
        import_row.addWidget(qti_btn)
        import_layout.addLayout(import_row)
        layout.addWidget(import_card)

        self._exam_status = QLabel("")
        self._exam_status.setObjectName("statusMessage")
        layout.addWidget(self._exam_status)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # Candidates tab
    # ------------------------------------------------------------------

    def _build_candidates_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        register_card, register_layout = self._section_card(
            "Register a candidate", "Enter the same candidate ID they will use on the login screen."
        )
        row1 = QHBoxLayout()
        id_label = QLabel("Candidate ID")
        id_label.setObjectName("fieldLabel")
        row1.addWidget(id_label)
        self._cand_id = QLineEdit()
        self._cand_id.setMinimumHeight(40)
        self._cand_id.setPlaceholderText("e.g. 2024CS001")
        row1.addWidget(self._cand_id)
        name_label = QLabel("Full name")
        name_label.setObjectName("fieldLabel")
        row1.addWidget(name_label)
        self._cand_name = QLineEdit()
        self._cand_name.setMinimumHeight(40)
        self._cand_name.setPlaceholderText("Candidate's name")
        row1.addWidget(self._cand_name)
        register_layout.addLayout(row1)

        reg_btn = QPushButton("Register Candidate")
        reg_btn.setObjectName("primaryButton")
        reg_btn.setMinimumHeight(44)
        reg_btn.clicked.connect(self._register_candidate)
        register_layout.addWidget(reg_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(register_card)

        import_card, import_layout = self._section_card(
            "Import a student list", "Bulk add candidates from a CSV file with id and full_name columns."
        )
        bulk_btn = QPushButton("Import Candidates CSV")
        bulk_btn.setObjectName("primaryButton")
        bulk_btn.setMinimumHeight(44)
        bulk_btn.clicked.connect(self._bulk_import_candidates)
        import_layout.addWidget(bulk_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(import_card)

        self._cand_status = QLabel("")
        self._cand_status.setObjectName("statusMessage")
        layout.addWidget(self._cand_status)

        table_card, table_layout = self._section_card("Registered candidates")
        self._cand_table = QTableWidget()
        self._cand_table.setColumnCount(3)
        self._cand_table.setHorizontalHeaderLabels(["ID", "Name", "Language"])
        self._cand_table.setAlternatingRowColors(True)
        self._cand_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._cand_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._cand_table.verticalHeader().setVisible(False)
        self._cand_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._cand_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._cand_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._cand_table.setMinimumHeight(150)
        table_layout.addWidget(self._cand_table)

        refresh_btn = QPushButton("Refresh List")
        refresh_btn.setMinimumHeight(38)
        refresh_btn.clicked.connect(self._refresh_candidates)
        table_layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(table_card, 1)
        return w

    # ------------------------------------------------------------------
    # Results tab
    # ------------------------------------------------------------------

    def _build_results_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        card, card_layout = self._section_card(
            "Export examination results", "Export all available results or filter the export to one exam."
        )
        row = QHBoxLayout()
        exam_id_label = QLabel("Exam ID (optional)")
        exam_id_label.setObjectName("fieldLabel")
        row.addWidget(exam_id_label)
        self._results_exam_id = QLineEdit()
        self._results_exam_id.setMinimumHeight(40)
        self._results_exam_id.setPlaceholderText("Leave blank to export all results")
        row.addWidget(self._results_exam_id)
        card_layout.addLayout(row)

        export_btn = QPushButton("Export Results CSV")
        export_btn.setObjectName("primaryButton")
        export_btn.setMinimumHeight(44)
        export_btn.clicked.connect(self._export_results)
        card_layout.addWidget(export_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(card)

        self._results_status = QLabel("")
        self._results_status.setObjectName("statusMessage")
        layout.addWidget(self._results_status)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # on_show
    # ------------------------------------------------------------------

    def on_show(self, **kwargs):
        if not self._ctx.auth.is_logged_in():
            self._ctx.navigate("admin_login")
            return
        self._refresh_candidates()
        self._refresh_exams()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _create_exam(self):
        title = self._exam_title_input.text().strip()
        if not title:
            self._exam_status.setText("Please enter an exam title.")
            return
        time_limit = self._time_spin.value() * 60
        eid = self._ctx.admin.create_exam(title, time_limit)
        self._exam_status.setText(f"Exam created. ID: {eid}")
        self._exam_title_input.clear()
        self._import_exam_id.setText(eid)
        self._refresh_exams()

    def _refresh_exams(self):
        rows = self._ctx.db.fetchall(
            "SELECT id, title, time_limit FROM exams ORDER BY rowid DESC"
        )
        self._exam_table.setRowCount(len(rows))
        for index, exam in enumerate(rows):
            self._exam_table.setItem(index, 0, QTableWidgetItem(exam["title"]))
            self._exam_table.setItem(index, 1, QTableWidgetItem(exam["id"]))
            minutes = int(exam["time_limit"] or 0) // 60
            self._exam_table.setItem(index, 2, QTableWidgetItem(f"{minutes} min"))
        if rows:
            self._exam_table.selectRow(0)

    def _selected_exam_id(self) -> str:
        row = self._exam_table.currentRow()
        item = self._exam_table.item(row, 1) if row >= 0 else None
        return item.text() if item else ""

    def _select_exam_row(self):
        exam_id = self._selected_exam_id()
        if exam_id:
            self._import_exam_id.setText(exam_id)

    def _use_selected_exam(self):
        exam_id = self._selected_exam_id()
        if exam_id:
            self._import_exam_id.setText(exam_id)
            self._exam_status.setText("Selected exam ID is ready for question import.")

    def _copy_selected_exam_id(self):
        exam_id = self._selected_exam_id()
        if not exam_id:
            self._exam_status.setText("Select an exam before copying its ID.")
            return
        QApplication.clipboard().setText(exam_id)
        self._exam_status.setText("Exam ID copied to the clipboard.")

    def _import_questions(self, fmt: str):
        exam_id = self._import_exam_id.text().strip()
        if not exam_id:
            self._exam_status.setText("Enter Exam ID before importing.")
            return
        filter_str = "CSV Files (*.csv)" if fmt == "csv" else "XML Files (*.xml)"
        path, _ = QFileDialog.getOpenFileName(self, "Select file", "", filter_str)
        if not path:
            return
        try:
            if fmt == "csv":
                n = self._ctx.admin.import_questions_csv(path, exam_id)
            else:
                n = self._ctx.admin.import_questions_qti(path, exam_id)
            self._exam_status.setText(f"Imported {n} questions from {Path(path).name}.")
        except Exception as exc:
            self._exam_status.setText(f"Import failed: {exc}")
            logger.error(f"Question import error: {exc}")

    def _register_candidate(self):
        cid = self._cand_id.text().strip()
        name = self._cand_name.text().strip()
        if not cid or not name:
            self._cand_status.setText("ID and name required.")
            return
        ok = self._ctx.admin.register_candidate(cid, name)
        if ok:
            self._cand_status.setText(f"Candidate {cid} registered.")
            self._cand_id.clear()
            self._cand_name.clear()
            self._refresh_candidates()
        else:
            self._cand_status.setText(f"Failed: ID '{cid}' may already exist.")

    def _bulk_import_candidates(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select candidates CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            n = self._ctx.admin.register_candidates_csv(path)
            self._cand_status.setText(f"Registered {n} candidates.")
            self._refresh_candidates()
        except Exception as exc:
            self._cand_status.setText(f"Import failed: {exc}")

    def _refresh_candidates(self):
        profiles = self._ctx.profile_manager.list_all()
        self._cand_table.setRowCount(len(profiles))
        for row, p in enumerate(profiles):
            self._cand_table.setItem(row, 0, QTableWidgetItem(p.id))
            self._cand_table.setItem(row, 1, QTableWidgetItem(p.full_name))
            self._cand_table.setItem(row, 2, QTableWidgetItem(p.language))

    def _export_results(self):
        exam_id = self._results_exam_id.text().strip() or None
        path, _ = QFileDialog.getSaveFileName(self, "Save results", "results.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            self._ctx.admin.save_results_csv(path, exam_id)
            self._results_status.setText(f"Results saved to {Path(path).name}.")
        except Exception as exc:
            self._results_status.setText(f"Export failed: {exc}")

    def _logout(self):
        self._ctx.auth.logout()
        self._ctx.navigate("login")
