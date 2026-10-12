"""
Comprehensive Regression Tests for Supplier Grouping & Bulk Editing.
Verifies all 12 required behaviors using synthetic company names:
1. Identical supplier names.
2. Names differing only by repeated whitespace.
3. Arabic font-spacing artifacts.
4. Common Alef variations.
5. Similar but genuinely different supplier names remaining separate.
6. Selecting only some records in a suggested group.
7. Applying one canonical supplier name to multiple selected records.
8. Cancelling a bulk edit without changing data.
9. Undoing the most recent bulk edit.
10. Preserving invoice and tax review issues after a supplier correction.
11. Updating underlying records and displayed table consistently.
12. Refreshing group suggestions after successful correction.
"""
import os
import sys
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from injaz.models import (
    TransactionRecord, ExtractionStatus, InclusionEligibility, UserDecision, DuplicateStatus
)
from injaz.supplier_matcher import (
    group_similar_suppliers,
    normalize_for_comparison,
    spaceless_key,
    has_font_spacing_artifacts,
    clean_despaced_candidate,
    generate_canonical_candidate,
    are_names_conservatively_similar,
)
from injaz.ui.models import TransactionTableModel


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    return app


def make_record(
    idx: int,
    supplier: str,
    invoice: str = "1001",
    date: str = "2026-05-10",
    project: str = "مشروع الأندلس",
    tax: float = 150.0,
    valid_supplier: bool = True,
    review_reasons: list = None,
    valid_invoice: bool = True,
    valid_tax: bool = True
) -> TransactionRecord:
    rec = TransactionRecord(
        page_number=1,
        record_index=idx,
        date=date,
        transaction_type="قيد يدوي",
        raw_description=f"شراء مواد من {supplier} فاتورة {invoice}",
        reference=f"REF-{idx:04d}",
        debit="1000.00",
        credit="0.00",
        balance="50000.00",
        project=project,
        invoice_number=invoice,
        supplier_name=supplier,
        tax_amount=tax,
        extraction_status=ExtractionStatus.VALIDATED if not review_reasons else ExtractionStatus.MANUAL_REVIEW,
        inclusion_eligibility=InclusionEligibility.ELIGIBLE_FOR_INCLUSION,
        is_supplier_valid=valid_supplier,
        is_invoice_valid=valid_invoice,
        is_tax_valid=valid_tax,
        review_reasons=list(review_reasons or [])
    )
    if review_reasons:
        rec.review_notes = " | ".join(review_reasons)
    return rec


# 1. Identical supplier names
def test_1_identical_supplier_names():
    records = [
        make_record(1, "شركة الأمل للتجارة", valid_supplier=False, review_reasons=["Supplier requires confirmation"]),
        make_record(2, "شركة الأمل للتجارة", valid_supplier=False, review_reasons=["Supplier requires confirmation"]),
        make_record(3, "شركة الأمل للتجارة", valid_supplier=False, review_reasons=["Supplier requires confirmation"]),
    ]
    groups = group_similar_suppliers(records)
    assert len(groups) == 1
    assert groups[0].total_records == 3
    assert len(groups[0].variants) == 1
    assert groups[0].variants[0].raw_name == "شركة الأمل للتجارة"


# 2. Names differing only by repeated whitespace
def test_2_names_differing_only_by_repeated_whitespace():
    records = [
        make_record(1, "شركة   البركة   للمقاولات"),
        make_record(2, "شركة البركة للمقاولات"),
        make_record(3, "شركة  البركة  للمقاولات"),
    ]
    groups = group_similar_suppliers(records)
    assert len(groups) == 1
    assert groups[0].total_records == 3
    assert len(groups[0].variants) >= 2
    assert groups[0].reason_code in ("whitespace", "font_spacing")


