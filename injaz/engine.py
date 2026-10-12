"""
Core Extraction Engine for Injaz (إنجاز) — Phase 2.
Orchestrates PDF layout parsing, field normalization, business rule classification,
and duplicate detection into a unified, modular, testable interface.
"""
from typing import Optional, List, Callable
from injaz.models import (
    TransactionRecord,
    ProcessingResult,
    ExtractionStatus,
    InclusionEligibility,
)
from injaz.pdf_extractor import PDFStatementExtractor
from injaz.rules import BusinessRulesEngine, is_head_office_project
from injaz.duplicates import evaluate_batch_duplicates


class CoreExtractionEngine:
    """
    Main entry point for Phase 2 Core Extraction & Classification.
    """
    def __init__(
        self,
        rules_engine: Optional[BusinessRulesEngine] = None,
        head_office_patterns: Optional[List[str]] = None
    ):
        self.rules_engine = rules_engine or BusinessRulesEngine(
            head_office_patterns=head_office_patterns
        )

    def process_statement(
        self,
        pdf_path: str,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> ProcessingResult:
        """
        Extracts, normalizes, classifies, and checks duplicates for a statement PDF.
        """
        # 1. Low-level layout extraction
        if progress_callback:
            progress_callback("قراءة كشف الحساب واستخراج المعاملات...", 20)
            
        raw_extractor = PDFStatementExtractor(
            pdf_path=pdf_path,
            head_office_patterns=self.rules_engine.head_office_patterns
        )
        records = raw_extractor.extract_transactions()

        # 2. Re-apply business rules engine to ensure complete decoupling
        if progress_callback:
            progress_callback("التحقق من البيانات وتطبيق قواعد الاستبعاد...", 55)
        exclusion_breakdown = {}
        for r in records:
            # Check for special single-digit invoice flag
            is_single_digit = (r.invoice_number is not None and len(r.invoice_number) == 1)
            
            eligibility, ex_cat, reason, decision, exp_status = self.rules_engine.classify_transaction(
                raw_desc=r.raw_description,
                project_str=r.project,
                extraction_status=r.extraction_status,
                is_single_digit_invoice=is_single_digit,
                extraction_error_note=r.review_notes
            )
            r.inclusion_eligibility = eligibility
            r.exclusion_category = ex_cat
            r.classification_reason = reason
            r.user_decision = decision
            r.export_status = exp_status

            if ex_cat:
                cat_name = ex_cat.value
                exclusion_breakdown[cat_name] = exclusion_breakdown.get(cat_name, 0) + 1

        # 3. Duplicate checks
        if progress_callback:
            progress_callback("اكتشاف التكرارات المحتملة...", 80)
        dup_count = evaluate_batch_duplicates(records)

        # 4. Compute aggregate metrics
        if progress_callback:
            progress_callback("إعداد وتجهيز الإحصائيات...", 95)
        val_ext = sum(1 for r in records if r.extraction_status == ExtractionStatus.VALIDATED)
        man_ext = sum(1 for r in records if r.extraction_status == ExtractionStatus.MANUAL_REVIEW)

        eligible = sum(1 for r in records if r.inclusion_eligibility == InclusionEligibility.ELIGIBLE_FOR_INCLUSION)
        excluded = sum(1 for r in records if r.inclusion_eligibility == InclusionEligibility.EXCLUDED_BY_RULE)
        review = sum(1 for r in records if r.inclusion_eligibility == InclusionEligibility.REQUIRES_USER_REVIEW)
        dual_rev = sum(1 for r in records if r.is_dual_review)
        ho_count = sum(1 for r in records if is_head_office_project(r.project, self.rules_engine.head_office_patterns))

        if progress_callback:
            progress_callback("اكتمل التحليل بنجاح.", 100)

        return ProcessingResult(
            total_records=len(records),
            records=records,
            validated_extraction_count=val_ext,
            manual_review_extraction_count=man_ext,
            eligible_count=eligible,
            excluded_count=excluded,
            user_review_count=review,
            dual_review_count=dual_rev,
            head_office_count=ho_count,
            duplicates_count=dup_count,
            exclusion_breakdown=exclusion_breakdown
        )
