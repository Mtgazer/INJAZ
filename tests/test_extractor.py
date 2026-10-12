"""
Automated unit and integration tests for PDFStatementExtractor.
Tests layout-aware PDF extraction, field parsing, and classification on synthetic statements.
"""
import pytest
from injaz.pdf_extractor import PDFStatementExtractor
from injaz.models import ExtractionStatus, InclusionEligibility, DuplicateStatus


class TestSyntheticStatementExtraction:
    """Verifies that PDFStatementExtractor accurately extracts records from PDF layout."""

    def test_extract_transactions_count_and_types(self, synthetic_pdf_path):
        extractor = PDFStatementExtractor(synthetic_pdf_path)
        records = extractor.extract_transactions()

        assert len(records) == 4
        for r in records:
            assert r.date.startswith("2026-05-")
            assert r.tax_amount is not None
            assert r.tax_amount > 0

    def test_extraction_identifies_legitimate_purchases(self, synthetic_pdf_path):
        extractor = PDFStatementExtractor(synthetic_pdf_path)
        records = extractor.extract_transactions()

        # Record 1: Clean purchase
        r1 = records[0]
        assert r1.date == "2026-05-01"
        assert r1.invoice_number == "101"
        assert r1.tax_amount == 150.0
        assert r1.debit == 150.0
        assert "14" in r1.project

    def test_extraction_identifies_duplicates_via_engine(self, synthetic_pdf_path):
        from injaz.engine import CoreExtractionEngine
        engine = CoreExtractionEngine()
        result = engine.process_statement(synthetic_pdf_path)

        # Records 3 and 4 share date, invoice 103, amount, and project
        r3 = result.records[2]
        r4 = result.records[3]
        assert r3.duplicate_status == DuplicateStatus.UNIQUE
        assert r4.duplicate_status == DuplicateStatus.POTENTIAL_DUPLICATE
        assert r4.duplicate_key != ""

    def test_missing_pdf_raises_error(self, tmp_path):
        non_existent = str(tmp_path / "non_existent_file.pdf")
        extractor = PDFStatementExtractor(non_existent)
        with pytest.raises(Exception):
            extractor.extract_transactions()