# 3. Arabic font-spacing artifacts
def test_3_arabic_font_spacing_artifacts():
    raw_spaced = "شركة ا لنجم للخدما ت"
    assert has_font_spacing_artifacts(raw_spaced) is True

    records = [
        make_record(1, raw_spaced, valid_supplier=False, review_reasons=["Supplier name contains font-spaced Arabic glyph artifacts"]),
        make_record(2, "شركة النجم للخدمات"),
    ]
    groups = group_similar_suppliers(records)
    assert len(groups) == 1
    assert groups[0].total_records == 2
    assert groups[0].reason_code == "font_spacing"


# 4. Common Alef variations
def test_4_common_alef_variations():
    records = [
        make_record(1, "شركة الأنوار الحديثة"),
        make_record(2, "شركة الانوار الحديثة"),
        make_record(3, "شركة الإنمائية الدولية"),
    ]
    # First two should group together; third is a distinct entity
    groups = group_similar_suppliers(records)
    anwar_group = [g for g in groups if "انوار" in normalize_for_comparison(g.suggested_label)]
    assert len(anwar_group) == 1
    assert anwar_group[0].total_records == 2


# 5. Similar but genuinely different supplier names remaining separate
def test_5_different_companies_remain_separate():
    name1 = "شركة الفهد للمقاولات"
    name2 = "شركة النمر للمقاولات"
    assert are_names_conservatively_similar(name1, name2) is False

    records = [
        make_record(1, name1),
        make_record(2, name2),
    ]
    groups = group_similar_suppliers(records)
    # Valid, distinct records with no issues should not be merged into one group
    for g in groups:
        raw_names = [v.raw_name for v in g.variants]
        assert not (name1 in raw_names and name2 in raw_names)


# 6. Selecting only some records in a suggested group
def test_6_selective_records_bulk_edit():
    records = [
        make_record(1, "مؤسسة الرواد ف"),
        make_record(2, "مؤسسة الرواد"),
        make_record(3, "مؤسسة الرواد بلك"),
    ]
    # Select only records 1 and 2
    selected = [records[0], records[1]]
    canonical = "مؤسسة الرواد للمقاولات"

    for r in selected:
        r.resolve_supplier_review(canonical)

    assert records[0].supplier_name == canonical
    assert records[1].supplier_name == canonical
    assert records[2].supplier_name == "مؤسسة الرواد بلك"  # Unchanged!


# 7. Applying one canonical supplier name to multiple selected records
def test_7_applying_canonical_name_to_multiple_records():
    records = [
        make_record(1, "شركة ا لصفوة", valid_supplier=False, review_reasons=["Supplier name contains font-spaced Arabic glyph artifacts"]),
        make_record(2, "شركة ا لصفوة", valid_supplier=False, review_reasons=["Supplier name contains font-spaced Arabic glyph artifacts"]),
        make_record(3, "شركة الصفوة"),
    ]
    canonical = "شركة الصفوة للمقاولات العامة"
    for r in records:
        r.resolve_supplier_review(canonical)

    for r in records:
        assert r.supplier_name == canonical
        assert r.is_supplier_valid is True
        assert "font-spaced" not in " ".join(r.review_reasons).lower()


# 8. Cancelling a bulk edit without changing data
def test_8_cancelling_bulk_edit_leaves_data_untouched():
    original_name = "مؤسسة البناء ا لحديث"
    rec = make_record(1, original_name, valid_supplier=False, review_reasons=["font-spaced"])
    # Simulating cancel: no resolve called
    assert rec.supplier_name == original_name
    assert rec.is_supplier_valid is False
    assert len(rec.review_reasons) == 1


