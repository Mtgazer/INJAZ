"""
Custom Accessible Light-Theme Dialogs for INJAZ (إنجاز).
Guarantees strict adherence to brand palette, high contrast,
and native Arabic RTL layout regardless of operating system dark-mode settings.
"""
import os
import platform
import subprocess
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont

from injaz.ui.theme import (
    COLOR_NAVY, COLOR_NAVY_HOVER, COLOR_TEAL, COLOR_TEAL_HOVER,
    COLOR_BG, COLOR_SURFACE, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_BORDER, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    ThemeManager, get_theme, get_dialog_stylesheet
)


DIALOG_BASE_STYLE = f"""
QDialog {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
}}

QLabel {{
    color: {COLOR_TEXT_PRIMARY};
    background: transparent;
}}

QLabel#dialogTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {COLOR_NAVY};
}}

QLabel#dialogSubtitle {{
    font-size: 12px;
    color: {COLOR_TEXT_SECONDARY};
}}

QFrame#infoCard {{
    background-color: {COLOR_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 12px;
}}

QPushButton#btnPrimaryConfirm {{
    background-color: {COLOR_TEAL};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    padding: 9px 20px;
    min-height: 20px;
}}

QPushButton#btnPrimaryConfirm:hover {{
    background-color: {COLOR_TEAL_HOVER};
}}

QPushButton#btnPrimaryNavy {{
    background-color: {COLOR_NAVY};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    padding: 9px 18px;
    min-height: 20px;
}}

QPushButton#btnPrimaryNavy:hover {{
    background-color: {COLOR_NAVY_HOVER};
}}

QPushButton#btnCancelNeutral {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_NAVY};
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 18px;
    min-height: 20px;
}}

QPushButton#btnCancelNeutral:hover {{
    background-color: #F8FAFC;
    border-color: #94A3B8;
}}
"""


