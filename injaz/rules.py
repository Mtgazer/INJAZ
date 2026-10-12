"""
Configurable business rules and transaction classifier for Injaz (إنجاز).
Evaluates inclusion eligibility, exclusion categories, and user-review requirements.
Completely decoupled from PDF parsing logic.
"""
import re
import unicodedata
from typing import Optional, List, Tuple
from injaz.models import (
    InclusionEligibility,
    ExclusionCategory,
    UserDecision,
    ExportStatus,
    ExtractionStatus,
)


DEFAULT_HEAD_OFFICE_PATTERNS = [
    "مركز رئيسي",
    "المركز الرئيسي",
    "مركز الرئيسي",
    "المركز رئيسي",
    "المركز الرئيسي لصيل",
    "المركز الرئيسي لصيل العقارية",
    "مركز رئيسي لصيل",
    "مركز الرئيسي لصيل العقارية"
]


def is_head_office_project(project_str: str, patterns: Optional[List[str]] = None) -> bool:
    """
    Checks if a project string corresponds to the Head Office.
    Normalizes whitespace and Arabic character variants.
    """
    if not project_str:
        return False
        
    norm_proj = unicodedata.normalize('NFKC', project_str)
    compact_proj = re.sub(r'\s+', '', norm_proj)
    
    if patterns is not None:
        for p in patterns:
            compact_pat = re.sub(r'\s+', '', unicodedata.normalize('NFKC', p))
            if compact_pat in compact_proj:
                return True
        return False
        
    if "مركز" in compact_proj and "رئيسي" in compact_proj:
        return True
        
    for p in DEFAULT_HEAD_OFFICE_PATTERNS:
        compact_pat = re.sub(r'\s+', '', unicodedata.normalize('NFKC', p))
        if compact_pat in compact_proj:
            return True
    return False


