"""
Screen A: New Process (عملية جديدة).
Allows user to select the PDF bank statement, the target Excel template, and start analysis.
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QFrame, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, Signal

from injaz.ui.theme import (
    COLOR_NAVY, COLOR_TEAL, COLOR_BORDER, COLOR_SURFACE, COLOR_BG, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY, COLOR_ERROR, ThemeManager, get_theme
)



class FileSelectCard(QFrame):
    """
    Component for selecting, viewing, replacing, and removing an input file.
    """
    file_selected = Signal(str)
    file_cleared = Signal()

    def __init__(self, title: str, button_text: str, file_filter: str, icon_symbol: str = "📄", parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.file_filter = file_filter
        self.selected_path = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Header with icon and title
        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        
        icon_lbl = QLabel(icon_symbol)
        icon_lbl.setStyleSheet(f"font-size: 22px; color: {COLOR_TEAL};")
        header_row.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("sectionTitle")
        header_row.addWidget(title_lbl)
        header_row.addStretch()

        layout.addLayout(header_row)

        # Empty state (Browse button)
        self.empty_widget = QWidget()
        empty_layout = QHBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_browse = QPushButton(button_text)
        self.btn_browse.setObjectName("primaryButton")
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(self._browse_file)
        empty_layout.addWidget(self.btn_browse)
        empty_layout.addStretch()

        layout.addWidget(self.empty_widget)

        # Selected state (File info + Change / Remove)
        self.selected_widget = QWidget()
        self.selected_widget.setVisible(False)
        selected_layout = QHBoxLayout(self.selected_widget)
        selected_layout.setContentsMargins(0, 0, 0, 0)
        selected_layout.setSpacing(10)

        info_vbox = QVBoxLayout()
        info_vbox.setSpacing(3)

        self.lbl_filename = QLabel("")
        self.lbl_filename.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLOR_NAVY};")
        info_vbox.addWidget(self.lbl_filename)

        self.lbl_filepath = QLabel("")
        self.lbl_filepath.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_SECONDARY};")
        info_vbox.addWidget(self.lbl_filepath)

        selected_layout.addLayout(info_vbox, stretch=1)

        self.btn_replace = QPushButton("تغيير")
        self.btn_replace.setObjectName("secondaryButton")
        self.btn_replace.setCursor(Qt.PointingHandCursor)
        self.btn_replace.clicked.connect(self._browse_file)
        selected_layout.addWidget(self.btn_replace)

        self.btn_remove = QPushButton("إلغاء")
        self.btn_remove.setObjectName("dangerButton")
        self.btn_remove.setCursor(Qt.PointingHandCursor)
        self.btn_remove.clicked.connect(self.clear_file)
        selected_layout.addWidget(self.btn_remove)

        layout.addWidget(self.selected_widget)

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "اختيار الملف",
            "",
            self.file_filter
        )
        if file_path:
            self.set_file(file_path)

    def set_file(self, path: str):
        self.selected_path = os.path.abspath(path)
        self.lbl_filename.setText(os.path.basename(self.selected_path))
        self.lbl_filepath.setText(self.selected_path)
        self.empty_widget.setVisible(False)
        self.selected_widget.setVisible(True)
        self.file_selected.emit(self.selected_path)

    def clear_file(self):
        self.selected_path = ""
        self.lbl_filename.setText("")
        self.lbl_filepath.setText("")
        self.selected_widget.setVisible(False)
        self.empty_widget.setVisible(True)
        self.file_cleared.emit()

    def set_theme(self, theme_name: str):
        theme = get_theme(theme_name)
        if hasattr(self, "lbl_filename"):
            self.lbl_filename.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {theme.text_primary};")
        if hasattr(self, "lbl_filepath"):
            self.lbl_filepath.setStyleSheet(f"font-size: 11px; color: {theme.text_secondary};")


class NewProcessPage(QWidget):
    """
    Screen A: Main view for selecting PDF account statement, configuring output,
    and launching extraction. Does not require an Excel template.
    """
    start_analysis_requested = Signal(str, str)  # pdf_path, output_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("newProcessPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.theme_name = ThemeManager.instance().current_theme
        self.pdf_path = ""
        self.template_path = ""
        self.output_path = ""

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(20)

        # 1. Header & Subtitle
        header_vbox = QVBoxLayout()
        header_vbox.setSpacing(4)
        
        title_lbl = QLabel("عملية جديدة")
        title_lbl.setObjectName("pageTitle")
        header_vbox.addWidget(title_lbl)

        subtitle_lbl = QLabel("استخرج معاملات كشف حساب PDF وراجعها ثم صدّرها إلى مصنف Excel جديد بسهولة وأمان.")
        subtitle_lbl.setObjectName("pageSubtitle")
        header_vbox.addWidget(subtitle_lbl)

        main_layout.addLayout(header_vbox)

        # 2. File Selection Cards
        cards_vbox = QVBoxLayout()
        cards_vbox.setSpacing(16)

        # PDF Statement Card
        self.pdf_card = FileSelectCard(
            title="كشف الحساب البنكي (PDF)",
            button_text="اختيار ملف PDF",
            file_filter="كشوفات الحساب PDF (*.pdf)",
            icon_symbol="📑"
        )
        self.pdf_card.file_selected.connect(self._on_pdf_selected)
        self.pdf_card.file_cleared.connect(self._on_pdf_cleared)
        cards_vbox.addWidget(self.pdf_card)

        # Output Destination Card
        self.dest_card = QFrame()
        self.dest_card.setObjectName("cardFrame")
        dest_layout = QHBoxLayout(self.dest_card)
        dest_layout.setContentsMargins(20, 14, 20, 14)
        dest_layout.setSpacing(12)

        dest_vbox = QVBoxLayout()
        dest_vbox.setSpacing(3)
        lbl_dest_title = QLabel("مسار حفظ مصنف Excel الجديد:")
        lbl_dest_title.setObjectName("fieldLabel")
        dest_vbox.addWidget(lbl_dest_title)

        self.lbl_dest_path = QLabel("سيتم تحديد المسار تلقائياً بعد اختيار كشف الحساب...")
        self.lbl_dest_path.setStyleSheet(f"font-size: 12px; color: {COLOR_NAVY};")
        dest_vbox.addWidget(self.lbl_dest_path)
        dest_layout.addLayout(dest_vbox, stretch=1)

        self.btn_change_dest = QPushButton("تغيير الوجهة")
        self.btn_change_dest.setObjectName("secondaryButton")
        self.btn_change_dest.setCursor(Qt.PointingHandCursor)
        self.btn_change_dest.clicked.connect(self._browse_destination)
        self.btn_change_dest.setEnabled(False)
        dest_layout.addWidget(self.btn_change_dest)

        cards_vbox.addWidget(self.dest_card)
        main_layout.addLayout(cards_vbox)

        # 3. Progress State (Initially hidden)
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("cardFrame")
        self.progress_frame.setStyleSheet(f"background-color: #E6F4F1; border: 1px solid {COLOR_TEAL};")
        self.progress_frame.setVisible(False)
        prog_layout = QVBoxLayout(self.progress_frame)
        prog_layout.setContentsMargins(20, 14, 20, 14)
        prog_layout.setSpacing(8)

        self.lbl_progress_status = QLabel("جاري قراءة كشف الحساب...")
        self.lbl_progress_status.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {COLOR_NAVY};")
        prog_layout.addWidget(self.lbl_progress_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #CBD5E1;
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_TEAL};
                border-radius: 4px;
            }}
        """)
        prog_layout.addWidget(self.progress_bar)

        main_layout.addWidget(self.progress_frame)

        main_layout.addStretch()

        # 4. Primary Bottom Action
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.btn_start = QPushButton("ابدأ التحليل")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setFixedHeight(44)
        self.btn_start.setMinimumWidth(200)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._on_start_clicked)
        action_layout.addWidget(self.btn_start)

        main_layout.addLayout(action_layout)

        self.set_theme(self.theme_name)

    def set_theme(self, theme_name: str):
        """Updates NewProcessPage and child cards to active theme."""
        self.theme_name = theme_name
        theme = get_theme(theme_name)
        self.setStyleSheet(f"#newProcessPage {{ background-color: {theme.bg}; }}")
        if hasattr(self, "pdf_card"):
            self.pdf_card.set_theme(theme_name)
        if hasattr(self, "lbl_dest_path"):
            self.lbl_dest_path.setStyleSheet(f"font-size: 12px; color: {theme.text_primary};")
        if hasattr(self, "progress_frame"):
            if theme_name == "dark":
                self.progress_frame.setStyleSheet(f"background-color: {theme.teal_bg}; border: 1px solid {theme.teal};")
            else:
                self.progress_frame.setStyleSheet(f"background-color: #E6F4F1; border: 1px solid {theme.teal};")
        if hasattr(self, "lbl_progress_status"):
            self.lbl_progress_status.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {theme.text_primary};")

    def _on_pdf_selected(self, path: str):
        self.pdf_path = path
        self._update_default_output()
        self._check_ready()

    def _on_pdf_cleared(self):
        self.pdf_path = ""
        self._update_default_output()
        self._check_ready()

    def _on_template_selected(self, path: str):
        self.template_path = path
        self._update_default_output()
        self._check_ready()

    def _on_template_cleared(self):
        self.template_path = ""
        self._update_default_output()
        self._check_ready()

    @staticmethod
    def get_default_exports_dir() -> str:
        """Returns standard user export directory (e.g. ~/Documents/INJAZ/Exports)."""
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents", "INJAZ", "Exports")
        try:
            os.makedirs(docs_dir, exist_ok=True)
            return docs_dir
        except Exception:
            return os.path.expanduser("~")

    def _update_default_output(self):
        """Sets a default safe output path in Documents/INJAZ/Exports, never inside references/."""
        if self.pdf_path and not self.output_path:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_dir = self.get_default_exports_dir()
            self.output_path = os.path.join(dest_dir, f"INJAZ_Transactions_{timestamp}.xlsx")
            self.lbl_dest_path.setText(self.output_path)
            self.btn_change_dest.setEnabled(True)
        elif not self.pdf_path:
            self.output_path = ""
            self.lbl_dest_path.setText("سيتم تحديد المسار تلقائياً بعد اختيار كشف الحساب...")
            self.btn_change_dest.setEnabled(False)

    def _browse_destination(self):
        default_dir = os.path.dirname(self.output_path) if self.output_path else ""
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "تحديد ملف المخرجات",
            default_dir,
            "ملفات إكسيل (*.xlsx)"
        )
        if save_path:
            if not save_path.endswith(".xlsx"):
                save_path += ".xlsx"
            self.output_path = os.path.abspath(save_path)
            self.lbl_dest_path.setText(self.output_path)
            self._check_ready()

    def _check_ready(self):
        is_ready = bool(
            self.pdf_path
            and os.path.exists(self.pdf_path)
            and self.output_path
        )
        self.btn_start.setEnabled(is_ready)

    def _on_start_clicked(self):
        # 1. Validation checks
        if not os.path.exists(self.pdf_path):
            QMessageBox.critical(self, "خطأ في الملف", "ملف كشف الحساب PDF المحدد غير موجود.")
            return

        # Ensure output destination does not overwrite PDF source file
        real_output = os.path.normcase(os.path.realpath(self.output_path))
        real_pdf = os.path.normcase(os.path.realpath(self.pdf_path))
        if real_output == real_pdf:
            QMessageBox.critical(
                self,
                "مسار غير صالح",
                "مسار ملف المخرجات مطابق لملف PDF الأصلي!\n"
                "يجب حفظ النتيجة في ملف إكسيل منفصل."
            )
            return

        # Disable button and show progress
        self.btn_start.setEnabled(False)
        self.progress_frame.setVisible(True)
        self.lbl_progress_status.setText("قراءة كشف الحساب واستخراج المعاملات...")
        self.progress_bar.setValue(10)

        self.start_analysis_requested.emit(self.pdf_path, self.output_path)

    def update_progress(self, stage_text: str, percentage: int):
        self.progress_frame.setVisible(True)
        self.lbl_progress_status.setText(stage_text)
        self.progress_bar.setValue(percentage)

    def reset_progress(self):
        self.progress_frame.setVisible(False)
        self.btn_start.setEnabled(True)
        self.progress_bar.setValue(0)

    def reset_page(self):
        """Resets all file inputs and state back to empty."""
        self.pdf_card.clear_file()
        self.pdf_path = ""
        self.template_path = ""
        self.output_path = ""
        self.lbl_dest_path.setText("سيتم تحديد المسار تلقائياً بعد اختيار كشف الحساب...")
        self.btn_change_dest.setEnabled(False)
        self.reset_progress()
        self._check_ready()
