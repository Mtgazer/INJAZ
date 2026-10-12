"""
Data models for Injaz (إنجاز) — Phase 2 Core Engine.
Defines structured financial transaction records, decoupled extraction statuses,
business inclusion outcomes, exclusion categories, and duplicate-check states.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple


class ExtractionStatus(str, Enum):
    """
    Technical document extraction status.
    Indicates whether field extraction succeeded with high certainty.
    """
    VALIDATED = "VALIDATED"          # All required fields cleanly extracted and verified
    MANUAL_REVIEW = "MANUAL_REVIEW"  # One or more fields missing, uncertain, or ambiguous


class InclusionEligibility(str, Enum):
    """
    Business inclusion outcome for the purchases worksheet.
    Independent of extraction accuracy.
    """
    ELIGIBLE_FOR_INCLUSION = "ELIGIBLE_FOR_INCLUSION"  # Valid project purchase passing rules
    EXCLUDED_BY_RULE = "EXCLUDED_BY_RULE"              # Clearly matches confirmed exclusion rule
    REQUIRES_USER_REVIEW = "REQUIRES_USER_REVIEW"      # Uncertain or requires explicit user approval


class UserDecision(str, Enum):
    """
    User decision state for transactions requiring review.
    """
    NOT_APPLICABLE = "NOT_APPLICABLE"    # Automatically resolved by rule or eligibility
    PENDING = "PENDING"                  # Awaiting user decision in review screen
    INCLUDED_BY_USER = "INCLUDED_BY_USER"  # User explicitly approved inclusion
    EXCLUDED_BY_USER = "EXCLUDED_BY_USER"  # User explicitly chose exclusion


class ExclusionCategory(str, Enum):
    """
    Confirmed business exclusion categories.
    """
    ELECTRICITY_BILL = "ELECTRICITY_BILL"      # سداد فواتير وعدادات الكهرباء
    GENERAL_BILL = "GENERAL_BILL"              # سداد فواتير عامة مطابقة للأنماط
    FUEL_EXPENSE = "FUEL_EXPENSE"              # محروقات ووقود المركبات والمولدات
    VAT_REFUND = "VAT_REFUND"                  # استرداد ضريبة القيمة المضافة من الهيئة
    RENT_PAYMENT = "RENT_PAYMENT"              # سداد الإيجارات
    HEAD_OFFICE_ADMIN = "HEAD_OFFICE_ADMIN"    # مهمات ومصروفات إدارية للمقر الرئيسي
    OTHER = "OTHER"                            # استبعاد مخصص آخر


class DuplicateStatus(str, Enum):
    """
    Duplicate-check state relative to incoming records or existing database.
    """
    UNIQUE = "UNIQUE"
    POTENTIAL_DUPLICATE = "POTENTIAL_DUPLICATE"


class ExportStatus(str, Enum):
    """
    Final readiness for writing to the target Excel worksheet.
    """
    READY_TO_WRITE = "READY_TO_WRITE"          # Ready to be written to Excel
    SKIPPED = "SKIPPED"                        # Excluded from Excel writing
    HELD_PENDING_REVIEW = "HELD_PENDING_REVIEW"  # Blocked until user decision is resolved


@dataclass
class TransactionRecord:
    page_number: int
    record_index: int
    date: str                                       # YYYY-MM-DD
    transaction_type: str                           # e.g. قيد يدوي
    raw_description: str                            # Full raw text from statement
    reference: str                                  # Accounting reference / مرجع القيد
    debit: float                                    # Raw debit amount (non-negative float)
    credit: float                                   # Raw credit amount (non-negative float)
    balance: str                                    # Raw balance string
    project: str                                    # Normalized project name
    invoice_number: Optional[str] = None            # Parsed invoice number
    supplier_name: Optional[str] = None             # Parsed supplier name
    tax_amount: Optional[float] = None              # Computed tax amount (+debit or -credit)
    
    # Classification dimensions
    extraction_status: ExtractionStatus = ExtractionStatus.VALIDATED
    inclusion_eligibility: InclusionEligibility = InclusionEligibility.ELIGIBLE_FOR_INCLUSION
    exclusion_category: Optional[ExclusionCategory] = None
    classification_reason: str = "Standard project purchase"
    user_decision: UserDecision = UserDecision.NOT_APPLICABLE
    duplicate_status: DuplicateStatus = DuplicateStatus.UNIQUE
    duplicate_key: str = ""
    export_status: ExportStatus = ExportStatus.READY_TO_WRITE
    review_notes: Optional[str] = None
    review_reasons: List[str] = field(default_factory=list)
    is_invoice_valid: bool = True
    is_tax_valid: bool = True
    is_supplier_valid: bool = True
    field_review_resolved: bool = False
    duplicate_resolved: bool = False

    def add_review_reason(self, reason: str):
        """Appends a review reason, updates review_notes, and flags extraction for manual review."""
        if reason and reason not in self.review_reasons:
            self.review_reasons.append(reason)
            self.review_notes = " | ".join(self.review_reasons)
            self.extraction_status = ExtractionStatus.MANUAL_REVIEW

    def resolve_field_review(self, notes: Optional[str] = None):
        """Explicitly marks all field-level review concerns as resolved by human reviewer."""
        self.field_review_resolved = True
        if notes:
            self.review_notes = (self.review_notes + " | " + notes) if self.review_notes else notes

    def resolve_duplicate_warning(self, notes: Optional[str] = None):
        """Explicitly marks potential duplicate warning as resolved/approved by human reviewer."""
        self.duplicate_resolved = True
        if notes:
            self.review_notes = (self.review_notes + " | " + notes) if self.review_notes else notes

    def resolve_supplier_review(self, canonical_name: str, notes: Optional[str] = None):
        """
        Updates the supplier name and clears ONLY supplier-related review concerns.
        Preserves invoice, tax, duplicate, and commercial inclusion reviews intact.
        If other field reviews remain, field_review_resolved remains False.
        """
        self.supplier_name = canonical_name
        self.is_supplier_valid = True
        
        # Remove supplier-specific review reasons
        supplier_keywords = [
            "font-spaced",
            "supplier",
            "residual reference",
            "insufficient supplier",
            "مورد",
        ]
        self.review_reasons = [
            r for r in self.review_reasons
            if not any(kw in r.lower() for kw in supplier_keywords)
        ]
        
        if self.review_reasons:
            self.review_notes = " | ".join(self.review_reasons)
            if notes:
                self.review_notes += f" | {notes}"
        else:
            self.review_notes = notes
            # Only if all fields are valid and no other review reasons exist
            if self.is_invoice_valid and self.is_tax_valid:
                self.field_review_resolved = True
                self.extraction_status = ExtractionStatus.VALIDATED

    def check_export_eligibility(self) -> Tuple[bool, Optional[str]]:
        """
        Evaluates strict, fail-closed export eligibility.
        Returns (is_eligible, rejection_reason).
        """
        # 1. Confirmed exclusions are NEVER exportable
        if self.inclusion_eligibility == InclusionEligibility.EXCLUDED_BY_RULE:
            return False, "Record is excluded by rule (EXCLUDED_BY_RULE)"

        # 2. Explicit user exclusion
        if self.user_decision == UserDecision.EXCLUDED_BY_USER:
            return False, "Record was explicitly excluded by user (EXCLUDED_BY_USER)"

        # 3. Commercial inclusion review requires explicit human inclusion approval
        if self.inclusion_eligibility == InclusionEligibility.REQUIRES_USER_REVIEW:
            if self.user_decision != UserDecision.INCLUDED_BY_USER:
                return False, "Record requires user review and inclusion has not been explicitly approved"

        # 4. Field review must be validated or explicitly resolved
        if self.requires_field_review and not self.field_review_resolved:
            reasons = ", ".join(self.review_reasons) or "uncertain fields"
            return False, f"Record has unresolved field-level review: {reasons}"

        # 5. Potential duplicate warning must be explicitly resolved
        if self.duplicate_status == DuplicateStatus.POTENTIAL_DUPLICATE and not self.duplicate_resolved:
            return False, f"Record has unresolved duplicate warning (key: {self.duplicate_key})"

        # 6. Required fields for Excel export must be present
        if not self.date or not self.project or not self.invoice_number or not self.supplier_name or self.tax_amount is None:
            return False, "Record is missing required export fields (date, project, invoice_number, supplier_name, tax_amount)"

        return True, None

    @property
    def is_export_eligible(self) -> bool:
        """True if record meets all fail-closed export criteria."""
        eligible, _ = self.check_export_eligibility()
        return eligible

    @property
    def requires_field_review(self) -> bool:
        """True if any extracted field is missing, uncertain, or requires visual confirmation."""
        return (
            self.extraction_status == ExtractionStatus.MANUAL_REVIEW
            or bool(self.review_reasons)
            or not (self.is_invoice_valid and self.is_tax_valid and self.is_supplier_valid)
        )

    @property
    def requires_inclusion_review(self) -> bool:
        """True if user must decide whether to include this transaction in Excel."""
        return self.inclusion_eligibility == InclusionEligibility.REQUIRES_USER_REVIEW

    @property
    def is_dual_review(self) -> bool:
        """True if transaction simultaneously requires field-level review and an inclusion decision."""
        return self.requires_field_review and self.requires_inclusion_review

    # Backwards compatibility properties for Phase 1 code
    @property
    def status(self) -> ExtractionStatus:
        return self.extraction_status

    @status.setter
    def status(self, val: ExtractionStatus):
        self.extraction_status = val

    @property
    def inclusion_decision(self):
        # Maps inclusion eligibility to inclusion decision representation
        from injaz.models import InclusionEligibility
        if self.inclusion_eligibility == InclusionEligibility.REQUIRES_USER_REVIEW:
            return "PENDING_REVIEW"
        elif self.inclusion_eligibility == InclusionEligibility.EXCLUDED_BY_RULE:
            return "EXCLUDE"
        else:
            return "INCLUDE"


@dataclass
class ProcessingResult:
    """
    Summary of the batch extraction and classification run.
    """
    total_records: int
    records: List[TransactionRecord]
    
    # Extraction status breakdown
    validated_extraction_count: int
    manual_review_extraction_count: int
    
    # Inclusion eligibility breakdown
    eligible_count: int
    excluded_count: int
    user_review_count: int
    
    # Review complexity metrics
    dual_review_count: int
    head_office_count: int
    duplicates_count: int
    
    # Exclusion category breakdown
    exclusion_breakdown: Dict[str, int] = field(default_factory=dict)
