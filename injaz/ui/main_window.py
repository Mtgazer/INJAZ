"""
Main Window for INJAZ (إنجاز) Desktop Application.
Coordinates top brand header, 3-step workflow views, and background worker threads.
"""
import os
from typing import List, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QMessageBox
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt

from injaz.models import ProcessingResult, TransactionRecord
from injaz.ui.theme import (
    ThemeManager, get_stylesheet, apply_theme_to_app
)
from injaz.ui.components.header import HeaderWidget
from injaz.ui.pages.new_process_page import NewProcessPage
from injaz.ui.pages.review_page import ReviewPage
from injaz.ui.pages.export_page import ExportPage
from injaz.ui.workers import AnalysisWorker, ExportWorker, CsvExportWorker


class MainWindow(QMainWindow):
    """
    Main application window implementing the 3-step workflow:
    1. New Process (الملفات)
    2. Review (المراجعة)
    3. Export (التصدير)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إنجاز - INJAZ")
        self.resize(1260, 820)
        self.setMinimumSize(1050, 700)

        # Application state
        self.pdf_path: str = ""
        self.template_path: str = ""
        self.output_path: str = ""
        self.records: List[TransactionRecord] = []
        self.current_theme: str = ThemeManager.instance().current_theme

        # Worker threads tracking
        self.analysis_worker: Optional[AnalysisWorker] = None
        self.export_worker: Optional[ExportWorker] = None
        self.csv_export_worker: Optional[ExportWorker] = None

        # Set application icon
        self._set_app_icon()

        # Apply initial theme stylesheet
        self.setStyleSheet(get_stylesheet(self.current_theme))

        # Central widget and layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Header with branding and 3-step workflow breadcrumb
        self.header = HeaderWidget(self)
        root_layout.addWidget(self.header)

        # 2. Stacked Pages container
        self.stack = QStackedWidget(self)
        root_layout.addWidget(self.stack, stretch=1)

        # Instantiate Pages
        self.new_process_page = NewProcessPage(self)
        self.review_page = ReviewPage(self)
        self.export_page = ExportPage(self)

        self.stack.addWidget(self.new_process_page)  # Index 0
        self.stack.addWidget(self.review_page)       # Index 1
        self.stack.addWidget(self.export_page)       # Index 2

        # Connect signals
        self._connect_signals()

        # Apply current theme to all pages and header
        self.apply_theme(self.current_theme)

        # Initialize on Step 1
        self._show_step_1()

    def _set_app_icon(self):
        from injaz.paths import get_asset_path
        icon_path = get_asset_path("app_icon.ico")
        if not os.path.exists(icon_path):
            icon_path = get_asset_path("app_icon.png")
        if not os.path.exists(icon_path):
            icon_path = get_asset_path("icon_mark.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def _connect_signals(self):
        # Header controls
        self.header.theme_toggle_requested.connect(self._toggle_theme)
        self.header.step_clicked.connect(self._on_header_step_clicked)

        # Step 1: New Process signals
        self.new_process_page.start_analysis_requested.connect(self._on_start_analysis_requested)

        # Step 2: Review Page signals
        self.review_page.back_to_files_requested.connect(self._show_step_1)
        self.review_page.proceed_to_export_requested.connect(self._show_step_3)

        # Step 3: Export Page signals
        self.export_page.back_to_review_requested.connect(self._show_step_2)
        self.export_page.export_started.connect(self._on_export_started)
        self.export_page.csv_export_started.connect(self._on_csv_export_started)
        self.export_page.new_process_requested.connect(self._reset_to_step_1)

    # ---------------------------------------------------------
    # Theme & Navigation Methods
    # ---------------------------------------------------------
    def _toggle_theme(self):
        """Toggles between Light and Dark themes, immediately refreshing entire app."""
        new_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme(new_theme)

    def apply_theme(self, theme_name: str):
        """Applies theme tokens and stylesheets across all views and persists preference."""
        self.current_theme = theme_name
        ThemeManager.instance().set_theme(theme_name)
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            apply_theme_to_app(app, theme_name)
        self.setStyleSheet(get_stylesheet(theme_name))
        self.header.set_theme(theme_name)
        if hasattr(self.new_process_page, "set_theme"):
            self.new_process_page.set_theme(theme_name)
        if hasattr(self.review_page, "set_theme"):
            self.review_page.set_theme(theme_name)
        if hasattr(self.export_page, "set_theme"):
            self.export_page.set_theme(theme_name)

    def _on_header_step_clicked(self, step: int):
        """Navigates to the clicked step if permitted by workflow state."""
        if step == 1:
            self._show_step_1()
        elif step == 2 and self.records:
            self._show_step_2()
        elif step == 3 and self.records:
            self._show_step_3()
    def _show_step_1(self):
        self.header.set_current_step(1)
        self.stack.setCurrentIndex(0)

    def _show_step_2(self):
        self.header.set_current_step(2)
        self.stack.setCurrentIndex(1)

    def _show_step_3(self):
        # Pass current records and target paths to ExportPage
        self.export_page.set_data(
            records=self.records,
            arg1=self.output_path
        )
        self.header.set_current_step(3)
        self.stack.setCurrentIndex(2)

    def _reset_to_step_1(self):
        self.records = []
        self.pdf_path = ""
        self.template_path = ""
        self.output_path = ""
        self.new_process_page.reset_page()
        self._show_step_1()

    # ---------------------------------------------------------
    # Analysis Workflow (Step 1 -> Step 2)
    # ---------------------------------------------------------
    def _on_start_analysis_requested(self, *args):
        if len(args) == 3:
            self.pdf_path = args[0]
            self.template_path = args[1]
            self.output_path = args[2]
        else:
            self.pdf_path = args[0]
            self.output_path = args[1]
            self.template_path = ""

        # Start background analysis worker
        self.analysis_worker = AnalysisWorker(self.pdf_path, self)
        self.analysis_worker.progress_updated.connect(self.new_process_page.update_progress)
        self.analysis_worker.analysis_finished.connect(self._on_analysis_success)
        self.analysis_worker.analysis_failed.connect(self._on_analysis_error)
        self.analysis_worker.start()

    def _on_analysis_success(self, result: ProcessingResult):
        self.records = result.records
        self.new_process_page.reset_progress()

        # Populate review page with real records
        self.review_page.set_records(self.records)

        # Transition to Step 2
        self._show_step_2()

    def _on_analysis_error(self, error_message: str):
        self.new_process_page.reset_progress()
        QMessageBox.critical(self, "خطأ في التحليل", error_message)

    # ---------------------------------------------------------
    # Export Workflow (Step 3)
    # ---------------------------------------------------------
    def _on_export_started(self, *args):
        if len(args) == 3:
            output_path = args[1]
            records = args[2]
        elif len(args) == 2:
            output_path = args[0]
            records = args[1]
        elif len(args) == 1:
            output_path = self.output_path
            records = args[0]
        else:
            output_path = self.output_path
            records = self.records

        self.export_worker = ExportWorker(
            output_path=output_path,
            records=records,
            export_format="xlsx",
            overwrite=True,
            parent=self
        )
        self.export_worker.export_finished.connect(self.export_page.handle_export_success)
        self.export_worker.export_failed.connect(self.export_page.handle_export_failure)
        self.export_worker.start()

    def _on_csv_export_started(self, output_path: str, records: List[TransactionRecord]):
        self.csv_export_worker = ExportWorker(
            output_path=output_path,
            records=records,
            export_format="csv",
            overwrite=True,
            parent=self
        )
        self.csv_export_worker.export_finished.connect(self.export_page.handle_csv_export_success)
        self.csv_export_worker.export_failed.connect(self.export_page.handle_export_failure)
        self.csv_export_worker.start()


