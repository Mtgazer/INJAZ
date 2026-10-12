"""
Integration and system tests for Injaz Core Extraction Engine (injaz.engine).
Tests orchestration, independence of extraction status and inclusion eligibility,
dual-review transaction handling, and end-to-end processing with privacy preservation.
"""
import pytest
import os
import hashlib
from injaz.engine import CoreExtractionEngine
from injaz.models import (
    ExtractionStatus,
    InclusionEligibility,
    UserDecision,
    ExclusionCategory,
    TransactionRecord,
    ProcessingResult,
    DuplicateStatus,
)


class TestCoreEngineDataModelIndependence:
    def test_dual_review_property(self):
        # Transaction requiring both field review and inclusion review
        rec = TransactionRecord(
            page_number=1, record_index=1, date="2026-04-15", transaction_type="قيد",
            raw_description="مؤسسة مقاولات فاتورة رقم 8", reference="3462", debit=11250.0,
            credit=0.0, balance="11250", project="صيل 16", invoice_number="8",
            supplier_name="مؤسسة مقاولات", tax_amount=11250.0,
            extraction_status=ExtractionStatus.MANUAL_REVIEW,
            inclusion_eligibility=InclusionEligibility.REQUIRES_USER_REVIEW
        )
        assert rec.requires_field_review is True
        assert rec.requires_inclusion_review is True
        assert rec.is_dual_review is True

    def test_extraction_validated_with_user_review(self):
        # Head office appraisal: clean fields (VALIDATED), but requires user decision
        rec = TransactionRecord(
            page_number=1, record_index=2, date="2026-04-15", transaction_type="قيد",
            raw_description="أتعاب تقييم عقاري 105", reference="3100", debit=2500.0,
            credit=0.0, balance="2500", project="المركز الرئيسي", invoice_number="105",
            supplier_name="شركة التقييم", tax_amount=2500.0,
            extraction_status=ExtractionStatus.VALIDATED,
            inclusion_eligibility=InclusionEligibility.REQUIRES_USER_REVIEW
        )
        assert rec.requires_field_review is False
        assert rec.requires_inclusion_review is True
        assert rec.is_dual_review is False

    def test_manual_review_extraction_with_rule_exclusion(self):
        # VAT refund: no invoice number (MANUAL_REVIEW), but excluded by rule
        rec = TransactionRecord(
            page_number=2, record_index=24, date="2026-04-15", transaction_type="قيد",
            raw_description="استرداد ضريبة القيمة المضافة", reference="3125", debit=0.0,
            credit=171435.33, balance="171435.33", project="المركز الرئيسي", invoice_number=None,
            supplier_name="استرداد ضريبة القيمة المضافة", tax_amount=-171435.33,
            extraction_status=ExtractionStatus.MANUAL_REVIEW,
            inclusion_eligibility=InclusionEligibility.EXCLUDED_BY_RULE,
            exclusion_category=ExclusionCategory.VAT_REFUND
        )
        assert rec.requires_field_review is True
        assert rec.requires_inclusion_review is False
        assert rec.is_dual_review is False
        assert rec.inclusion_eligibility == InclusionEligibility.EXCLUDED_BY_RULE

    def test_simultaneous_invoice_and_tax_uncertainty_preserves_all_reasons(self):
        # Test simultaneous invoice-number and tax-amount uncertainty
        rec = TransactionRecord(
            page_number=1, record_index=1, date="2026-04-15", transaction_type="قيد",
            raw_description="توريد مواد بدون فاتورة وبقيم مشبوهة", reference="1001",
            debit=100.0, credit=50.0, balance="50", project="صيل 16", invoice_number=None,
            supplier_name="شركة التوريد", tax_amount=None,
            is_invoice_valid=False, is_tax_valid=False, is_supplier_valid=True
        )
        rec.add_review_reason("Both Debit (100.0) and Credit (50.0) are nonzero")
        rec.add_review_reason("No identifiable invoice number in description")
        
        assert len(rec.review_reasons) == 2
        assert "Both Debit" in rec.review_reasons[0]
        assert "No identifiable invoice" in rec.review_reasons[1]
        assert " | " in rec.review_notes
        assert rec.extraction_status == ExtractionStatus.MANUAL_REVIEW
        assert rec.is_invoice_valid is False
        assert rec.is_tax_valid is False

    def test_debit_and_credit_both_positive_tax_uncertainty(self):
        from injaz.normalizer import compute_tax_amount
        tax, err = compute_tax_amount(500.0, 200.0)
        assert tax is None
        assert "Both Debit (500.0) and Credit (200.0) are nonzero" in err


class TestEndToEndSyntheticExtraction:
    def test_synthetic_statement_processing(self, synthetic_pdf_path):
        """Verifies full engine execution on synthetic statement."""
        engine = CoreExtractionEngine()
        result = engine.process_statement(synthetic_pdf_path)

        assert result.total_records == 4
        assert len(result.records) == 4
        assert result.validated_extraction_count + result.manual_review_extraction_count == 4

        # Check records
        r1 = result.records[0]
        assert r1.date == "2026-05-01"
        assert r1.invoice_number == "101"
        assert r1.tax_amount == 150.0

    def test_source_pdf_immutability(self, synthetic_pdf_path):
        """Verifies source PDF is never modified during engine execution."""
        def file_hash(path):
            h = hashlib.sha256()
            with open(path, 'rb') as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            return h.hexdigest()

        pdf_before = file_hash(synthetic_pdf_path)

        engine = CoreExtractionEngine()
        result = engine.process_statement(synthetic_pdf_path)
        assert result.total_records == 4

        pdf_after = file_hash(synthetic_pdf_path)
        assert pdf_before == pdf_after

    def test_duplicate_detection_integration(self, synthetic_pdf_path):
        """Verifies duplicate transaction pairs are flagged by the engine."""
        engine = CoreExtractionEngine()
        result = engine.process_statement(synthetic_pdf_path)

        dup_records = [r for r in result.records if r.duplicate_status == DuplicateStatus.POTENTIAL_DUPLICATE]
        assert len(dup_records) == 1
        assert dup_records[0].invoice_number == "103"
        assert dup_records[0].duplicate_key != ""
