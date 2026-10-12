"""
Supplier Grouping & Bulk Editing Dialogs for INJAZ (إنجاز).
Provides interactive review of clustered supplier variants,
selective transaction checkbox updates, canonical name editing,
and audit-safe bulk application.
"""
from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QCheckBox,
    QMessageBox, QWidget, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from injaz.models import TransactionRecord
from injaz.supplier_matcher import SupplierGroupSuggestion, SupplierVariant
from injaz.ui.components.dialogs import BaseInjazDialog
from injaz.ui.theme import (
    COLOR_NAVY, COLOR_NAVY_HOVER, COLOR_TEAL, COLOR_TEAL_HOVER,
    COLOR_BG, COLOR_SURFACE, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_BORDER, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    get_theme
)


class SupplierGroupingDialog(BaseInjazDialog):
    """
    Displays the manageable table of suggested supplier groups.
    User can view affected record counts, variant counts, reason, and launch group review.
    """
    review_group_requested = Signal(object)  # SupplierGroupSuggestion

    def __init__(self, groups: List[SupplierGroupSuggestion], parent=None):
        super().__init__("تجميع الموردين المتشابهين", parent)
        self.groups = groups
        self.setMinimumWidth(820)
        self.setMinimumHeight(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Header
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_lbl = QLabel("🏢")
        icon_lbl.setStyleSheet(f"font-size: 26px; color: {COLOR_TEAL};")
        header_row.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        title_lbl = QLabel("تجميع الموردين المتشابهين ومراجعة الأسماء")
        title_lbl.setObjectName("dialogTitle")
        title_vbox.addWidget(title_lbl)

        sub_lbl = QLabel(
            f"تم العثور على {len(groups)} مجموعة مقترحة للتصحيح الجماعي السريع بناءً على مسافات الخط والفروق الإملائية."
        )
        sub_lbl.setObjectName("dialogSubtitle")
        title_vbox.addWidget(sub_lbl)

        header_row.addLayout(title_vbox)
        header_row.addStretch()
        layout.addLayout(header_row)

        # 2. Table of groups
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "اسم المورد المقترح",
            "المعاملات المتأثرة",
            "عدد المتغيرات",
            "سبب التجميع والملاحظات",
            "الإجراء"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self._populate_table()
        layout.addWidget(self.table)

        # 3. Footer
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        btn_close = QPushButton("إغلاق")
        btn_close.setObjectName("btnCancelNeutral")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(btn_close)

        layout.addLayout(footer_layout)

    def _populate_table(self):
        self.table.setRowCount(len(self.groups))
        for row_idx, grp in enumerate(self.groups):
            # Col 0: Label
            item_lbl = QTableWidgetItem(grp.suggested_label)
            item_lbl.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row_idx, 0, item_lbl)

            # Col 1: Record count
            item_cnt = QTableWidgetItem(f"{grp.total_records} معاملة")
            item_cnt.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 1, item_cnt)

            # Col 2: Variants count
            item_vars = QTableWidgetItem(f"{len(grp.variants)} متغير")
            item_vars.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, item_vars)

            # Col 3: Reason
            item_reason = QTableWidgetItem(grp.reason_ar)
            item_reason.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row_idx, 3, item_reason)

            # Col 4: Action button
            theme = get_theme()
            btn_review = QPushButton("مراجعة وتعديل ←")
            btn_review.setObjectName("btnPrimaryConfirm")
            btn_review.setCursor(Qt.PointingHandCursor)
            btn_review.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.teal};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {theme.teal_hover};
                }}
            """)
            btn_review.clicked.connect(lambda _, g=grp: self._on_review_clicked(g))
            self.table.setCellWidget(row_idx, 4, btn_review)

    def _on_review_clicked(self, group: SupplierGroupSuggestion):
        self.review_group_requested.emit(group)


class BulkSupplierEditDialog(BaseInjazDialog):
    """
    Dialog for reviewing and bulk-editing supplier names within a single group:
    - Editable canonical supplier name field
    - Checkbox to select all / individual records
    - Summary label dynamically updated: 'سيتم تعديل اسم المورد في X معاملة'
    - Primary action: 'تطبيق على المحدد'
    - Cancel action
    - Explicit confirmation dialog before applying
    """
    applied = Signal(object, str, list)  # group, canonical_name, selected_records

    def __init__(self, group: SupplierGroupSuggestion, parent=None):
        super().__init__(f"تعديل مجموعة: {group.suggested_label}", parent)
        self.group = group
        self.records = group.records
        self.setMinimumWidth(880)
        self.setMinimumHeight(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        theme = get_theme()

        # 1. Header
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        icon_lbl = QLabel("✏️")
        icon_lbl.setStyleSheet(f"font-size: 24px; color: {theme.teal};")
        header_row.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        title_lbl = QLabel(f"مراجعة وتصحيح اسم المورد ({group.total_records} معاملة)")
        title_lbl.setObjectName("dialogTitle")
        title_vbox.addWidget(title_lbl)

        sub_lbl = QLabel("حدد المعاملات المراد تحديثها واعتمد الاسم القانوني الموحد للمورد.")
        sub_lbl.setObjectName("dialogSubtitle")
        title_vbox.addWidget(sub_lbl)

        header_row.addLayout(title_vbox)
        header_row.addStretch()
        layout.addLayout(header_row)

        # 2. Canonical Name Edit Box
        name_card = QFrame()
        name_card.setObjectName("infoCard")
        name_layout = QHBoxLayout(name_card)
        name_layout.setContentsMargins(14, 10, 14, 10)
        name_layout.setSpacing(12)

        lbl_input_tag = QLabel("الاسم المعتمد للمورد:")
        lbl_input_tag.setStyleSheet(f"font-weight: 700; color: {theme.text_primary}; font-size: 13px;")
        name_layout.addWidget(lbl_input_tag)

        self.edit_canonical = QLineEdit(group.canonical_candidate)
        self.edit_canonical.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.surface};
                border: 1px solid {theme.teal};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                font-weight: 600;
                color: {theme.text_primary};
            }}
        """)
        self.edit_canonical.textChanged.connect(self._update_summary)
        name_layout.addWidget(self.edit_canonical, stretch=1)

        layout.addWidget(name_card)

        # 3. Selection & Filter Bar
        sel_bar = QHBoxLayout()
        sel_bar.setSpacing(12)

        self.chk_select_all = QCheckBox("تحديد كافة المعاملات")
        self.chk_select_all.setChecked(True)
        self.chk_select_all.setStyleSheet(f"font-weight: 700; color: {theme.text_primary}; font-size: 12px;")
        self.chk_select_all.stateChanged.connect(self._on_select_all_changed)
        sel_bar.addWidget(self.chk_select_all)

        sel_bar.addStretch()

        self.lbl_summary = QLabel(f"سيتم تعديل اسم المورد في {len(self.records)} معاملة")
        self.lbl_summary.setStyleSheet(f"font-weight: 700; color: {theme.teal}; font-size: 13px;")
        sel_bar.addWidget(self.lbl_summary)

        layout.addLayout(sel_bar)

        # 4. Table of Records
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "تحديد",
            "المعاملة #",
            "الاسم المستخرج الحالي",
            "التاريخ",
            "المشروع",
            "رقم الفاتورة",
            "الضريبة"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)

        self.row_checkboxes: List[QCheckBox] = []
        self._populate_table()
        layout.addWidget(self.table)

        # 5. Bottom Actions
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_cancel = QPushButton("إلغاء")
        btn_cancel.setObjectName("btnCancelNeutral")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_layout.addStretch()

        self.btn_apply = QPushButton("تطبيق على المحدد")
        self.btn_apply.setObjectName("btnPrimaryConfirm")
        self.btn_apply.setCursor(Qt.PointingHandCursor)
        self.btn_apply.setFixedHeight(36)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        btn_layout.addWidget(self.btn_apply)

        layout.addLayout(btn_layout)

    def _populate_table(self):
        self.table.setRowCount(len(self.records))
        self.row_checkboxes = []

        for row_idx, rec in enumerate(self.records):
            # Checkbox
            chk = QCheckBox()
            chk.setChecked(True)
            chk.stateChanged.connect(self._on_row_chk_changed)
            chk_widget = QWidget()
            chk_l = QHBoxLayout(chk_widget)
            chk_l.setContentsMargins(4, 0, 4, 0)
            chk_l.setAlignment(Qt.AlignCenter)
            chk_l.addWidget(chk)
            self.table.setCellWidget(row_idx, 0, chk_widget)
            self.row_checkboxes.append(chk)

            # Col 1: Record index
            item_idx = QTableWidgetItem(f"#{rec.record_index}")
            item_idx.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 1, item_idx)

            # Col 2: Current supplier
            item_supp = QTableWidgetItem(rec.supplier_name or "")
            item_supp.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row_idx, 2, item_supp)

            # Col 3: Date
            item_date = QTableWidgetItem(str(rec.date or ""))
            item_date.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 3, item_date)

            # Col 4: Project
            item_proj = QTableWidgetItem(rec.project or "")
            item_proj.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 4, item_proj)

            # Col 5: Invoice
            item_inv = QTableWidgetItem(str(rec.invoice_number or ""))
            item_inv.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 5, item_inv)

            # Col 6: Tax
            tax_str = f"{rec.tax_amount:.2f}" if rec.tax_amount is not None else "0.00"
            item_tax = QTableWidgetItem(tax_str)
            item_tax.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 6, item_tax)

    def _on_select_all_changed(self, state: int):
        is_checked = (state == Qt.Checked)
        for chk in self.row_checkboxes:
            chk.blockSignals(True)
            chk.setChecked(is_checked)
            chk.blockSignals(False)
        self._update_summary()

    def _on_row_chk_changed(self):
        checked_cnt = sum(1 for chk in self.row_checkboxes if chk.isChecked())
        self.chk_select_all.blockSignals(True)
        self.chk_select_all.setChecked(checked_cnt == len(self.row_checkboxes))
        self.chk_select_all.blockSignals(False)
        self._update_summary()

    def _update_summary(self):
        checked_cnt = sum(1 for chk in self.row_checkboxes if chk.isChecked())
        canonical_name = self.edit_canonical.text().strip()
        self.lbl_summary.setText(f"سيتم تعديل اسم المورد في {checked_cnt} معاملة")
        self.btn_apply.setEnabled(checked_cnt > 0 and bool(canonical_name))

    def _on_apply_clicked(self):
        canonical_name = self.edit_canonical.text().strip()
        if not canonical_name:
            QMessageBox.warning(self, "اسم المورد مطلوب", "يرجى كتابة الاسم المعتمد للمورد.")
            return

        selected_records = [
            self.records[i]
            for i, chk in enumerate(self.row_checkboxes)
            if chk.isChecked()
        ]
        if not selected_records:
            QMessageBox.warning(self, "لا توجد معاملات محددة", "يرجى تحديد معاملة واحدة على الأقل للتعديل.")
            return

        # Confirm before applying
        reply = QMessageBox.question(
            self,
            "تأكيد التعديل الجماعي",
            f"هل أنت متأكد من اعتماد وتطبيق اسم المورد:\n'{canonical_name}'\n\nعلى {len(selected_records)} معاملة محددة؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        self.applied.emit(self.group, canonical_name, selected_records)
        self.accept()
