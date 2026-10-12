"""
Injaz (إنجاز) — Arabic PDF to Excel Automation.
Core Extraction Engine — Phase 2.
"""
from injaz.models import (
    TransactionRecord,
    ProcessingResult,
    ExtractionStatus,
    InclusionEligibility,
    UserDecision,
    ExclusionCategory,
    DuplicateStatus,
    ExportStatus,
)
from injaz.engine import CoreExtractionEngine
from injaz.rules import BusinessRulesEngine, is_head_office_project
from injaz.normalizer import (
    normalize_arabic_text,
    parse_numeric_amount,
    compute_tax_amount,
    extract_invoice_and_reference,
)
from injaz.xlsx_exporter import XlsxExporter, XlsxExportSummary

__version__ = "1.0.1"

__all__ = [
    "TransactionRecord",
    "ProcessingResult",
    "ExtractionStatus",
    "InclusionEligibility",
    "UserDecision",
    "ExclusionCategory",
    "DuplicateStatus",
    "ExportStatus",
    "CoreExtractionEngine",
    "BusinessRulesEngine",
    "is_head_office_project",
    "normalize_arabic_text",
    "parse_numeric_amount",
    "compute_tax_amount",
    "extract_invoice_and_reference",
    "XlsxExporter",
    "XlsxExportSummary",
]
