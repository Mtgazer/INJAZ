"""
Screen B: Transaction Review (مراجعة المعاملات).
Displays the transaction table, real-time counters, search/filter controls,
editable details panel, field review resolution, commercial inclusion decisions,
and potential duplicate side-by-side comparison.
"""
from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTableView, QFrame, QScrollArea, QMessageBox, QHeaderView,
    QGridLayout, QSizePolicy, QDialog
)
from PySide6.QtCore import Qt, Signal, QModelIndex
from PySide6.QtGui import QColor

from injaz.models import (
    TransactionRecord,
    InclusionEligibility,
    UserDecision,
    DuplicateStatus,
    ExtractionStatus,
)
from injaz.supplier_matcher import group_similar_suppliers, SupplierGroupSuggestion
from injaz.ui.components.supplier_dialogs import SupplierGroupingDialog, BulkSupplierEditDialog
from injaz.ui.models import TransactionTableModel
from injaz.ui.theme import (
    COLOR_NAVY, COLOR_TEAL, COLOR_BORDER, COLOR_SURFACE, COLOR_BG, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY, COLOR_WARNING, COLOR_WARNING_BG, COLOR_ERROR,
    COLOR_ERROR_BG, COLOR_SUCCESS, COLOR_SUCCESS_BG,
    ThemeManager, get_theme, get_current_theme, style_combo_box
)



