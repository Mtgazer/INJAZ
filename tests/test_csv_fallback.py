"""
Comprehensive Regression Tests for CSV Export Fallback.
Verifies all Priority 3 requirements:
- Arabic text round-tripping.
- UTF-8 BOM encoding (utf-8-sig).
- Correct headers and column ordering.
- Correct signs and values (+debit, -credit).
- Empty eligible-record batch behavior.
- Rejection of ineligible transactions.
- Preservation of source files.
- Existing-output-file overwrite protection.
- Reopening the CSV and programmatic row verification.
"""
import os
import csv
import pytest
import tempfile
import hashlib

from injaz.models import (
    TransactionRecord, ExtractionStatus, InclusionEligibility, UserDecision, DuplicateStatus
)
from injaz.csv_writer import (
    CsvPopulationEngine, CsvExportError, IneligibleCsvExportError, CsvValidationError
)


def make_record(
    idx: int,
    supplier: str = "شركة البناء الحديث",
    invoice: str = "20261",
    date: str = "2026-05-15",
    project: str = "مشروع النرجس",
    tax: float = 245.50,
    eligible: bool = True
) -> TransactionRecord:
    rec = TransactionRecord(
        page_number=1,
        record_index=idx,
        date=date,
        transaction_type="قيد يدوي",
        raw_description=f"فاتورة {invoice} {supplier}",
        reference=f"REF-{idx:04d}",
        debit="1636.67",
        credit="0.00",
        balance="100000.00",
        project=project,
        invoice_number=invoice,
        supplier_name=supplier,
        tax_amount=tax,
        extraction_status=ExtractionStatus.VALIDATED if eligible else ExtractionStatus.MANUAL_REVIEW,
        inclusion_eligibility=InclusionEligibility.ELIGIBLE_FOR_INCLUSION if eligible else InclusionEligibility.EXCLUDED_BY_RULE,
        is_supplier_valid=eligible,
        is_invoice_valid=eligible,
        is_tax_valid=eligible
    )
    if not eligible:
        rec.add_review_reason("Record flagged for manual review")
    return rec


def test_csv_headers_and_column_ordering(tmp_path):
    engine = CsvPopulationEngine()
    out_file = str(tmp_path / "test_headers.csv")
    records = [make_record(1)]

    summary = engine.export_transactions(out_file, records)
    assert summary.records_exported == 1

    with open(out_file, "r", newline="", encoding="utf-8-sig") as f:
        reader = list(csv.reader(f))

    assert len(reader) == 2  # 1 header + 1 data row
    assert reader[0] == ["م", "التاريخ", "المشروع", "رقم الفاتورة", "المورد", "الضريبة"]
    assert reader[1][0] == "1"
    assert reader[1][1] == "2026-05-15"
    assert reader[1][2] == "مشروع النرجس"
    assert reader[1][3] == "20261"
    assert reader[1][4] == "شركة البناء الحديث"
    assert reader[1][5] == "245.50"


def test_csv_utf8_bom_presence(tmp_path):
    engine = CsvPopulationEngine()
    out_file = str(tmp_path / "test_bom.csv")
    records = [make_record(1)]

    engine.export_transactions(out_file, records)

    with open(out_file, "rb") as f:
        bom_bytes = f.read(3)
    assert bom_bytes == b'\xef\xbb\xbf', "CSV must begin with UTF-8 BOM"


def test_csv_arabic_text_round_tripping(tmp_path):
    engine = CsvPopulationEngine()
    out_file = str(tmp_path / "test_arabic.csv")
    arabic_supplier = "مؤسسة الوفاء للتجارة والمقاولات العامة (ذ.م.م)"
    arabic_project = "مشروع صيل 16 - مرحلة العظم"
    records = [make_record(1, supplier=arabic_supplier, project=arabic_project)]

    engine.export_transactions(out_file, records)

    with open(out_file, "r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    assert rows[1][2] == arabic_project
    assert rows[1][4] == arabic_supplier


def test_csv_tax_signs_and_values(tmp_path):
    engine = CsvPopulationEngine()
    out_file = str(tmp_path / "test_tax_signs.csv")
    r_pos = make_record(1, tax=150.75)
    r_neg = make_record(2, tax=-300.00)

    engine.export_transactions(out_file, [r_pos, r_neg])

    with open(out_file, "r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    assert rows[1][5] == "150.75"
    assert rows[2][5] == "-300.00"


def test_csv_empty_eligible_record_batch(tmp_path):
    engine = CsvPopulationEngine()
    out_file = str(tmp_path / "test_empty.csv")
    records = []

    summary = engine.export_transactions(out_file, records)
    assert summary.records_exported == 0
    assert summary.total_records_submitted == 0

    with open(out_file, "r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 1  # Only headers


def test_csv_rejection_of_ineligible_records(tmp_path):
    engine = CsvPopulationEngine()
    out_file = str(tmp_path / "test_ineligible.csv")
    r_valid = make_record(1, eligible=True)
    r_invalid = make_record(2, eligible=False)

    summary = engine.export_transactions(out_file, [r_valid, r_invalid], fail_on_ineligible=False)
    assert summary.records_exported == 1
    assert summary.records_rejected_ineligible == 1
    assert len(summary.rejection_details) == 1

    # With fail_on_ineligible=True
    with pytest.raises(IneligibleCsvExportError):
        engine.export_transactions(
            str(tmp_path / "test_fail.csv"),
            [r_invalid],
            fail_on_ineligible=True
        )


def test_csv_existing_output_file_behavior(tmp_path):
    engine = CsvPopulationEngine()
    out_file = str(tmp_path / "test_exists.csv")
    records = [make_record(1)]

    # First write: creates file
    engine.export_transactions(out_file, records, overwrite=False)

    # Second write without overwrite: must raise FileExistsError
    with pytest.raises(FileExistsError):
        engine.export_transactions(out_file, records, overwrite=False)

    # Second write with overwrite=True: succeeds
    summary2 = engine.export_transactions(out_file, records, overwrite=True)
    assert summary2.records_exported == 1


def test_csv_preserves_reference_files(synthetic_pdf_path, synthetic_template_path, tmp_path):
    h_pdf_before = hashlib.sha256(open(synthetic_pdf_path, "rb").read()).hexdigest()
    h_xlsx_before = hashlib.sha256(open(synthetic_template_path, "rb").read()).hexdigest()

    engine = CsvPopulationEngine()
    out_file = str(tmp_path / "csv_preservation_test.csv")
    engine.export_transactions(out_file, [make_record(1)])

    h_pdf_after = hashlib.sha256(open(synthetic_pdf_path, "rb").read()).hexdigest()
    h_xlsx_after = hashlib.sha256(open(synthetic_template_path, "rb").read()).hexdigest()

    assert h_pdf_before == h_pdf_after
    assert h_xlsx_before == h_xlsx_after