class BusinessRulesEngine:
    """
    Configurable rules engine for transaction inclusion and exclusion.
    """
    def __init__(
        self,
        head_office_patterns: Optional[List[str]] = None,
        general_bill_patterns: Optional[List[str]] = None,
        electricity_bill_patterns: Optional[List[str]] = None,
        fuel_patterns: Optional[List[str]] = None,
        rent_patterns: Optional[List[str]] = None,
        vat_refund_patterns: Optional[List[str]] = None,
    ):
        self.head_office_patterns = head_office_patterns or DEFAULT_HEAD_OFFICE_PATTERNS
        self.general_bill_patterns = general_bill_patterns or [
            "سداد فاتورة اتصالات", "سداد فاتورة مياه", "سداد فاتورة هاتف",
            "سداد فاتورة انترنت", "سداد فاتورة إنترنت", "سداد فاتورة خدمة",
            "سداد فاتورة عامة", "سداد فواتير عامة"
        ]
        self.electricity_bill_patterns = electricity_bill_patterns or [
            "فاتورة كهرب", "فاتورة عداد الكهرباء", "سداد فاتور كهرب", "عداد كهرب"
        ]
        self.electricity_contracting_keywords = [
            "أعمال الكهرباء", "اعمال الكهرباء", "مقاولات الكهرباء", "مقاول الكهرباء",
            "دفعة أعمال الكهرباء", "تمديدات الكهرباء", "أعمال كهربائية", "اعمال كهربائية"
        ]
        self.fuel_patterns = fuel_patterns or ["وقود", "بنزين", "ديزل"]
        self.rent_patterns = rent_patterns or ["إيجار", "ايجار"]
        self.vat_refund_patterns = vat_refund_patterns or [
            "استرداد ضريبة", "إسترداد ضريبة", "استرداد ضريبة القيمة المضافة"
        ]

    def match_exclusion(
        self, raw_desc: str, project_str: str
    ) -> Tuple[Optional[ExclusionCategory], Optional[str]]:
        """
        Tests description and project against confirmed exclusion categories.
        Uses contextual matching to prevent false positives on legitimate purchases.
        """
        norm_desc = unicodedata.normalize('NFKC', raw_desc)
        compact_desc = re.sub(r'\s+', '', norm_desc)
        is_ho = is_head_office_project(project_str, self.head_office_patterns)
        
        # 1. VAT refund / recovery
        for pat in self.vat_refund_patterns:
            compact_pat = re.sub(r'\s+', '', pat)
            if compact_pat in compact_desc:
                return (
                    ExclusionCategory.VAT_REFUND,
                    "استرداد ضريبة القيمة المضافة من الهيئة (VAT Refund)"
                )

        # 2. Rent payments (excluding equipment / scaffolding / machinery rentals)
        equipment_keywords = ["معدات", "سقالات", "آليات", "كرين", "حفار", "خلاطة"]
        is_equipment_rent = any(
            re.sub(r'\s+', '', kw) in compact_desc for kw in equipment_keywords
        )
        if not is_equipment_rent:
            for pat in self.rent_patterns:
                compact_pat = re.sub(r'\s+', '', pat)
                if compact_pat in compact_desc and ("سداد" in compact_desc or "مقدم" in compact_desc):
                    return (
                        ExclusionCategory.RENT_PAYMENT,
                        "سداد إيجار مقر إداري (Rent Payment)"
                    )

        # 3. Electricity utility & meter bills
        # Protects contractor electrical works (e.g. 'أعمال الكهرباء')
        is_contractor_work = any(
            re.sub(r'\s+', '', kw) in compact_desc for kw in self.electricity_contracting_keywords
        )
        if not is_contractor_work:
            for pat in self.electricity_bill_patterns:
                compact_pat = re.sub(r'\s+', '', pat)
                if compact_pat in compact_desc:
                    return (
                        ExclusionCategory.ELECTRICITY_BILL,
                        "سداد فواتير وعدادات الكهرباء الخدمية (Electricity Meter Bill)"
                    )

        # 4. General bill payments
        for pat in self.general_bill_patterns:
            compact_pat = re.sub(r'\s+', '', pat)
            if compact_pat in compact_desc:
                return (
                    ExclusionCategory.GENERAL_BILL,
                    "سداد فواتير عامة مطابقة لنمط الاستبعاد (General Bill Payment)"
                )

        # 5. Fuel & vehicle / generator fuel
        for pat in self.fuel_patterns:
            compact_pat = re.sub(r'\s+', '', pat)
            if compact_pat in compact_desc:
                return (
                    ExclusionCategory.FUEL_EXPENSE,
                    "محروقات ووقود المركبات والمولدات (Fuel Expense)"
                )

        # 6. Head-Office Administrative Purchases (e.g. office supplies)
        if is_ho and ("مكتبية" in compact_desc or "ورقتصوير" in compact_desc or "مطبوعات" in compact_desc):
            return (
                ExclusionCategory.HEAD_OFFICE_ADMIN,
                "مهمات ومصروفات إدارية للمقر الرئيسي (Office Supplies)"
            )

        return None, None

    def classify_transaction(
        self,
        raw_desc: str,
        project_str: str,
        extraction_status: ExtractionStatus,
        is_single_digit_invoice: bool = False,
        extraction_error_note: Optional[str] = None
    ) -> Tuple[InclusionEligibility, Optional[ExclusionCategory], str, UserDecision, ExportStatus]:
        """
        Applies the approved multi-tier classification workflow:
        1. Evaluate explicit confirmed exclusion rules first.
        2. If Head Office and not excluded -> REQUIRES_USER_REVIEW.
        3. If extraction had uncertain fields (missing invoice, single-digit invoice, etc.) -> REQUIRES_USER_REVIEW.
        4. Clean standard project purchase -> ELIGIBLE_FOR_INCLUSION.
        """
        # Step 1: Confirmed exclusion rules
        ex_cat, ex_reason = self.match_exclusion(raw_desc, project_str)
        if ex_cat:
            return (
                InclusionEligibility.EXCLUDED_BY_RULE,
                ex_cat,
                ex_reason,
                UserDecision.NOT_APPLICABLE,
                ExportStatus.SKIPPED
            )

        # Step 2: Head Office transactions (neither auto-included nor auto-excluded)
        if is_head_office_project(project_str, self.head_office_patterns):
            return (
                InclusionEligibility.REQUIRES_USER_REVIEW,
                None,
                "معاملة مركز رئيسي تتطلب قرار المستخدم الصريح بالإدراج أو الاستبعاد",
                UserDecision.PENDING,
                ExportStatus.HELD_PENDING_REVIEW
            )

        # Step 3: Special contractor milestone payments with single-digit candidate invoices
        # Require commercial user approval (milestone payment inclusion) as well as field confirmation
        if is_single_digit_invoice:
            return (
                InclusionEligibility.REQUIRES_USER_REVIEW,
                None,
                "دفعة مقاول برقم فاتورة أحادي ومراحل إنجاز تتطلب مراجعة المستخدم التجارية وتأكيد الحقل",
                UserDecision.PENDING,
                ExportStatus.HELD_PENDING_REVIEW
            )

        # Step 4: Standard project purchase (InclusionEligibility is independent of extraction quality)
        exp_status = (
            ExportStatus.READY_TO_WRITE
            if extraction_status == ExtractionStatus.VALIDATED
            else ExportStatus.HELD_PENDING_REVIEW
        )
        return (
            InclusionEligibility.ELIGIBLE_FOR_INCLUSION,
            None,
            "مشتريات مشروع مؤكدة ومطابقة للقواعد",
            UserDecision.NOT_APPLICABLE,
            exp_status
        )