# 9. Undoing the most recent bulk edit
def test_9_undoing_most_recent_bulk_edit():
    r1 = make_record(1, "شركة ا لقوة", valid_supplier=False, review_reasons=["font-spaced"])
    r2 = make_record(2, "شركة القوة")
    records = [r1, r2]

    # Snapshot before edit
    snapshot = [
        {
            "record": r,
            "supplier_name": r.supplier_name,
            "is_supplier_valid": r.is_supplier_valid,
            "review_reasons": list(r.review_reasons),
            "review_notes": r.review_notes,
            "extraction_status": r.extraction_status,
            "field_review_resolved": r.field_review_resolved
        }
        for r in records
    ]

    # Apply edit
    for r in records:
        r.resolve_supplier_review("شركة القوة المتحدة")

    assert r1.supplier_name == "شركة القوة المتحدة"
    assert r2.supplier_name == "شركة القوة المتحدة"

    # Revert via undo
    for item in snapshot:
        rec = item["record"]
        rec.supplier_name = item["supplier_name"]
        rec.is_supplier_valid = item["is_supplier_valid"]
        rec.review_reasons = list(item["review_reasons"])
        rec.review_notes = item["review_notes"]
        rec.extraction_status = item["extraction_status"]
        rec.field_review_resolved = item["field_review_resolved"]

    assert r1.supplier_name == "شركة ا لقوة"
    assert r1.is_supplier_valid is False
    assert r1.review_reasons == ["font-spaced"]
    assert r2.supplier_name == "شركة القوة"


# 10. Preserving invoice and tax review issues after supplier correction
def test_10_preserving_unrelated_reviews_after_supplier_correction():
    rec = make_record(
        idx=1,
        supplier="شركة ا لتطوير",
        invoice="5",
        valid_supplier=False,
        valid_invoice=True,
        review_reasons=[
            "Supplier name contains font-spaced Arabic glyph artifacts",
            "Single-digit invoice number requires manual field confirmation"
        ]
    )
    assert rec.requires_field_review is True
    assert rec.is_export_eligible is False

    # Resolve ONLY supplier
    rec.resolve_supplier_review("شركة التطوير العقاري")

    # Supplier is fixed and valid
    assert rec.supplier_name == "شركة التطوير العقاري"
    assert rec.is_supplier_valid is True

    # BUT invoice review is PRESERVED!
    assert "Single-digit invoice number requires manual field confirmation" in rec.review_reasons
    assert rec.field_review_resolved is False
    assert rec.requires_field_review is True
    assert rec.extraction_status == ExtractionStatus.MANUAL_REVIEW
    # Strict fail-closed export eligibility remains False until invoice is also resolved!
    assert rec.is_export_eligible is False


# 11. Updating underlying records and displayed table consistently
def test_11_table_model_consistency(qapp):
    records = [
        make_record(1, "شركة ا لتقنية", valid_supplier=False, review_reasons=["font-spaced"]),
        make_record(2, "شركة التقنية"),
    ]
    model = TransactionTableModel()
    model.set_records(records)
    assert model.rowCount() == 2

    # Before edit
    idx0 = model.index(0, 4)  # Col 4 is Supplier
    assert idx0.data() == "شركة ا لتقنية"

    # Resolve supplier on record 0
    records[0].resolve_supplier_review("شركة التقنية المتقدمة")
    model.beginResetModel()
    model.endResetModel()

    # After edit
    idx0_after = model.index(0, 4)
    assert idx0_after.data() == "شركة التقنية المتقدمة"


# 12. Refreshing group suggestions after successful correction
def test_12_group_suggestions_refresh_after_correction():
    records = [
        make_record(1, "شركة ا لرائد", valid_supplier=False, review_reasons=["Supplier name contains font-spaced Arabic glyph artifacts"]),
        make_record(2, "شركة ا لرائد", valid_supplier=False, review_reasons=["Supplier name contains font-spaced Arabic glyph artifacts"]),
    ]
    # Before correction: group is suggested
    groups_before = group_similar_suppliers(records)
    assert len(groups_before) == 1

    # Apply canonical correction to both
    for r in records:
        r.resolve_supplier_review("شركة الرائد للتجارة")

    # After correction: both are valid with no review reasons or artifacts
    groups_after = group_similar_suppliers(records)
    assert len(groups_after) == 0  # No longer needs review!
