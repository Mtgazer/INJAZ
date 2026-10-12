"""
Qt Table Models for INJAZ Transaction Review.
Provides high-performance filtering, searching, and color-coded status rendering.
"""
from typing import List, Optional
import unicodedata
import re

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QBrush

from injaz.models import (
    TransactionRecord,
    InclusionEligibility,
    ExtractionStatus,
    DuplicateStatus,
    UserDecision,
)
from injaz.ui.theme import (
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY
)


class TransactionTableModel(QAbstractTableModel):
    """
    QAbstractTableModel displaying transactions with live search and status filtering.
    """
    COL_INDEX = 0
    COL_DATE = 1
    COL_PROJECT = 2
    COL_INVOICE = 3
    COL_SUPPLIER = 4
    COL_TAX = 5
    COL_STATUS = 6

    HEADERS = [
        "#",
        "التاريخ",
        "المشروع",
        "رقم الفاتورة",
        "المورد",
        "الضريبة",
        "الحالة",
    ]

    def __init__(self, records: Optional[List[TransactionRecord]] = None, parent=None):
        super().__init__(parent)
        self._all_records: List[TransactionRecord] = records or []
        self._filtered_records: List[TransactionRecord] = list(self._all_records)
        self._search_query: str = ""
        self._status_filter: str = "ALL"

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._filtered_records)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._filtered_records)):
            return None

        rec = self._filtered_records[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_INDEX:
                return str(rec.record_index)
            elif col == self.COL_DATE:
                return rec.date or "—"
            elif col == self.COL_PROJECT:
                return rec.project or "—"
            elif col == self.COL_INVOICE:
                return str(rec.invoice_number) if rec.invoice_number else "—"
            elif col == self.COL_SUPPLIER:
                return rec.supplier_name or "—"
            elif col == self.COL_TAX:
                return f"{rec.tax_amount:,.2f}" if rec.tax_amount is not None else "—"
            elif col == self.COL_STATUS:
                return self.get_status_text(rec)

        elif role == Qt.TextAlignmentRole:
            if col in (self.COL_INDEX, self.COL_INVOICE, self.COL_TAX, self.COL_STATUS):
                return int(Qt.AlignCenter)
            return int(Qt.AlignRight | Qt.AlignVCenter)

        elif role == Qt.ForegroundRole:
            from injaz.ui.theme import get_current_theme
            theme = get_current_theme()
            if col == self.COL_STATUS:
                return self.get_status_color(rec)
            elif col == self.COL_INDEX:
                return QBrush(QColor(theme.text_secondary))
            else:
                return QBrush(QColor(theme.text_primary))

        return None

    def get_status_text(self, rec: TransactionRecord) -> str:
        """Computes concise Arabic status label based on actual record state."""
        if rec.inclusion_eligibility == InclusionEligibility.EXCLUDED_BY_RULE:
            return "مستبعدة (بقاعدة)"
        if rec.user_decision == UserDecision.EXCLUDED_BY_USER:
            return "مستبعدة (بقرارك)"
        if rec.duplicate_status == DuplicateStatus.POTENTIAL_DUPLICATE and not rec.duplicate_resolved:
            return "تكرار محتمل"
        if rec.requires_field_review and not rec.field_review_resolved:
            return "مراجعة الحقول"
        if rec.requires_inclusion_review and rec.user_decision != UserDecision.INCLUDED_BY_USER:
            return "قرار الإدراج"
        if rec.is_export_eligible:
            return "جاهزة للإدراج"
        return "معلقة"

    def get_status_color(self, rec: TransactionRecord) -> QBrush:
        """Returns semantic text color for status based on active theme."""
        text = self.get_status_text(rec)
        from injaz.ui.theme import get_current_theme
        theme = get_current_theme()
        if "جاهزة" in text:
            return QBrush(QColor(theme.success))
        elif "مستبعدة" in text:
            return QBrush(QColor(theme.error))
        else:
            return QBrush(QColor(theme.warning))


    def get_record(self, row: int) -> Optional[TransactionRecord]:
        if 0 <= row < len(self._filtered_records):
            return self._filtered_records[row]
        return None

    def set_records(self, records: List[TransactionRecord]):
        self.beginResetModel()
        self._all_records = records
        self._apply_filter()
        self.endResetModel()

    def update_record_at(self, row: int):
        """Notifies views that data in the specified filtered row has changed."""
        if 0 <= row < len(self._filtered_records):
            top_left = self.index(row, 0)
            bottom_right = self.index(row, len(self.HEADERS) - 1)
            self.dataChanged.emit(top_left, bottom_right)

    def set_search_query(self, query: str):
        self._search_query = query.strip()
        self.beginResetModel()
        self._apply_filter()
        self.endResetModel()

    def set_status_filter(self, filter_key: str):
        self._status_filter = filter_key
        self.beginResetModel()
        self._apply_filter()
        self.endResetModel()

    def _apply_filter(self):
        """Filters _all_records into _filtered_records without modifying underlying records."""
        q = self._search_query.lower()
        f = self._status_filter

        results = []
        for r in self._all_records:
            # 1. Status Filter Check
            status_text = self.get_status_text(r)
            if f == "READY" and status_text != "جاهزة للإدراج":
                continue
            elif f == "REVIEW" and status_text not in ("مراجعة الحقول", "قرار الإدراج"):
                continue
            elif f == "DUPLICATE" and status_text != "تكرار محتمل":
                continue
            elif f == "EXCLUDED" and not status_text.startswith("مستبعدة"):
                continue

            # 2. Text Search Check
            if q:
                match = (
                    q in str(r.record_index)
                    or q in (r.date or "").lower()
                    or q in (r.project or "").lower()
                    or q in str(r.invoice_number or "").lower()
                    or q in (r.supplier_name or "").lower()
                    or q in (r.raw_description or "").lower()
                )
                if not match:
                    continue

            results.append(r)

        self._filtered_records = results