class BaseInjazDialog(QDialog):
    """Base dialog enforcing strict RTL, proper theme surface, and high contrast."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setLayoutDirection(Qt.RightToLeft)
        theme_name = ThemeManager.instance().current_theme
        self.setStyleSheet(get_dialog_stylesheet(theme_name))
        self.setModal(True)


class ExportConfirmDialog(BaseInjazDialog):
    """
    Export Confirmation Dialog:
    - Dynamic surface conforming to active theme
    - High contrast text
    - Primary Teal confirmation button: 'تأكيد التصدير'
    - Neutral secondary button: 'إلغاء'
    - Full Arabic RTL layout
    """
    def __init__(
        self,
        eligible_count: int,
        output_path: str,
        template_path: str = "",
        parent=None
    ):
        super().__init__("تأكيد عملية التصدير", parent)
        self.setMinimumWidth(500)
        theme = get_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        # Header with icon and title
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_lbl = QLabel("📊")
        icon_lbl.setStyleSheet(f"font-size: 26px; color: {theme.teal};")
        header_row.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        title_lbl = QLabel("تأكيد إنشاء مصنف Excel جديد")
        title_lbl.setObjectName("dialogTitle")
        title_vbox.addWidget(title_lbl)

        sub_lbl = QLabel("الرجاء مراجعة تفاصيل التصدير أدناه قبل الاعتماد.")
        sub_lbl.setObjectName("dialogSubtitle")
        title_vbox.addWidget(sub_lbl)

        header_row.addLayout(title_vbox)
        header_row.addStretch()
        layout.addLayout(header_row)

        # Info Card
        card = QFrame()
        card.setObjectName("infoCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        # Count
        row_cnt = QHBoxLayout()
        lbl_c_tag = QLabel("المعاملات المعتمدة الجاهزة للتصدير:")
        lbl_c_tag.setStyleSheet(f"font-weight: 600; color: {theme.text_primary};")
        lbl_c_val = QLabel(f"{eligible_count} معاملة")
        lbl_c_val.setStyleSheet(f"font-weight: 800; font-size: 14px; color: {theme.success};")
        row_cnt.addWidget(lbl_c_tag)
        row_cnt.addWidget(lbl_c_val)
        row_cnt.addStretch()
        card_layout.addLayout(row_cnt)

        # Output path
        lbl_out_title = QLabel("مسار ملف المخرجات المستهدف:")
        lbl_out_title.setStyleSheet(f"font-weight: 600; font-size: 11px; color: {theme.text_secondary};")
        card_layout.addWidget(lbl_out_title)

        lbl_out_val = QLabel(output_path)
        lbl_out_val.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {theme.text_primary}; background-color: {theme.surface}; padding: 6px 10px; border: 1px solid {theme.border}; border-radius: 4px;")
        lbl_out_val.setWordWrap(True)
        card_layout.addWidget(lbl_out_val)

        # Safety bullets
        safety_text = (
            "• لن يتم تصدير أي معاملة مستبعدة أو معلقة.\n"
            "• سيتم إنشاء مصنف Excel جديد مستقل يتضمن كافة المعاملات المعتمدة.\n"
            "• البيانات تُصدّر بأرقام تسلسلية وتواريخ وقيم ضريبية رقمية دقيقة."
        )
        lbl_safety = QLabel(safety_text)
        lbl_safety.setStyleSheet(f"font-size: 11px; color: {theme.text_secondary}; line-height: 140%;")
        card_layout.addWidget(lbl_safety)

        layout.addWidget(card)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_cancel = QPushButton("إلغاء")
        self.btn_cancel.setObjectName("btnCancelNeutral")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        btn_layout.addStretch()

        self.btn_confirm = QPushButton("تأكيد التصدير")
        self.btn_confirm.setObjectName("btnPrimaryConfirm")
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_confirm)

        layout.addLayout(btn_layout)


class ExportSuccessDialog(BaseInjazDialog):
    """
    Success Dialog displayed after export completion:
    - Direct button to open the generated Excel workbook.
    - Direct button to open containing folder.
    - Button to start new process.
    - High contrast, light theme, accessible styling.
    """
    new_process_clicked = Signal()

    def __init__(
        self,
        output_path: str,
        records_exported: int,
        records_skipped: int = 0,
        parent=None
    ):
        super().__init__("تم تصدير الملف بنجاح", parent)
        self.output_path = output_path
        self.output_dir = os.path.dirname(os.path.abspath(output_path))
        self.setMinimumWidth(520)
        theme = get_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_lbl = QLabel("✅")
        icon_lbl.setStyleSheet(f"font-size: 28px; color: {theme.success};")
        header_row.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        title_lbl = QLabel("تم تصدير الملف بنجاح")
        title_lbl.setObjectName("dialogTitle")
        title_vbox.addWidget(title_lbl)

        sub_lbl = QLabel(f"تمت كتابة {records_exported} معاملة بنجاح.")
        sub_lbl.setObjectName("dialogSubtitle")
        title_vbox.addWidget(sub_lbl)

        header_row.addLayout(title_vbox)
        header_row.addStretch()
        layout.addLayout(header_row)

        # Details Card
        card = QFrame()
        card.setObjectName("infoCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)

        # File name
        row_fn = QHBoxLayout()
        lbl_fn_tag = QLabel("ملف المخرجات:")
        lbl_fn_tag.setStyleSheet(f"font-weight: 600; color: {theme.text_secondary};")
        lbl_fn_val = QLabel(os.path.basename(output_path))
        lbl_fn_val.setStyleSheet(f"font-weight: 700; color: {theme.text_primary};")
        row_fn.addWidget(lbl_fn_tag)
        row_fn.addWidget(lbl_fn_val)
        row_fn.addStretch()
        card_layout.addLayout(row_fn)

        # Full path
        lbl_p_tag = QLabel("المسار الكامل:")
        lbl_p_tag.setStyleSheet(f"font-weight: 600; color: {theme.text_secondary}; font-size: 11px;")
        card_layout.addWidget(lbl_p_tag)

        lbl_p_val = QLabel(output_path)
        lbl_p_val.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {theme.teal}; background: {theme.surface}; padding: 6px 10px; border: 1px solid {theme.border}; border-radius: 4px;")
        lbl_p_val.setWordWrap(True)
        card_layout.addWidget(lbl_p_val)

        if records_skipped > 0:
            lbl_skip = QLabel(f"• تم تخطي {records_skipped} معاملة كانت مسجلة مسبقاً.")
            lbl_skip.setStyleSheet(f"font-size: 11px; color: {theme.warning}; font-weight: 600;")
            card_layout.addWidget(lbl_skip)

        lbl_note = QLabel("• تم إنشاء وتنسيق المصنف والتحقق من سلامة البيانات رقمياً.")
        lbl_note.setStyleSheet(f"font-size: 11px; color: {theme.success};")
        card_layout.addWidget(lbl_note)

        layout.addWidget(card)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # Open File Button
        is_csv = output_path.lower().endswith(".csv")
        btn_text = "فتح ملف CSV" if is_csv else "فتح ملف Excel"
        self.btn_open_file = QPushButton(btn_text)
        self.btn_open_file.setObjectName("btnPrimaryConfirm")
        self.btn_open_file.setCursor(Qt.PointingHandCursor)
        self.btn_open_file.clicked.connect(self._open_file)
        btn_layout.addWidget(self.btn_open_file)

        # Open Folder Button
        self.btn_open_folder = QPushButton("فتح مجلد الملف")
        self.btn_open_folder.setObjectName("btnPrimaryNavy")
        self.btn_open_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self._open_folder)
        btn_layout.addWidget(self.btn_open_folder)

        btn_layout.addStretch()

        # Start New Process Button
        self.btn_new = QPushButton("عملية جديدة")
        self.btn_new.setObjectName("btnCancelNeutral")
        self.btn_new.setCursor(Qt.PointingHandCursor)
        self.btn_new.clicked.connect(self._on_new_process)
        btn_layout.addWidget(self.btn_new)

        # Close
        self.btn_close = QPushButton("إغلاق")
        self.btn_close.setObjectName("btnCancelNeutral")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _open_file(self):
        if os.path.exists(self.output_path):
            if platform.system() == "Windows":
                os.startfile(self.output_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", self.output_path])
            else:
                subprocess.Popen(["xdg-open", self.output_path])

    def _open_folder(self):
        if os.path.exists(self.output_dir):
            if platform.system() == "Windows":
                os.startfile(self.output_dir)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", self.output_dir])
            else:
                subprocess.Popen(["xdg-open", self.output_dir])

    def _on_new_process(self):
        self.accept()
        self.new_process_clicked.emit()


class ExportSkippedDialog(BaseInjazDialog):
    """Dialog displayed when all submitted records already exist in the workbook."""
    def __init__(self, output_path: str, skipped_count: int, parent=None):
        super().__init__("تنبيه: المعاملات مسجلة مسبقاً", parent)
        self.output_path = output_path
        self.output_dir = os.path.dirname(os.path.abspath(output_path))
        self.setMinimumWidth(500)
        theme = get_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_lbl = QLabel("ℹ️")
        icon_lbl.setStyleSheet(f"font-size: 26px; color: {theme.warning};")
        header_row.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        title_lbl = QLabel("كافة المعاملات مسجلة مسبقاً")
        title_lbl.setObjectName("dialogTitle")
        title_vbox.addWidget(title_lbl)

        sub_lbl = QLabel(f"جميع المعاملات المؤهلة ({skipped_count}) موجودة بالفعل في هذا القالب.")
        sub_lbl.setObjectName("dialogSubtitle")
        title_vbox.addWidget(sub_lbl)

        header_row.addLayout(title_vbox)
        header_row.addStretch()
        layout.addLayout(header_row)

        card = QFrame()
        card.setObjectName("infoCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(8)

        msg = QLabel(
            "لم يتم إضافة صفوف جديدة إلى الجدول لمنع تكرار القيود.\n"
            "إذا كنت تود إضافة معاملات جديدة، تأكد من اختيار قالب أو كشف حساب مناسب."
        )
        msg.setStyleSheet(f"font-size: 12px; color: {theme.text_primary}; line-height: 140%;")
        c_layout.addWidget(msg)
        layout.addWidget(card)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_open_file = QPushButton("فتح ملف الإكسيل")
        btn_open_file.setObjectName("btnPrimaryNavy")
        btn_open_file.setCursor(Qt.PointingHandCursor)
        btn_open_file.clicked.connect(self._open_file)
        btn_layout.addWidget(btn_open_file)

        btn_open_folder = QPushButton("فتح المجلد")
        btn_open_folder.setObjectName("btnCancelNeutral")
        btn_open_folder.setCursor(Qt.PointingHandCursor)
        btn_open_folder.clicked.connect(self._open_folder)
        btn_layout.addWidget(btn_open_folder)

        btn_layout.addStretch()

        btn_close = QPushButton("إغلاق")
        btn_close.setObjectName("btnCancelNeutral")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _open_file(self):
        if os.path.exists(self.output_path):
            if platform.system() == "Windows":
                os.startfile(self.output_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", self.output_path])
            else:
                subprocess.Popen(["xdg-open", self.output_path])

    def _open_folder(self):
        if os.path.exists(self.output_dir):
            if platform.system() == "Windows":
                os.startfile(self.output_dir)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", self.output_dir])
            else:
                subprocess.Popen(["xdg-open", self.output_dir])
