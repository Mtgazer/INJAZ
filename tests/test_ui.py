"""
Unit and integration tests for INJAZ (إنجاز) Phase 4 Desktop UI.
Runs headless using Qt offscreen platform.
Covers all 14 required UI criteria.
"""
import os
import sys
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from PySide6.QtCore import Qt, QModelIndex

from injaz.models import (
    TransactionRecord,
    ExtractionStatus,
    InclusionEligibility,
    UserDecision,
    DuplicateStatus,
    ProcessingResult,
    ExclusionCategory,
)
from injaz.excel_writer import ExportSummary, ExcelPopulationError
from injaz.ui.theme import APP_STYLESHEET
from injaz.ui.components.header import HeaderWidget
from injaz.ui.models import TransactionTableModel
from injaz.ui.pages.new_process_page import NewProcessPage
from injaz.ui.pages.review_page import ReviewPage
from injaz.ui.pages.export_page import ExportPage
from injaz.ui.main_window import MainWindow
from injaz.ui.workers import AnalysisWorker, ExportWorker


@pytest.fixture(scope="session")
def qapp():
    """Initializes a shared QApplication in offscreen mode with Arabic RTL layout."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    return app


@pytest.fixture(autouse=True)
def mock_message_boxes(monkeypatch):
    """Prevents modal dialogs from blocking headless tests."""
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "exec_", lambda self: QMessageBox.Ok)
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(QDialog, "exec_", lambda self: QDialog.Accepted)


def create_synthetic_record(
    index: int = 1,
    date: str = "2024-05-15",
    project: str = "مشروع الرياض",
    invoice: str = "10025",
    supplier: str = "شركة المقاولات المتحدة",
    tax: float = 150.0,
    extraction_status: ExtractionStatus = ExtractionStatus.VALIDATED,
    inclusion_eligibility: InclusionEligibility = InclusionEligibility.ELIGIBLE_FOR_INCLUSION,
    user_decision: UserDecision = UserDecision.NOT_APPLICABLE,
    duplicate_status: DuplicateStatus = DuplicateStatus.UNIQUE,
    duplicate_key: str = "",
) -> TransactionRecord:
    """Helper creating a test TransactionRecord with precise attributes."""
    rec = TransactionRecord(
        page_number=1,
        record_index=index,
        date=date,
        transaction_type="قيد يدوي",
        raw_description=f"فاتورة {invoice} {supplier}",
        reference=f"REF-{index}",
        debit=tax,
        credit=0.0,
        balance="1000.0",
        project=project,
        invoice_number=invoice,
        supplier_name=supplier,
        tax_amount=tax,
        extraction_status=extraction_status,
        inclusion_eligibility=inclusion_eligibility,
        user_decision=user_decision,
        duplicate_status=duplicate_status,
        duplicate_key=duplicate_key or f"{project}_{invoice}_{tax}",
    )
    if extraction_status == ExtractionStatus.MANUAL_REVIEW:
        rec.add_review_reason("تأكيد حقول المعاملة مطلوب")
    return rec


def create_synthetic_result(records: list) -> ProcessingResult:
    """Helper creating a real ProcessingResult matching dataclass fields."""
    return ProcessingResult(
        total_records=len(records),
        records=records,
        validated_extraction_count=sum(1 for r in records if r.extraction_status == ExtractionStatus.VALIDATED),
        manual_review_extraction_count=sum(1 for r in records if r.extraction_status == ExtractionStatus.MANUAL_REVIEW),
        eligible_count=sum(1 for r in records if r.inclusion_eligibility == InclusionEligibility.ELIGIBLE_FOR_INCLUSION),
        excluded_count=sum(1 for r in records if r.inclusion_eligibility == InclusionEligibility.EXCLUDED_BY_RULE),
        user_review_count=sum(1 for r in records if r.inclusion_eligibility == InclusionEligibility.REQUIRES_USER_REVIEW),
        dual_review_count=sum(1 for r in records if r.is_dual_review),
        head_office_count=0,
        duplicates_count=sum(1 for r in records if r.duplicate_status == DuplicateStatus.POTENTIAL_DUPLICATE),
    )


# =========================================================================
# Requirement 1: Application creation without an unhandled exception
# =========================================================================
def test_1_application_creation_without_unhandled_exception(qapp):
    window = MainWindow()
    assert window is not None
    assert "إنجاز" in window.windowTitle()
    assert window.centralWidget() is not None
    assert window.header is not None
    assert window.stack is not None
    assert window.stack.count() == 3
    assert window.stack.currentIndex() == 0  # Starts on Step 1 (New Process)
    window.close()


# =========================================================================
# Requirement 2: Correct Arabic RTL layout initialization
# =========================================================================
def test_2_correct_arabic_rtl_layout_initialization(qapp):
    window = MainWindow()
    assert qapp.layoutDirection() == Qt.RightToLeft
    assert window.layoutDirection() == Qt.RightToLeft
    assert window.header.layoutDirection() == Qt.RightToLeft
    assert window.new_process_page.layoutDirection() == Qt.RightToLeft
    window.close()


# =========================================================================
# Requirement 3: PDF file selection validation (PDF-only workflow)
# =========================================================================
def test_3_pdf_file_selection_validation(qapp, tmp_path):
    page = NewProcessPage()
    assert not page.btn_start.isEnabled()

    # Create dummy pdf
    pdf_file = tmp_path / "test_statement.pdf"
    pdf_file.write_text("dummy pdf content")

    page._on_pdf_selected(str(pdf_file))
    assert page.pdf_path == str(pdf_file)
    # Ready immediately because PDF-only workflow auto-determines default output
    assert page.btn_start.isEnabled()

    # Clearing resets path and state
    page.pdf_card.clear_file()
    assert page.pdf_path == ""
    assert not page.btn_start.isEnabled()


# =========================================================================
# Requirement 4: PDF-only workflow and overwrite protection (no template required)
# =========================================================================
def test_4_excel_template_selection_validation(qapp, tmp_path):
    page = NewProcessPage()
    # In simplified workflow, no excel template card exists on screen
    assert not hasattr(page, "excel_card")

    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_text("pdf")
    page._on_pdf_selected(str(pdf_file))
    assert page.btn_start.isEnabled()

    # Overwrite protection: output path matching input PDF must be rejected
    page.output_path = str(pdf_file)
    started = []
    page.start_analysis_requested.connect(lambda *args: started.append(args))
    page._on_start_clicked()
    assert len(started) == 0

    # With distinct output path, analysis request emits cleanly
    valid_out = str(tmp_path / "output.xlsx")
    page.output_path = valid_out
    page._on_start_clicked()
    assert len(started) == 1
    assert started[0][0] == str(pdf_file)
    assert started[0][1] == valid_out


# =========================================================================
# Requirement 5: Analysis success and analysis failure
# =========================================================================
def test_5_analysis_success_and_analysis_failure(qapp, monkeypatch):
    window = MainWindow()

    # 1. Test Analysis Success
    rec1 = create_synthetic_record(index=1)
    synthetic_result = create_synthetic_result([rec1])
    window._on_analysis_success(synthetic_result)
    assert window.records == [rec1]
    assert window.stack.currentIndex() == 1  # Navigated to Review
    assert window.header.step_widgets[1][0] is not None  # Step 2 active

    # 2. Test Analysis Failure
    window._show_step_1()
    window.new_process_page.progress_frame.setVisible(True)
    window._on_analysis_error("خطأ في قراءة ملف PDF")
    assert not window.new_process_page.progress_frame.isVisible()
    assert window.new_process_page.btn_start.isEnabled()
    window.close()


# =========================================================================
# Requirement 6: Navigation from file selection to review and back
# =========================================================================
def test_6_navigation_from_file_selection_to_review(qapp):
    window = MainWindow()
    assert window.stack.currentIndex() == 0

    # Advance to review
    rec = create_synthetic_record()
    window._on_analysis_success(create_synthetic_result([rec]))
    assert window.stack.currentIndex() == 1

    # Click Back to files
    window.review_page.back_to_files_requested.emit()
    assert window.stack.currentIndex() == 0

    window.close()


# =========================================================================
# Requirement 7: Rendering real transaction records and their status labels
# =========================================================================
def test_7_rendering_real_transaction_records_and_status_labels(qapp):
    rec_ready = create_synthetic_record(1, "2024-01-01", "مشروع أ", "101", "مورد أ", 100.0)
    rec_review = create_synthetic_record(
        2, "2024-01-02", "مشروع ب", "102", "مورد ب", 50.0,
        extraction_status=ExtractionStatus.MANUAL_REVIEW
    )
    rec_excluded = create_synthetic_record(
        3, "2024-01-03", "مشروع ج", "103", "مورد ج", 200.0,
        inclusion_eligibility=InclusionEligibility.EXCLUDED_BY_RULE
    )
    rec_dup = create_synthetic_record(
        4, "2024-01-04", "مشروع د", "104", "مورد د", 300.0,
        duplicate_status=DuplicateStatus.POTENTIAL_DUPLICATE
    )

    records = [rec_ready, rec_review, rec_excluded, rec_dup]
    model = TransactionTableModel(records)

    assert model.rowCount() == 4
    assert model.data(model.index(0, TransactionTableModel.COL_STATUS)) == "جاهزة للإدراج"
    assert model.data(model.index(1, TransactionTableModel.COL_STATUS)) == "مراجعة الحقول"
    assert "مستبعدة" in model.data(model.index(2, TransactionTableModel.COL_STATUS))
    assert model.data(model.index(3, TransactionTableModel.COL_STATUS)) == "تكرار محتمل"

    # Test ReviewPage counter updates
    page = ReviewPage()
    page.set_records(records)
    assert page.badge_ready.lbl_count.text() == "1"
    assert page.badge_review.lbl_count.text() == "1"
    assert page.badge_excluded.lbl_count.text() == "1"
    assert page.badge_duplicate.lbl_count.text() == "1"


# =========================================================================
# Requirement 8: Search and filtering without modifying underlying data
# =========================================================================
def test_8_search_and_filtering_without_modifying_underlying_data(qapp):
    rec1 = create_synthetic_record(1, invoice="5551", supplier="مورد الفاخر")
    rec2 = create_synthetic_record(2, invoice="9992", supplier="مؤسسة التقنية")
    rec3 = create_synthetic_record(
        3, invoice="3333", supplier="شركة النور",
        inclusion_eligibility=InclusionEligibility.EXCLUDED_BY_RULE
    )

    records = [rec1, rec2, rec3]
    model = TransactionTableModel(records)
    assert model.rowCount() == 3

    # Search filter
    model.set_search_query("الفاخر")
    assert model.rowCount() == 1
    assert model.get_record(0).supplier_name == "مورد الفاخر"
    # Ensure underlying data not dropped
    assert len(model._all_records) == 3

    # Status filter
    model.set_search_query("")
    model.set_status_filter("EXCLUDED")
    assert model.rowCount() == 1
    assert model.get_record(0).record_index == 3

    # Reset
    model.set_status_filter("ALL")
    assert model.rowCount() == 3


# =========================================================================
# Requirement 9: Editing a transaction and resolving field review correctly
# =========================================================================
def test_9_editing_transaction_and_resolving_field_review_correctly(qapp):
    rec = create_synthetic_record(
        1, invoice="10", supplier="مورد_غير_مؤكد",
        extraction_status=ExtractionStatus.MANUAL_REVIEW
    )
    assert rec.requires_field_review
    assert not rec.field_review_resolved

    page = ReviewPage()
    page.set_records([rec])

    # Select the row
    page.select_record_by_index(0)
    assert page.selected_record == rec

    # Edit fields in the UI
    page.edit_supplier.setText("شركة الأمل للتجارة")
    page.edit_invoice.setText("1099")
    page.edit_tax.setText("250.00")

    # Confirm user clicks save and confirm review button
    page._on_save_fields_clicked()

    # Check that underlying record was updated, not just the UI
    assert rec.supplier_name == "شركة الأمل للتجارة"
    assert rec.invoice_number == "1099"
    assert rec.tax_amount == 250.0
    assert rec.field_review_resolved is True
    assert rec.is_export_eligible is True


# =========================================================================
# Requirement 10: Inclusion and exclusion decisions separate from technical review
# =========================================================================
def test_10_inclusion_and_exclusion_decisions_separate_from_technical_review(qapp):
    rec_review = create_synthetic_record(
        1,
        inclusion_eligibility=InclusionEligibility.REQUIRES_USER_REVIEW,
        user_decision=UserDecision.PENDING
    )
    assert not rec_review.is_export_eligible

    page = ReviewPage()
    page.set_records([rec_review])
    page.select_record_by_index(0)

    # Click Include
    page._on_include_clicked()
    assert rec_review.user_decision == UserDecision.INCLUDED_BY_USER
    assert rec_review.is_export_eligible is True

    # Rule-excluded records cannot be overridden by include button
    rec_rule_excluded = create_synthetic_record(
        2, inclusion_eligibility=InclusionEligibility.EXCLUDED_BY_RULE
    )
    page.set_records([rec_rule_excluded])
    page.select_record_by_index(0)
    assert not page.btn_include.isEnabled()

    page._on_include_clicked()  # Attempting to call handler directly
    # Decision must remain untouched
    assert rec_rule_excluded.user_decision != UserDecision.INCLUDED_BY_USER
    assert rec_rule_excluded.is_export_eligible is False


# =========================================================================
# Requirement 11: Duplicate decisions being explicit and non-destructive
# =========================================================================
def test_11_duplicate_decisions_being_explicit_and_non_destructive(qapp):
    rec1 = create_synthetic_record(
        1, duplicate_status=DuplicateStatus.POTENTIAL_DUPLICATE, duplicate_key="PROJ_INV_100"
    )
    rec2 = create_synthetic_record(
        2, duplicate_status=DuplicateStatus.POTENTIAL_DUPLICATE, duplicate_key="PROJ_INV_100"
    )

    page = ReviewPage()
    page.set_records([rec1, rec2])
    assert len(page.records) == 2

    # Case A: Confirm as independent transaction
    page.select_record_by_index(0)
    page._on_confirm_duplicate_clicked()
    assert rec1.duplicate_resolved is True
    assert rec1.is_export_eligible is True
    assert len(page.records) == 2  # Non-destructive: neither record is deleted

    # Case B: Exclude duplicate
    page.select_record_by_index(1)
    page._on_exclude_duplicate_clicked()
    assert rec2.user_decision == UserDecision.EXCLUDED_BY_USER
    assert rec2.is_export_eligible is False
    assert len(page.records) == 2  # Record preserved in data for audit history


# =========================================================================
# Requirement 12: Export being blocked when reviews or decisions remain unresolved
# =========================================================================
def test_12_export_being_blocked_when_reviews_or_decisions_remain_unresolved(qapp):
    # Create records with various unresolved issues
    rec_unresolved_field = create_synthetic_record(
        1, extraction_status=ExtractionStatus.MANUAL_REVIEW
    )
    rec_unresolved_inc = create_synthetic_record(
        2, inclusion_eligibility=InclusionEligibility.REQUIRES_USER_REVIEW
    )
    rec_unresolved_dup = create_synthetic_record(
        3, duplicate_status=DuplicateStatus.POTENTIAL_DUPLICATE
    )

    records = [rec_unresolved_field, rec_unresolved_inc, rec_unresolved_dup]

    page = ExportPage()
    page.set_data(records, "template.xlsx", "output.xlsx")

    assert page.row_eligible.lbl_count.text() == "0"
    assert page.row_field_rev.lbl_count.text() == "1"
    assert page.row_inc_dec.lbl_count.text() == "1"
    assert page.row_dup.lbl_count.text() == "1"

    # Export button must be disabled
    assert not page.btn_export.isEnabled()

    # Calling handler directly blocks export
    export_signals = []
    page.export_started.connect(lambda *args: export_signals.append(args))
    page._on_export_clicked()
    assert len(export_signals) == 0


# =========================================================================
# Requirement 13: Successful export calling existing writer and displaying real result
# =========================================================================
def test_13_successful_export_calling_existing_writer_and_displaying_real_result(qapp, tmp_path, monkeypatch):
    rec_eligible = create_synthetic_record(1)
    assert rec_eligible.is_export_eligible

    page = ExportPage()
    template_path = str(tmp_path / "template.xlsx")
    output_path = str(tmp_path / "output.xlsx")
    page.set_data([rec_eligible], template_path, output_path)

    assert page.btn_export.isEnabled()

    # Test ExportWorker execution with mocked engine
    mock_summary = ExportSummary(
        total_records_submitted=1,
        records_exported=1,
        records_skipped_already_present=0,
        records_rejected_ineligible=0,
        output_path=output_path,
    )

    worker = ExportWorker(template_path, output_path, [rec_eligible])
    monkeypatch.setattr(
        "injaz.ui.workers.ExcelPopulationEngine.export_transactions",
        lambda *args, **kwargs: mock_summary
    )

    results = []
    worker.export_finished.connect(lambda summary: results.append(summary))
    worker.run()

    assert len(results) == 1
    assert results[0].records_exported == 1

    # Verify ExportPage success handling
    page.handle_export_success(results[0])
    assert not page.progress_frame.isVisible()
    assert page.btn_export.isEnabled()


# =========================================================================
# Requirement 14: Export failure leaving input files untouched and preserving review state
# =========================================================================
def test_14_export_failure_leaving_input_files_untouched_and_preserving_review_state(qapp, tmp_path, monkeypatch):
    rec_eligible = create_synthetic_record(1)
    template_file = tmp_path / "template.xlsx"
    template_file.write_text("original content")

    page = ExportPage()
    output_path = str(tmp_path / "out.xlsx")
    page.set_data([rec_eligible], str(template_file), output_path)

    worker = ExportWorker(str(template_file), output_path, [rec_eligible])

    def mock_fail(*args, **kwargs):
        raise ExcelPopulationError("تعذر كتابة ملف الإكسيل: خطأ في البنية")

    monkeypatch.setattr("injaz.ui.workers.ExcelPopulationEngine.export_transactions", mock_fail)

    errors = []
    worker.export_failed.connect(lambda err: errors.append(err))
    worker.run()

    assert len(errors) == 1
    assert "تعذر كتابة ملف الإكسيل" in errors[0]

    # Verify input template file content remains completely untouched
    assert template_file.read_text() == "original content"
    assert not os.path.exists(output_path)

    # Verify review records preserved
    assert len(page.records) == 1
    assert page.records[0] == rec_eligible
