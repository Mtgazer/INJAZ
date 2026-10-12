"""
Screen C: Export (تصدير الملف إلى Excel).
Displays audit readiness breakdown, template & destination verification,
and executes safe Phase 3 population engine with post-export success actions.
"""
import os
import subprocess
import platform

from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QMessageBox, QProgressBar, QDialog, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from injaz.models import (
    TransactionRecord,
    InclusionEligibility,
    UserDecision,
    DuplicateStatus,
)
from injaz.excel_writer import ExportSummary
from injaz.ui.components.dialogs import (
    ExportConfirmDialog, ExportSuccessDialog, ExportSkippedDialog
)
from injaz.ui.theme import (
    COLOR_NAVY, COLOR_TEAL, COLOR_BORDER, COLOR_SURFACE, COLOR_BG, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    ThemeManager, get_theme
)



class AuditStatRow(QFrame):
    """Row displaying metric with badge and status icon."""
    def __init__(self, label: str, count: int, color_hex: str, icon_str: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        lbl_icon = QLabel(icon_str)
        lbl_icon.setStyleSheet(f"font-size: 16px; color: {color_hex};")
        layout.addWidget(lbl_icon)

        self.lbl_text = QLabel(label)
        self.lbl_text.setStyleSheet(f"font-size: 13px; color: {COLOR_NAVY};")
        layout.addWidget(self.lbl_text, stretch=1)

        self.lbl_count = QLabel(str(count))
        self.lbl_count.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {color_hex};")
        layout.addWidget(self.lbl_count)

    def set_count(self, count: int):
        self.lbl_count.setText(str(count))

    def set_theme(self, theme_name: str):
        theme = get_theme(theme_name)
        if hasattr(self, "lbl_text"):
            self.lbl_text.setStyleSheet(f"font-size: 13px; color: {theme.text_primary};")


class ExportPage(QWidget):
    """
    Screen C: Export page enforcing audit readiness before invoking Phase 3 Excel writer
    or reliable CSV export fallback.
    """
    back_to_review_requested = Signal()
    export_started = Signal(str, str, list)      # template_path, output_path, records
    csv_export_started = Signal(str, list)       # output_path, records
    new_process_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("exportPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.theme_name = ThemeManager.instance().current_theme
        self.records: List[TransactionRecord] = []
        self.template_path: str = ""
        self.output_path: str = ""

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 25, 40, 25)
        main_layout.setSpacing(20)

        # 1. Header
        header_vbox = QVBoxLayout()
        header_vbox.setSpacing(4)
        
        title_lbl = QLabel("تصدير إلى Excel")
        title_lbl.setObjectName("pageTitle")
        header_vbox.addWidget(title_lbl)

        subtitle_lbl = QLabel("تحقق من الجاهزية والاعتماد قبل كتابة المخرجات.")
        subtitle_lbl.setObjectName("pageSubtitle")
        header_vbox.addWidget(subtitle_lbl)

        main_layout.addLayout(header_vbox)

        # 2. Audit Readiness Summary Card
        self.audit_card = QFrame()
        self.audit_card.setObjectName("cardFrame")
        audit_layout = QVBoxLayout(self.audit_card)
        audit_layout.setContentsMargins(20, 16, 20, 16)
        audit_layout.setSpacing(8)

        lbl_card_title = QLabel("ملخص الجاهزية والأمان المالي للمعاملات:")
        lbl_card_title.setObjectName("sectionTitle")
        audit_layout.addWidget(lbl_card_title)

        self.row_eligible = AuditStatRow("معاملات معتمدة وجاهزة للتصدير", 0, COLOR_SUCCESS, "✅")
        self.row_field_rev = AuditStatRow("معاملات بانتظار تأكيد مراجعة الحقول (محجوبة)", 0, COLOR_WARNING, "⚠️")
        self.row_inc_dec = AuditStatRow("معاملات بانتظار قرار الإدراج التجاري (محجوبة)", 0, COLOR_WARNING, "⚠️")
        self.row_dup = AuditStatRow("معاملات معلقة بسبب تحذير تكرار غير محلول (محجوبة)", 0, COLOR_WARNING, "⚠️")
        self.row_excluded = AuditStatRow("معاملات مستبعدة بقاعدة أو بقرار صريح (لن تُصدر)", 0, COLOR_ERROR, "🚫")

        audit_layout.addWidget(self.row_eligible)
        audit_layout.addWidget(self.row_field_rev)
        audit_layout.addWidget(self.row_inc_dec)
        audit_layout.addWidget(self.row_dup)
        audit_layout.addWidget(self.row_excluded)

        main_layout.addWidget(self.audit_card)

        # 3. Target File Information Card
        self.target_card = QFrame()
        self.target_card.setObjectName("cardFrame")
        target_layout = QVBoxLayout(self.target_card)
        target_layout.setContentsMargins(20, 16, 20, 16)
        target_layout.setSpacing(10)

        lbl_target_title = QLabel("مسار مصنف المخرجات:")
        lbl_target_title.setObjectName("sectionTitle")
        target_layout.addWidget(lbl_target_title)

        # Output info
        o_row = QHBoxLayout()
        o_row.addWidget(QLabel("مسار حفظ مصنف Excel الجديد:"))
        self.lbl_output_path = QLabel("—")
        self.lbl_output_path.setStyleSheet(f"font-weight: bold; color: {COLOR_TEAL};")
        o_row.addWidget(self.lbl_output_path, stretch=1)
        target_layout.addLayout(o_row)

        self.lbl_template_path = QLabel("")  # backwards-compatible reference
        self.lbl_template_path.setVisible(False)

        main_layout.addWidget(self.target_card)

        # 4. Progress / Loading state
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("cardFrame")
        self.progress_frame.setStyleSheet(f"background-color: #E6F4F1; border: 1px solid {COLOR_TEAL};")
        self.progress_frame.setVisible(False)
        prog_vbox = QVBoxLayout(self.progress_frame)
        prog_vbox.setContentsMargins(16, 12, 16, 12)
        prog_vbox.setSpacing(6)
        
        self.lbl_export_status = QLabel("جاري تصدير المعاملات المعتمدة والتحقق من سلامة المعادلات...")
        self.lbl_export_status.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {COLOR_NAVY};")
        prog_vbox.addWidget(self.lbl_export_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setFixedHeight(6)
        prog_vbox.addWidget(self.progress_bar)
        main_layout.addWidget(self.progress_frame)

        main_layout.addStretch()

        # 5. Bottom Navigation & Action Bar
        nav_layout = QHBoxLayout()

        btn_back = QPushButton("← العودة إلى المراجعة")
        btn_back.setObjectName("secondaryButton")
        btn_back.clicked.connect(self.back_to_review_requested.emit)
        nav_layout.addWidget(btn_back)

        nav_layout.addStretch()

        self.btn_export_csv = QPushButton("تصدير CSV كبديل")
        self.btn_export_csv.setObjectName("secondaryButton")
        self.btn_export_csv.setFixedHeight(44)
        self.btn_export_csv.setMinimumWidth(180)
        self.btn_export_csv.setCursor(Qt.PointingHandCursor)
        self.btn_export_csv.clicked.connect(self._on_export_csv_clicked)
        nav_layout.addWidget(self.btn_export_csv)

        self.btn_export = QPushButton("تصدير إلى Excel")
        self.btn_export.setObjectName("primaryButton")
        self.btn_export.setFixedHeight(44)
        self.btn_export.setMinimumWidth(220)
        self.btn_export.clicked.connect(self._on_export_clicked)
        nav_layout.addWidget(self.btn_export)

        main_layout.addLayout(nav_layout)

        self.set_theme(self.theme_name)

    def set_theme(self, theme_name: str):
        """Updates ExportPage cards, rows, and status indicators to active theme."""
        self.theme_name = theme_name
        theme = get_theme(theme_name)
        self.setStyleSheet(f"#exportPage {{ background-color: {theme.bg}; }}")
        for row in (self.row_eligible, self.row_field_rev, self.row_inc_dec, self.row_dup, self.row_excluded):
            if hasattr(row, "set_theme"):
                row.set_theme(theme_name)
        if hasattr(self, "lbl_output_path"):
            self.lbl_output_path.setStyleSheet(f"font-weight: bold; color: {theme.teal};")
        if hasattr(self, "progress_frame"):
            if theme_name == "dark":
                self.progress_frame.setStyleSheet(f"background-color: {theme.teal_bg}; border: 1px solid {theme.teal};")
            else:
                self.progress_frame.setStyleSheet(f"background-color: #E6F4F1; border: 1px solid {theme.teal};")
        if hasattr(self, "lbl_export_status"):
            self.lbl_export_status.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {theme.text_primary};")

    def set_data(self, records: List[TransactionRecord], arg1: str, arg2: Optional[str] = None):
        """Refreshes export screen with current review state and paths."""
        self.records = records
        if arg2 is not None:
            # Legacy signature: set_data(records, template_path, output_path)
            self.template_path = arg1
            self.output_path = arg2
            self.lbl_template_path.setText(arg1)
        else:
            # New signature: set_data(records, output_path)
            self.output_path = arg1
            self.template_path = ""
            self.lbl_template_path.setText("")

        self.lbl_output_path.setText(self.output_path)

        # Recompute strict audit breakdown
        eligible_cnt = sum(1 for r in records if r.is_export_eligible)
        field_rev_cnt = sum(1 for r in records if r.requires_field_review and not r.field_review_resolved)
        inc_dec_cnt = sum(1 for r in records if r.requires_inclusion_review and r.user_decision != UserDecision.INCLUDED_BY_USER)
        dup_cnt = sum(1 for r in records if r.duplicate_status == DuplicateStatus.POTENTIAL_DUPLICATE and not r.duplicate_resolved)
        excluded_cnt = sum(
            1 for r in records
            if r.inclusion_eligibility == InclusionEligibility.EXCLUDED_BY_RULE
            or r.user_decision == UserDecision.EXCLUDED_BY_USER
        )

        self.row_eligible.set_count(eligible_cnt)
        self.row_field_rev.set_count(field_rev_cnt)
        self.row_inc_dec.set_count(inc_dec_cnt)
        self.row_dup.set_count(dup_cnt)
        self.row_excluded.set_count(excluded_cnt)

        # Enable export actions only if at least 1 record is eligible
        self.btn_export.setEnabled(eligible_cnt > 0)
        self.btn_export_csv.setEnabled(eligible_cnt > 0)

    def _on_export_clicked(self):
        eligible_cnt = sum(1 for r in self.records if r.is_export_eligible)
        if eligible_cnt == 0:
            QMessageBox.warning(
                self,
                "لا توجد معاملات مؤهلة",
                "لا توجد أي معاملات معتمدة ومؤهلة للتصدير حالياً.\n"
                "يرجى مراجعة المعاملات واعتمادها أولاً."
            )
            return

        # Explicit accessible light-themed confirmation dialog
        dlg = ExportConfirmDialog(
            eligible_count=eligible_cnt,
            output_path=self.output_path,
            template_path=self.template_path,
            parent=self
        )
        if dlg.exec() != QDialog.Accepted:
            return

        self.btn_export.setEnabled(False)
        self.btn_export_csv.setEnabled(False)
        self.progress_frame.setVisible(True)
        self.lbl_export_status.setText("جاري إنشاء مصنف Excel الجديد والتحقق من سلامة البيانات...")
        self.export_started.emit(self.template_path, self.output_path, self.records)

    def _on_export_csv_clicked(self):
        eligible_cnt = sum(1 for r in self.records if r.is_export_eligible)
        if eligible_cnt == 0:
            QMessageBox.warning(
                self,
                "لا توجد معاملات مؤهلة",
                "لا توجد أي معاملات معتمدة ومؤهلة للتصدير حالياً.\n"
                "يرجى مراجعة المعاملات واعتمادها أولاً."
            )
            return

        # Prepare default CSV path based on current output path
        default_csv = ""
        if self.output_path:
            base, _ = os.path.splitext(self.output_path)
            default_csv = base + ".csv"

        csv_path, _ = QFileDialog.getSaveFileName(
            self,
            "تحديد مسار حفظ ملف CSV البديل",
            default_csv,
            "ملفات CSV (*.csv)"
        )
        if not csv_path:
            return

        if not csv_path.lower().endswith(".csv"):
            csv_path += ".csv"

        # Explicit confirmation for CSV data-only export
        reply = QMessageBox.question(
            self,
            "تأكيد تصدير ملف CSV البديل",
            f"سيتم تصدير {eligible_cnt} معاملة معتمدة إلى ملف CSV بصيغة UTF-8 مع BOM متوافقة مع Excel.\n\n"
            f"المسار المستهدف:\n{csv_path}\n\n"
            "تنبيه: تصدير CSV هو بديل مباشر للبيانات فقط، ولا يتضمن صيغ القالب وتنسيقات الجداول.\n\n"
            "هل ترغب في المتابعة؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_export.setEnabled(False)
        self.btn_export_csv.setEnabled(False)
        self.progress_frame.setVisible(True)
        self.lbl_export_status.setText("جاري تصدير ملف CSV البديل والتحقق من سلامة البيانات...")
        self.csv_export_started.emit(csv_path, self.records)

    def handle_export_success(self, summary: ExportSummary):
        """Displays completion dialog with direct buttons to open file and containing folder."""
        self.progress_frame.setVisible(False)
        self.btn_export.setEnabled(True)
        self.btn_export_csv.setEnabled(True)

        if summary.records_exported == 0:
            skipped_cnt = getattr(summary, "records_skipped_already_present", 0)
            if skipped_cnt > 0:
                # Informative dialog when all submitted records are already in workbook
                dlg = ExportSkippedDialog(
                    output_path=summary.output_path,
                    skipped_count=skipped_cnt,
                    parent=self
                )
                dlg.exec()
                return
            else:
                QMessageBox.warning(
                    self,
                    "لم يتم تصدير أي معاملة",
                    "لم يتم تصدير أي معاملة إلى ملف الإكسيل لعدم استيفاء السجلات لشروط الأمان المالي والاعتماد."
                )
                return

        # Success dialog with direct file & folder open buttons
        dlg = ExportSuccessDialog(
            output_path=summary.output_path,
            records_exported=summary.records_exported,
            records_skipped=getattr(summary, "records_skipped_already_present", 0),
            parent=self
        )
        dlg.new_process_clicked.connect(self.new_process_requested.emit)
        dlg.exec()

    def handle_csv_export_success(self, summary):
        """Displays completion dialog for CSV export fallback."""
        self.progress_frame.setVisible(False)
        self.btn_export.setEnabled(True)
        self.btn_export_csv.setEnabled(True)

        if summary.records_exported == 0:
            QMessageBox.warning(
                self,
                "لم يتم تصدير أي معاملة",
                "لم يتم تصدير أي معاملة إلى ملف CSV لعدم وجود سجلات معتمدة ومؤهلة."
            )
            return

        dlg = ExportSuccessDialog(
            output_path=summary.output_path,
            records_exported=summary.records_exported,
            records_skipped=0,
            parent=self
        )
        dlg.new_process_clicked.connect(self.new_process_requested.emit)
        dlg.exec()

    def handle_export_failure(self, error_msg: str):
        self.progress_frame.setVisible(False)
        self.btn_export.setEnabled(True)
        self.btn_export_csv.setEnabled(True)
        QMessageBox.critical(self, "فشل التصدير", f"تعذر إتمام عملية التصدير:\n\n{error_msg}")

