"""
Comprehensive Verification Tests for INJAZ UI Polish, Branding, Dropdown Contrast & Full Dark Mode.
Covers all 8 requirements specified in the UI polish specification.
"""
import os
import sys
import pytest
from PySide6.QtWidgets import (
    QApplication, QComboBox, QStyledItemDelegate, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QPalette, QColor

from injaz.models import (
    TransactionRecord, ExtractionStatus, InclusionEligibility,
    UserDecision, DuplicateStatus
)
from injaz.ui.theme import (
    ThemeManager, get_theme, get_current_theme, get_stylesheet,
    get_dialog_stylesheet, style_combo_box, apply_theme_to_app,
    LIGHT_THEME, DARK_THEME
)
from injaz.ui.main_window import MainWindow
from injaz.ui.components.header import HeaderWidget
from injaz.ui.pages.review_page import ReviewPage
from injaz.ui.components.dialogs import ExportConfirmDialog, ExportSuccessDialog


@pytest.fixture(scope="session")
def qapp():
    """Initializes shared QApplication in offscreen mode."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    return app


@pytest.fixture(autouse=True)
def mock_dialogs(monkeypatch):
    """Mocks blocking modal dialogs during automated tests."""
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)


def create_sample_record(idx: int = 1, status: str = "READY") -> TransactionRecord:
    rec = TransactionRecord(
        page_number=1,
        record_index=idx,
        date="2024-05-15",
        transaction_type="قيد يدوي",
        raw_description=f"فاتورة مشتريات #{1000+idx}",
        reference=f"REF-{idx}",
        debit=15.0,
        credit=0.0,
        balance="1000.0",
        project="مشروع العليا",
        invoice_number=str(1000 + idx),
        supplier_name="شركة الرياض للتجارة",
        tax_amount=15.0,
        is_invoice_valid=True,
        is_tax_valid=True,
        is_supplier_valid=True,
        extraction_status=ExtractionStatus.VALIDATED,
        inclusion_eligibility=InclusionEligibility.ELIGIBLE_FOR_INCLUSION,
        user_decision=UserDecision.NOT_APPLICABLE,
        duplicate_status=DuplicateStatus.UNIQUE,
        duplicate_key=f"مشروع العليا_{1000+idx}_15.0",
    )
    if status == "READY":
        rec.field_review_resolved = True
    elif status == "REVIEW_FIELDS":
        rec.extraction_status = ExtractionStatus.MANUAL_REVIEW
        rec.field_review_resolved = False
        rec.review_reasons = ["فحص يدوي مطلوب"]
    elif status == "REVIEW_DECISION":
        rec.inclusion_eligibility = InclusionEligibility.REQUIRES_USER_REVIEW
        rec.user_decision = UserDecision.PENDING
    elif status == "DUPLICATE":
        rec.duplicate_status = DuplicateStatus.POTENTIAL_DUPLICATE
        rec.duplicate_resolved = False
        rec.duplicate_key = "dup_key_1"
    elif status == "EXCLUDED":
        rec.inclusion_eligibility = InclusionEligibility.EXCLUDED_BY_RULE
        rec.classification_reason = "سحب نقدي"
    return rec


# =========================================================================
# 1. Light Theme Initialization
# =========================================================================
def test_1_light_theme_initialization(qapp):
    theme = get_theme("light")
    assert theme.name == "light"
    assert theme.primary_navy == "#16324F"
    assert theme.teal == "#1D9A8A"
    assert theme.bg == "#F5F7FA"
    assert theme.surface == "#FFFFFF"
    assert theme.text_primary == "#172033"
    assert theme.text_secondary == "#667085"
    assert theme.border == "#E2E8F0"
    assert theme.warning == "#E8A23A"
    assert theme.error == "#D64545"
    assert theme.success == "#248B62"


# =========================================================================
# 2. Dark Theme Activation
# =========================================================================
def test_2_dark_theme_activation(qapp):
    theme = get_theme("dark")
    assert theme.name == "dark"
    assert theme.bg == "#111827"
    assert theme.bg_secondary == "#18212D"
    assert theme.surface == "#202A36"
    assert theme.text_primary == "#F1F5F9"
    assert theme.text_secondary == "#B6C2D0"
    assert theme.border == "#344152"
    assert theme.teal == "#35B8A6"
    assert theme.warning == "#F2B84B"
    assert theme.error == "#F06A73"
    assert theme.success == "#4CC38A"

    window = MainWindow()
    window.apply_theme("dark")
    assert window.current_theme == "dark"
    assert ThemeManager.instance().current_theme == "dark"
    # Clean up to light
    window.apply_theme("light")
    assert window.current_theme == "light"


# =========================================================================
# 3. Dropdown Contrast and Styling (Light & Dark)
# =========================================================================
def test_3_dropdown_contrast_and_options(qapp):
    review = ReviewPage()
    combo = review.filter_combo

    # Verify all 5 required options exist with unchanged keys
    items = [combo.itemText(i) for i in range(combo.count())]
    expected_items = [
        "عرض الكل",
        "جاهزة للإدراج فقط",
        "تحتاج مراجعة (حقول أو قرار)",
        "تكرار محتمل فقط",
        "مستبعدة"
    ]
    assert items == expected_items

    # Verify custom item delegate is set
    assert isinstance(combo.itemDelegate(), QStyledItemDelegate)

    # Verify Light theme popup palette
    style_combo_box(combo, "light")
    view = combo.view()
    assert view is not None
    pal_light = view.palette()
    assert pal_light.color(QPalette.Base).name().upper() == "#FFFFFF"
    assert pal_light.color(QPalette.Text).name().upper() == "#172033"
    assert pal_light.color(QPalette.Highlight).name().upper() == "#E6F4F1"

    # Verify Dark theme popup palette
    style_combo_box(combo, "dark")
    pal_dark = view.palette()
    assert pal_dark.color(QPalette.Base).name().upper() == "#202A36"
    assert pal_dark.color(QPalette.Text).name().upper() == "#F1F5F9"
    assert pal_dark.color(QPalette.Highlight).name().upper() in ("#1E3D45", "#283545", "#2A3B4C")


# =========================================================================
# 4. Logo Assets Selected Correctly for Theme
# =========================================================================
def test_4_logo_assets_selected_for_theme(qapp):
    header = HeaderWidget()

    # Light mode logo
    header.set_theme("light")
    pix_light = header.logo_label.pixmap()
    assert pix_light is not None and not pix_light.isNull()
    assert pix_light.height() == 40
    # Width should preserve aspect ratio ~ 110px
    assert 90 <= pix_light.width() <= 130
    assert not header.logo_label.isHidden()
    assert header.logo_fallback.isHidden()

    # Dark mode logo
    header.set_theme("dark")
    pix_dark = header.logo_label.pixmap()
    assert pix_dark is not None and not pix_dark.isNull()
    assert pix_dark.height() == 40
    assert 90 <= pix_dark.width() <= 130
    assert not header.logo_label.isHidden()
    assert header.logo_fallback.isHidden()

    # Test fallback reporting
    header._show_logo_fallback(get_theme("light"), "Test missing asset")
    assert header.logo_label.isHidden()
    assert not header.logo_fallback.isHidden()
    assert "إنجاز" in header.logo_fallback.text()


# =========================================================================
# 5. Native Windows Window Title
# =========================================================================
def test_5_exact_window_title(qapp):
    window = MainWindow()
    assert window.windowTitle() == "إنجاز - INJAZ"


# =========================================================================
# 6. Workflow Step Labels - Inner Rectangles Removed & Navigation
# =========================================================================
def test_6_workflow_step_inner_rectangles_and_navigation(qapp):
    header = HeaderWidget()
    assert len(header.step_widgets) == 3

    # Check that pill labels have transparent border and background
    for pill, num_lbl, text_lbl in header.step_widgets:
        text_style = text_lbl.styleSheet()
        assert "border: none" in text_style
        assert "background: transparent" in text_style
        assert "outline: none" in text_style

    # Stepper navigation signal
    signals_received = []
    header.step_clicked.connect(lambda s: signals_received.append(s))
    header.set_current_step(2)
    header._on_pill_clicked(1)
    assert signals_received == [1]


# =========================================================================
# 7. Theme Persistence via QSettings
# =========================================================================
def test_7_theme_persistence_across_launches(qapp):
    mgr = ThemeManager.instance()
    
    # Save dark
    mgr.save_theme_preference("dark")
    settings = QSettings("INJAZ", "InjazApp")
    assert settings.value("theme") == "dark"
    assert mgr.load_theme_preference() == "dark"

    # Save light
    mgr.save_theme_preference("light")
    assert settings.value("theme") == "light"
    assert mgr.load_theme_preference() == "light"


# =========================================================================
# 8. Business Logic, Review Decisions, and Filtering Functionality Preserved
# =========================================================================
def test_8_review_filtering_and_decisions_preserved(qapp):
    review = ReviewPage()
    r1 = create_sample_record(1, "READY")
    r2 = create_sample_record(2, "REVIEW_FIELDS")
    r3 = create_sample_record(3, "REVIEW_DECISION")
    r4 = create_sample_record(4, "DUPLICATE")
    r5 = create_sample_record(5, "EXCLUDED")
    records = [r1, r2, r3, r4, r5]

    review.set_records(records)
    assert review.table_model.rowCount() == 5
    assert review.badge_ready.count_val == 1
    assert review.badge_review.count_val == 2
    assert review.badge_duplicate.count_val == 1
    assert review.badge_excluded.count_val == 1

    # Filter Ready
    review.filter_combo.setCurrentIndex(1)
    assert review.table_model.rowCount() == 1
    assert review.table_model.get_record(0).record_index == 1

    # Filter Review
    review.filter_combo.setCurrentIndex(2)
    assert review.table_model.rowCount() == 2

    # Filter Duplicate
    review.filter_combo.setCurrentIndex(3)
    assert review.table_model.rowCount() == 1
    assert review.table_model.get_record(0).record_index == 4

    # Filter Excluded
    review.filter_combo.setCurrentIndex(4)
    assert review.table_model.rowCount() == 1
    assert review.table_model.get_record(0).record_index == 5

    # Reset filter
    review._reset_filters()
    assert review.table_model.rowCount() == 5

    # Resolve field review on r2
    review.select_record_by_index(1)
    review.edit_supplier.setText("مورد مصحح")
    review._on_save_fields_clicked()
    assert r2.supplier_name == "مورد مصحح"
    assert r2.field_review_resolved is True
    review.deleteLater()
    qapp.processEvents()