class StatusBadgeCard(QFrame):
    """Small status indicator widget above the table."""
    def __init__(
        self,
        title: str,
        count: int = 0,
        color_hex: Optional[str] = None,
        bg_hex: Optional[str] = None,
        parent=None,
        key: Optional[str] = None
    ):
        super().__init__(parent)
        if key is not None:
            self.key = key
        elif "جاهزة" in title:
            self.key = "ready"
        elif "تحتاج" in title:
            self.key = "review"
        elif "مستبعدة" in title:
            self.key = "excluded"
        else:
            self.key = "duplicate"

        self.title_text = title
        self.count_val = count

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.lbl_title = QLabel(title)
        layout.addWidget(self.lbl_title)

        self.lbl_count = QLabel(str(count))
        layout.addWidget(self.lbl_count)

        self.set_theme(ThemeManager.instance().current_theme)

    def set_count(self, count: int):
        self.count_val = count
        self.lbl_count.setText(str(count))

    def set_theme(self, theme_name: str):
        theme = get_theme(theme_name)
        if self.key == "ready":
            color = theme.success
            bg = theme.success_bg
            border = theme.success_border
        elif self.key == "review":
            color = theme.warning
            bg = theme.warning_bg
            border = theme.warning_border
        elif self.key == "excluded":
            color = theme.error
            bg = theme.error_bg
            border = theme.error_border
        else:  # duplicate
            color = theme.duplicate
            bg = theme.duplicate_bg
            border = theme.duplicate_border

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 12px;
            }}
        """)
        self.lbl_title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.text_primary}; border: none; background: transparent;")
        self.lbl_count.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {color}; border: none; background: transparent;")


class ReviewPage(QWidget):
    """
    Screen B: Central hub for reviewing, correcting, and deciding on extracted transactions.
    """
    proceed_to_export_requested = Signal()
    back_to_files_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("reviewPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.theme_name = ThemeManager.instance().current_theme
        self.records: List[TransactionRecord] = []
        self.selected_record: Optional[TransactionRecord] = None
        self.selected_row_idx: int = -1
        self.last_bulk_edit: Optional[Dict[str, Any]] = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(12)

        # 1. Top Status Counters Row
        counters_layout = QHBoxLayout()
        counters_layout.setSpacing(10)

        self.badge_ready = StatusBadgeCard("جاهزة للإدراج", 0, key="ready", parent=self)
        self.badge_review = StatusBadgeCard("تحتاج مراجعة", 0, key="review", parent=self)
        self.badge_excluded = StatusBadgeCard("مستبعدة", 0, key="excluded", parent=self)
        self.badge_duplicate = StatusBadgeCard("تكرار محتمل", 0, key="duplicate", parent=self)

        counters_layout.addWidget(self.badge_ready)
        counters_layout.addWidget(self.badge_review)
        counters_layout.addWidget(self.badge_excluded)
        counters_layout.addWidget(self.badge_duplicate)
        counters_layout.addStretch()

        main_layout.addLayout(counters_layout)

        # 2. Filter & Search Controls Bar
        filter_bar = QFrame()
        filter_bar.setObjectName("cardFrame")
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(12, 8, 12, 8)
        filter_layout.setSpacing(10)

        # Search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("بحث برقم الفاتورة، المورد، المشروع، أو البيان...")
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_input, stretch=2)

        # Status filter dropdown
        self.lbl_filter = QLabel("تصفية:")
        self.lbl_filter.setObjectName("fieldLabel")
        filter_layout.addWidget(self.lbl_filter)

        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("filterDropdown")
        self.filter_combo.addItem("عرض الكل", "ALL")
        self.filter_combo.addItem("جاهزة للإدراج فقط", "READY")
        self.filter_combo.addItem("تحتاج مراجعة (حقول أو قرار)", "REVIEW")
        self.filter_combo.addItem("تكرار محتمل فقط", "DUPLICATE")
        self.filter_combo.addItem("مستبعدة", "EXCLUDED")
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        style_combo_box(self.filter_combo, self.theme_name)
        filter_layout.addWidget(self.filter_combo, stretch=1)

        # Clear filters button
        btn_reset = QPushButton("إعادة تعيين")
        btn_reset.setObjectName("secondaryButton")
        btn_reset.clicked.connect(self._reset_filters)
        filter_layout.addWidget(btn_reset)

        # Supplier Grouping Button
        self.btn_group_suppliers = QPushButton("تجميع الموردين المتشابهين")
        self.btn_group_suppliers.setObjectName("secondaryButton")
        self.btn_group_suppliers.setCursor(Qt.PointingHandCursor)
        self.btn_group_suppliers.setStyleSheet(f"""
            QPushButton {{
                background-color: #E6F4F1;
                color: {COLOR_TEAL};
                border: 1px solid {COLOR_TEAL};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLOR_TEAL};
                color: #FFFFFF;
            }}
        """)
        self.btn_group_suppliers.clicked.connect(self._on_group_suppliers_clicked)
        filter_layout.addWidget(self.btn_group_suppliers)

        # Undo Bulk Edit Button
        self.btn_undo_bulk = QPushButton("تراجع عن التعديل الأخير")
        self.btn_undo_bulk.setObjectName("secondaryButton")
        self.btn_undo_bulk.setCursor(Qt.PointingHandCursor)
        self.btn_undo_bulk.setVisible(False)
        self.btn_undo_bulk.setEnabled(False)
        self.btn_undo_bulk.setStyleSheet("""
            QPushButton {
                background-color: #FEF3C7;
                color: #92400E;
                border: 1px solid #F59E0B;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #FDE68A;
            }
        """)
        self.btn_undo_bulk.clicked.connect(self._on_undo_bulk_clicked)
        filter_layout.addWidget(self.btn_undo_bulk)

        # Record count indicator
        self.lbl_count_info = QLabel("المعاملات: 0")
        self.lbl_count_info.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLOR_NAVY};")
        filter_layout.addWidget(self.lbl_count_info)

        main_layout.addWidget(filter_bar)

        # 3. Main Split View: Table (Left/Center) + Detail Panel (Right)
        split_layout = QHBoxLayout()
        split_layout.setSpacing(15)

        # Table View
        self.table_view = QTableView()
        self.table_model = TransactionTableModel()
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.selectionModel().selectionChanged.connect(self._on_row_selected)
        self.table_view.clicked.connect(lambda index: self.select_record_by_index(index.row()))
        split_layout.addWidget(self.table_view, stretch=3)

        # Detail Panel (Scrollable card on the right)
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFixedWidth(380)
        self.detail_scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: transparent; }}")

        self.detail_card = QFrame()
        self.detail_card.setObjectName("cardFrame")
        self.detail_layout = QVBoxLayout(self.detail_card)
        self.detail_layout.setContentsMargins(16, 16, 16, 16)
        self.detail_layout.setSpacing(12)

        self._build_detail_panel()
        self.detail_scroll.setWidget(self.detail_card)
        split_layout.addWidget(self.detail_scroll, stretch=1)

        main_layout.addLayout(split_layout, stretch=1)

        # 4. Bottom Navigation Footer
        footer_layout = QHBoxLayout()
        
        btn_back = QPushButton("← رجوع إلى الملفات")
        btn_back.setObjectName("secondaryButton")
        btn_back.clicked.connect(self.back_to_files_requested.emit)
        footer_layout.addWidget(btn_back)

        footer_layout.addStretch()

        self.btn_proceed = QPushButton("المتابعة إلى التصدير ←")
        self.btn_proceed.setObjectName("primaryButton")
        self.btn_proceed.setFixedHeight(38)
        self.btn_proceed.clicked.connect(self.proceed_to_export_requested.emit)
        footer_layout.addWidget(self.btn_proceed)

        main_layout.addLayout(footer_layout)

        # Apply initial theme
        self.set_theme(self.theme_name)

    def set_theme(self, theme_name: str):
        """Updates all ReviewPage sub-components, badges, buttons, and detail alerts to the active theme."""
        self.theme_name = theme_name
        theme = get_theme(theme_name)

        # 1. Update badges
        self.badge_ready.set_theme(theme_name)
        self.badge_review.set_theme(theme_name)
        self.badge_excluded.set_theme(theme_name)
        self.badge_duplicate.set_theme(theme_name)

        # 2. Update filter combo delegate and palette
        style_combo_box(self.filter_combo, theme_name)

        # 3. Indicator label
        self.lbl_count_info.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.text_secondary};")

        # 4. Supplier buttons
        if theme_name == "dark":
            self.btn_group_suppliers.setStyleSheet(f"""
                QPushButton {{
                    background-color: #17333B;
                    color: {theme.teal};
                    border: 1px solid {theme.teal};
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {theme.teal};
                    color: #111827;
                }}
            """)
            self.btn_undo_bulk.setStyleSheet(f"""
                QPushButton {{
                    background-color: #382613;
                    color: {theme.warning};
                    border: 1px solid {theme.warning};
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: #4D351A;
                }}
            """)
        else:
            self.btn_group_suppliers.setStyleSheet(f"""
                QPushButton {{
                    background-color: #E6F4F1;
                    color: {theme.teal};
                    border: 1px solid {theme.teal};
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {theme.teal};
                    color: #FFFFFF;
                }}
            """)
            self.btn_undo_bulk.setStyleSheet("""
                QPushButton {
                    background-color: #FEF3C7;
                    color: #92400E;
                    border: 1px solid #F59E0B;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #FDE68A;
                }
            """)

        # 5. Detail panel labels & containers
        if hasattr(self, "lbl_meta_info"):
            self.lbl_meta_info.setStyleSheet(f"font-size: 11px; color: {theme.text_secondary};")

        if hasattr(self, "reasons_box"):
            self.reasons_box.setStyleSheet(
                f"background-color: {theme.warning_bg}; border: 1px solid {theme.warning_border}; border-radius: 6px; padding: 6px;"
            )
            self.lbl_reasons_title.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {theme.warning};")
            self.lbl_reasons_text.setStyleSheet(f"font-size: 11px; color: {theme.text_primary};")

        if hasattr(self, "lbl_raw_desc"):
            self.lbl_raw_desc.setStyleSheet(
                f"background-color: {theme.bg_secondary}; border: 1px solid {theme.border}; border-radius: 4px; padding: 6px; font-size: 11px; color: {theme.text_primary};"
            )

        if hasattr(self, "dup_box"):
            self.dup_box.setStyleSheet(
                f"background-color: {theme.duplicate_bg}; border: 1px solid {theme.duplicate_border}; border-radius: 6px; padding: 6px;"
            )
            self.lbl_dup_title.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {theme.duplicate};")
            self.lbl_dup_info.setStyleSheet(f"font-size: 11px; color: {theme.text_primary};")

        if hasattr(self, "btn_include"):
            self.btn_include.setStyleSheet(f"border-color: {theme.success}; color: {theme.success}; font-weight: bold;")
            self.btn_exclude.setStyleSheet(f"border-color: {theme.error}; color: {theme.error}; font-weight: bold;")

        # Refresh details if a record is selected
        if hasattr(self, "selected_record") and self.selected_record:
            self._display_record_details(self.selected_record)

        # Refresh table view colors
        if hasattr(self, "table_model"):
            self.table_model.beginResetModel()
            self.table_model.endResetModel()

    def _build_detail_panel(self):
        """Constructs widgets inside the detail panel."""
        # Header info
        self.lbl_detail_title = QLabel("تفاصيل المعاملة")
        self.lbl_detail_title.setObjectName("sectionTitle")
        self.detail_layout.addWidget(self.lbl_detail_title)

        self.lbl_meta_info = QLabel("حدد معاملة من الجدول لعرض تفاصيلها ومراجعتها.")
        self.lbl_meta_info.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_SECONDARY};")
        self.lbl_meta_info.setWordWrap(True)
        self.detail_layout.addWidget(self.lbl_meta_info)

        # Review Reasons Alert Box (shown only when reasons exist)
        self.reasons_box = QFrame()
        self.reasons_box.setStyleSheet(f"background-color: {COLOR_WARNING_BG}; border: 1px solid {COLOR_WARNING}; border-radius: 6px; padding: 6px;")
        self.reasons_box.setVisible(False)
        reasons_layout = QVBoxLayout(self.reasons_box)
        reasons_layout.setContentsMargins(8, 6, 8, 6)
        self.lbl_reasons_title = QLabel("تنبيهات وملاحظات المراجعة:")
        self.lbl_reasons_title.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {COLOR_NAVY};")
        reasons_layout.addWidget(self.lbl_reasons_title)
        self.lbl_reasons_text = QLabel("")
        self.lbl_reasons_text.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_PRIMARY};")
        self.lbl_reasons_text.setWordWrap(True)
        reasons_layout.addWidget(self.lbl_reasons_text)
        self.detail_layout.addWidget(self.reasons_box)

        # Raw Description Box
        self.lbl_raw_desc_title = QLabel("البيان من كشف الحساب:")
        self.lbl_raw_desc_title.setObjectName("fieldLabel")
        self.detail_layout.addWidget(self.lbl_raw_desc_title)
        
        self.lbl_raw_desc = QLabel("—")
        self.lbl_raw_desc.setStyleSheet(f"background-color: #F8FAFC; border: 1px solid {COLOR_BORDER}; border-radius: 4px; padding: 6px; font-size: 11px; color: {COLOR_NAVY};")
        self.lbl_raw_desc.setWordWrap(True)
        self.detail_layout.addWidget(self.lbl_raw_desc)

        # Editable Fields Section
        form_grid = QGridLayout()
        form_grid.setSpacing(8)

        # Date
        form_grid.addWidget(QLabel("التاريخ:"), 0, 0)
        self.edit_date = QLineEdit()
        form_grid.addWidget(self.edit_date, 0, 1)

        # Project
        form_grid.addWidget(QLabel("المشروع:"), 1, 0)
        self.edit_project = QLineEdit()
        form_grid.addWidget(self.edit_project, 1, 1)

        # Invoice
        form_grid.addWidget(QLabel("رقم الفاتورة:"), 2, 0)
        self.edit_invoice = QLineEdit()
        form_grid.addWidget(self.edit_invoice, 2, 1)

        # Supplier
        form_grid.addWidget(QLabel("المورد:"), 3, 0)
        self.edit_supplier = QLineEdit()
        form_grid.addWidget(self.edit_supplier, 3, 1)

        # Tax
        form_grid.addWidget(QLabel("الضريبة:"), 4, 0)
        self.edit_tax = QLineEdit()
        form_grid.addWidget(self.edit_tax, 4, 1)

        self.detail_layout.addLayout(form_grid)

        # Save and Confirm Field Review Button
        self.btn_save_field_review = QPushButton("حفظ التعديلات وتأكيد الحقول")
        self.btn_save_field_review.setObjectName("tealButton")
        self.btn_save_field_review.setCursor(Qt.PointingHandCursor)
        self.btn_save_field_review.clicked.connect(self._on_save_fields_clicked)
        self.detail_layout.addWidget(self.btn_save_field_review)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.HLine)
        div1.setStyleSheet(f"color: {COLOR_BORDER};")
        self.detail_layout.addWidget(div1)

        # Commercial Inclusion Decision Section
        self.inclusion_box = QFrame()
        inc_layout = QVBoxLayout(self.inclusion_box)
        inc_layout.setContentsMargins(0, 0, 0, 0)
        inc_layout.setSpacing(6)

        lbl_inc_title = QLabel("القرار التجاري للإدراج في المشتريات:")
        lbl_inc_title.setObjectName("fieldLabel")
        inc_layout.addWidget(lbl_inc_title)

        self.lbl_inc_status = QLabel("حالة الإدراج: —")
        self.lbl_inc_status.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {COLOR_NAVY};")
        inc_layout.addWidget(self.lbl_inc_status)

        inc_btn_row = QHBoxLayout()
        inc_btn_row.setSpacing(8)

        self.btn_include = QPushButton("إدراج المعاملة")
        self.btn_include.setObjectName("secondaryButton")
        self.btn_include.setStyleSheet(f"border-color: {COLOR_SUCCESS}; color: {COLOR_SUCCESS}; font-weight: bold;")
        self.btn_include.clicked.connect(self._on_include_clicked)
        inc_btn_row.addWidget(self.btn_include)

        self.btn_exclude = QPushButton("استبعاد المعاملة")
        self.btn_exclude.setObjectName("dangerButton")
        self.btn_exclude.clicked.connect(self._on_exclude_clicked)
        inc_btn_row.addWidget(self.btn_exclude)

        inc_layout.addLayout(inc_btn_row)
        self.detail_layout.addWidget(self.inclusion_box)

        # Duplicate Comparison Section (shown if potential duplicate)
        self.dup_box = QFrame()
        self.dup_box.setStyleSheet(f"background-color: #FFF7ED; border: 1px solid #FDBA74; border-radius: 6px; padding: 6px;")
        self.dup_box.setVisible(False)
        dup_layout = QVBoxLayout(self.dup_box)
        dup_layout.setContentsMargins(8, 8, 8, 8)
        dup_layout.setSpacing(6)

        self.lbl_dup_title = QLabel("تنبيه تكرار محتمل (مقارنة):")
        self.lbl_dup_title.setStyleSheet(f"font-size: 11px; font-weight: bold; color: #9A3412;")
        dup_layout.addWidget(self.lbl_dup_title)

        self.lbl_dup_info = QLabel("")
        self.lbl_dup_info.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_PRIMARY};")
        self.lbl_dup_info.setWordWrap(True)
        dup_layout.addWidget(self.lbl_dup_info)

        dup_btn_row = QHBoxLayout()
        self.btn_confirm_dup = QPushButton("تأكيد كمعاملة مستقلة")
        self.btn_confirm_dup.setObjectName("tealButton")
        self.btn_confirm_dup.clicked.connect(self._on_confirm_duplicate_clicked)
        dup_btn_row.addWidget(self.btn_confirm_dup)

        self.btn_exclude_dup = QPushButton("استبعاد المكررة")
        self.btn_exclude_dup.setObjectName("dangerButton")
        self.btn_exclude_dup.clicked.connect(self._on_exclude_duplicate_clicked)
        dup_btn_row.addWidget(self.btn_exclude_dup)
        dup_layout.addLayout(dup_btn_row)

        self.detail_layout.addWidget(self.dup_box)

        self.detail_layout.addStretch()

    def set_records(self, records: List[TransactionRecord]):
        """Populates the review screen with real records from extraction engine."""
        self.records = records
        self.table_model.set_records(records)
        self._update_counters()
        self._resize_columns()

        # Select first record if available
        if self.table_model.rowCount() > 0:
            self.select_record_by_index(0)

    def select_record_by_index(self, row: int):
        """Selects a record by its row index in the model and populates details."""
        if 0 <= row < self.table_model.rowCount():
            model_idx = self.table_model.index(row, 0)
            self.table_view.setCurrentIndex(model_idx)
            self.table_view.selectRow(row)
            rec = self.table_model.get_record(row)
            if rec:
                self.selected_record = rec
                self.selected_row_idx = row
                self._display_record_details(rec)

    def _resize_columns(self):
        header = self.table_view.horizontalHeader()
        header.resizeSection(0, 45)   # #
        header.resizeSection(1, 95)   # Date
        header.resizeSection(2, 105)  # Project
        header.resizeSection(3, 95)   # Invoice
        header.resizeSection(4, 170)  # Supplier
        header.resizeSection(5, 80)   # Tax
        header.resizeSection(6, 110)  # Status

    def _update_counters(self):
        """Recomputes status counters dynamically from real transaction states."""
        ready_cnt = sum(1 for r in self.records if r.is_export_eligible)
        review_cnt = sum(
            1 for r in self.records
            if (r.requires_field_review and not r.field_review_resolved)
            or (r.requires_inclusion_review and r.user_decision != UserDecision.INCLUDED_BY_USER)
        )
        excluded_cnt = sum(
            1 for r in self.records
            if r.inclusion_eligibility == InclusionEligibility.EXCLUDED_BY_RULE
            or r.user_decision == UserDecision.EXCLUDED_BY_USER
        )
        dup_cnt = sum(
            1 for r in self.records
            if r.duplicate_status == DuplicateStatus.POTENTIAL_DUPLICATE and not r.duplicate_resolved
        )

        self.badge_ready.set_count(ready_cnt)
        self.badge_review.set_count(review_cnt)
        self.badge_excluded.set_count(excluded_cnt)
        self.badge_duplicate.set_count(dup_cnt)

        total_visible = self.table_model.rowCount()
        self.lbl_count_info.setText(f"المعاملات المعروضة: {total_visible} من {len(self.records)}")

    def _on_search_changed(self, text: str):
        self.table_model.set_search_query(text)
        self._update_counters()

    def _on_filter_changed(self, idx: int):
        filter_key = self.filter_combo.currentData()
        self.table_model.set_status_filter(filter_key)
        self._update_counters()

    def _reset_filters(self):
        self.search_input.clear()
        self.filter_combo.setCurrentIndex(0)

    def _on_row_selected(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            row = indexes[0].row()
            self.select_record_by_index(row)

    def _display_record_details(self, rec: TransactionRecord):
        """Populates detail panel with the selected record's current state."""
        self.lbl_detail_title.setText(f"معاملة رقم #{rec.record_index}")
        meta_text = f"صفحة PDF: {rec.page_number} | مرجع القيد: {rec.reference or '—'}"
        self.lbl_meta_info.setText(meta_text)

        # Review reasons
        if rec.review_reasons:
            self.reasons_box.setVisible(True)
            self.lbl_reasons_text.setText("\n• ".join([""] + rec.review_reasons))
        else:
            self.reasons_box.setVisible(False)

        # Raw Description
        self.lbl_raw_desc.setText(rec.raw_description or "—")

        # Editable fields
        self.edit_date.setText(rec.date or "")
        self.edit_project.setText(rec.project or "")
        self.edit_invoice.setText(str(rec.invoice_number or ""))
        self.edit_supplier.setText(rec.supplier_name or "")
        self.edit_tax.setText(f"{rec.tax_amount:.2f}" if rec.tax_amount is not None else "0.00")

        # Commercial Inclusion Decision section
        theme = get_theme(self.theme_name)
        if rec.inclusion_eligibility == InclusionEligibility.EXCLUDED_BY_RULE:
            self.lbl_inc_status.setText(f"مستبعدة تلقائياً ({rec.classification_reason})")
            self.lbl_inc_status.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {theme.error};")
            self.btn_include.setEnabled(False)
            self.btn_exclude.setEnabled(False)
        elif rec.user_decision == UserDecision.EXCLUDED_BY_USER:
            self.lbl_inc_status.setText("مستبعدة بقرار صريح منك")
            self.lbl_inc_status.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {theme.error};")
            self.btn_include.setEnabled(True)
            self.btn_exclude.setEnabled(False)
        elif rec.user_decision == UserDecision.INCLUDED_BY_USER:
            self.lbl_inc_status.setText("معتمدة للإدراج بقرارك الصريح")
            self.lbl_inc_status.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {theme.success};")
            self.btn_include.setEnabled(False)
            self.btn_exclude.setEnabled(True)
        elif rec.requires_inclusion_review:
            self.lbl_inc_status.setText("بانتظار قرارك: هل تدرج في المشتريات؟")
            self.lbl_inc_status.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {theme.warning};")
            self.btn_include.setEnabled(True)
            self.btn_exclude.setEnabled(True)
        else:
            self.lbl_inc_status.setText("مؤهلة تلقائياً (مشتريات مشروع)")
            self.lbl_inc_status.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {theme.success};")
            self.btn_include.setEnabled(False)
            self.btn_exclude.setEnabled(True)

        # Potential Duplicate section
        if rec.duplicate_status == DuplicateStatus.POTENTIAL_DUPLICATE:
            self.dup_box.setVisible(True)
            # Find colliding record in batch
            colliders = [r for r in self.records if r != rec and r.duplicate_key == rec.duplicate_key]
            if colliders:
                col = colliders[0]
                self.lbl_dup_info.setText(
                    f"هذه المعاملة تتطابق في المفتاح المركب مع المعاملة #{col.record_index}:\n"
                    f"المشروع: {col.project} | الفاتورة: {col.invoice_number} | الضريبة: {col.tax_amount}"
                )
            else:
                self.lbl_dup_info.setText(f"مفتاح التكرار: {rec.duplicate_key}")
        else:
            self.dup_box.setVisible(False)

    def _on_save_fields_clicked(self):
        """Saves edited field values and prompts to resolve field review."""
        if not self.selected_record:
            return

        rec = self.selected_record
        rec.date = self.edit_date.text().strip()
        rec.project = self.edit_project.text().strip()
        rec.invoice_number = self.edit_invoice.text().strip() or None
        rec.supplier_name = self.edit_supplier.text().strip() or None
        try:
            rec.tax_amount = float(self.edit_tax.text().strip())
        except ValueError:
            QMessageBox.warning(self, "خطأ في القيمة", "الرجاء إدخال رقم ضريبة صحيح.")
            return

        # Explicit user confirmation to resolve field review
        rec.resolve_field_review("تم تأكيد وتصحيح الحقول يدوياً بواسطة المستخدم")
        
        # Refresh UI
        self.table_model.update_record_at(self.selected_row_idx)
        self._display_record_details(rec)
        self._update_counters()

        QMessageBox.information(
            self,
            "تم الحفظ",
            f"تم حفظ تعديلات المعاملة #{rec.record_index} وتأكيد مراجعة الحقول بنجاح."
        )

    def _on_include_clicked(self):
        """Explicitly approves commercial inclusion."""
        if not self.selected_record:
            return
        rec = self.selected_record
        if rec.inclusion_eligibility == InclusionEligibility.EXCLUDED_BY_RULE:
            QMessageBox.critical(self, "ممنوع", "لا يمكن إدراج معاملة مستبعدة بقاعدة نظامية معتمدة.")
            return

        rec.user_decision = UserDecision.INCLUDED_BY_USER
        self.table_model.update_record_at(self.selected_row_idx)
        self._display_record_details(rec)
        self._update_counters()

    def _on_exclude_clicked(self):
        """Explicitly excludes commercial inclusion."""
        if not self.selected_record:
            return
        rec = self.selected_record
        rec.user_decision = UserDecision.EXCLUDED_BY_USER
        self.table_model.update_record_at(self.selected_row_idx)
        self._display_record_details(rec)
        self._update_counters()

    def _on_confirm_duplicate_clicked(self):
        """Confirms duplicate is an independent legitimate transaction."""
        if not self.selected_record:
            return
        rec = self.selected_record
        rec.resolve_duplicate_warning("تم التأكيد كمعاملة مستقلة وليست تكراراً بالخطأ")
        self.table_model.update_record_at(self.selected_row_idx)
        self._display_record_details(rec)
        self._update_counters()
        QMessageBox.information(self, "تأكيد المعاملة", "تم تأكيد المعاملة كمعاملة مستقلة واعتمادها.")

    def _on_exclude_duplicate_clicked(self):
        """Excludes the duplicate record from export."""
        if not self.selected_record:
            return
        rec = self.selected_record
        rec.user_decision = UserDecision.EXCLUDED_BY_USER
        self.table_model.update_record_at(self.selected_row_idx)
        self._display_record_details(rec)
        self._update_counters()
        QMessageBox.information(self, "استبعاد التكرار", "تم استبعاد المعاملة المكررة من التصدير.")

    # ---------------------------------------------------------
    # Supplier Grouping & Bulk Editing Actions
    # ---------------------------------------------------------
    def _on_group_suppliers_clicked(self):
        """Displays suggested supplier groups and allows interactive bulk editing."""
        groups = group_similar_suppliers(self.records)
        if not groups:
            QMessageBox.information(
                self,
                "لا توجد مجموعات موردين",
                "لم يتم العثور على مجموعات موردين متشابهين بحاجة إلى تصحيح حالياً."
            )
            return

        dlg = SupplierGroupingDialog(groups, parent=self)
        dlg.review_group_requested.connect(lambda grp: self._on_review_group(grp, parent_dlg=dlg))
        dlg.exec()

    def _on_review_group(self, group: SupplierGroupSuggestion, parent_dlg=None):
        """Opens the bulk editing dialog for the selected group."""
        edit_dlg = BulkSupplierEditDialog(group, parent=self)
        edit_dlg.applied.connect(self._apply_bulk_supplier_edit)
        if edit_dlg.exec() == QDialog.Accepted and parent_dlg:
            # Refresh the grouping dialog table with updated remaining suggestions
            remaining_groups = group_similar_suppliers(self.records)
            if remaining_groups:
                parent_dlg.groups = remaining_groups
                parent_dlg._populate_table()
            else:
                parent_dlg.accept()

    def _apply_bulk_supplier_edit(self, group, canonical_name: str, selected_records: List[TransactionRecord]):
        """Applies canonical supplier name to selected records and stores snapshot for undo."""
        # Store undo state
        self.last_bulk_edit = {
            "canonical_name": canonical_name,
            "count": len(selected_records),
            "records_data": [
                {
                    "record": r,
                    "supplier_name": r.supplier_name,
                    "is_supplier_valid": r.is_supplier_valid,
                    "review_reasons": list(r.review_reasons),
                    "review_notes": r.review_notes,
                    "extraction_status": r.extraction_status,
                    "field_review_resolved": r.field_review_resolved,
                }
                for r in selected_records
            ]
        }

        for r in selected_records:
            r.resolve_supplier_review(canonical_name, notes="تم التصحيح والاعتماد الجماعي للمورد")

        # Refresh model
        self.table_model.beginResetModel()
        self.table_model.endResetModel()

        # Update counters and details panel
        self._update_counters()
        if self.selected_record in selected_records:
            self._display_record_details(self.selected_record)

        self.btn_undo_bulk.setVisible(True)
        self.btn_undo_bulk.setEnabled(True)

        QMessageBox.information(
            self,
            "تم التعديل الجماعي",
            f"تم اعتماد وتطبيق اسم المورد '{canonical_name}' بنجاح على {len(selected_records)} معاملة."
        )

    def _on_undo_bulk_clicked(self):
        """Reverts the most recent bulk supplier edit performed during the current review session."""
        if not self.last_bulk_edit:
            return

        reply = QMessageBox.question(
            self,
            "تأكيد التراجع",
            f"هل تريد التراجع عن التعديل الجماعي الأخير وإعادة {self.last_bulk_edit['count']} معاملة لحالتها السابقة؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        for item in self.last_bulk_edit["records_data"]:
            r = item["record"]
            r.supplier_name = item["supplier_name"]
            r.is_supplier_valid = item["is_supplier_valid"]
            r.review_reasons = list(item["review_reasons"])
            r.review_notes = item["review_notes"]
            r.extraction_status = item["extraction_status"]
            r.field_review_resolved = item["field_review_resolved"]

        self.last_bulk_edit = None
        self.btn_undo_bulk.setVisible(False)
        self.btn_undo_bulk.setEnabled(False)

        self.table_model.beginResetModel()
        self.table_model.endResetModel()
        self._update_counters()
        if self.selected_record:
            self._display_record_details(self.selected_record)

        QMessageBox.information(
            self,
            "تم التراجع",
            "تم التراجع عن التعديل الجماعي الأخير وإعادة البيانات إلى حالتها السابقة بنجاح."
        )
