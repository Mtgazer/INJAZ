"""
Unit tests for Injaz business rules engine (injaz.rules).
Tests head-office detection, confirmed exclusion categories, contextual protection
for legitimate purchases (contracting, equipment rent, materials), multi-tier classification,
and decoupled user-review requirements.
"""
import pytest
from injaz.rules import (
    BusinessRulesEngine,
    is_head_office_project,
    DEFAULT_HEAD_OFFICE_PATTERNS,
)
from injaz.models import (
    InclusionEligibility,
    ExclusionCategory,
    ExtractionStatus,
    UserDecision,
    ExportStatus,
)


class TestHeadOfficeDetection:
    def test_standard_head_office_patterns(self):
        assert is_head_office_project("مركز رئيسي") is True
        assert is_head_office_project("المركز الرئيسي") is True
        assert is_head_office_project("المركز الرئيسي لصيل العقارية") is True
        assert is_head_office_project("مركز رئيسي لصيل") is True

    def test_spaced_and_variant_characters(self):
        assert is_head_office_project("مركز ا لرئيسي لصيل ا لعقا ر ية") is True
        assert is_head_office_project(" المركز   الرئيسي  ") is True

    def test_non_head_office_projects(self):
        assert is_head_office_project("صيل 13") is False
        assert is_head_office_project("صيل 14") is False
        assert is_head_office_project("صيل 16") is False
        assert is_head_office_project("مشروع برج الياسمين") is False
        assert is_head_office_project("") is False
        assert is_head_office_project(None) is False

    def test_configurable_patterns(self):
        custom_patterns = ["المقر العام بالرياض", "الإدارة التنفيذية"]
        assert is_head_office_project("المقر العام بالرياض", custom_patterns) is True
        assert is_head_office_project("الإدارة التنفيذية", custom_patterns) is True
        assert is_head_office_project("مركز رئيسي", custom_patterns) is False


class TestConfirmedExclusionCategories:
    @pytest.fixture
    def rules_engine(self):
        return BusinessRulesEngine()

    def test_vat_refund_exclusion(self, rules_engine):
        desc = "إسترداد ضريبة القيمة المضافة للربع الرابع لعام 2025"
        cat, reason = rules_engine.match_exclusion(desc, "المركز الرئيسي")
        assert cat == ExclusionCategory.VAT_REFUND
        assert "استرداد ضريبة" in reason

    def test_rent_payment_exclusion(self, rules_engine):
        desc = "سداد إيجار مقر إداري للشركة عن الربع الأول"
        cat, reason = rules_engine.match_exclusion(desc, "المركز الرئيسي")
        assert cat == ExclusionCategory.RENT_PAYMENT
        assert "إيجار" in reason

    def test_electricity_meter_bill_exclusion(self, rules_engine):
        desc = "سداد فاتورة عداد الكهرباء رقم 3001234567"
        cat, reason = rules_engine.match_exclusion(desc, "صيل 14")
        assert cat == ExclusionCategory.ELECTRICITY_BILL
        assert "فواتير وعدادات الكهرباء" in reason

    def test_general_bill_payment_exclusion(self, rules_engine):
        desc = "سداد فاتورة عامة للخدمات الإلكترونية"
        cat, reason = rules_engine.match_exclusion(desc, "صيل 13")
        assert cat == ExclusionCategory.GENERAL_BILL
        assert "سداد فواتير عامة" in reason

    def test_fuel_expense_exclusion(self, rules_engine):
        desc = "وقود السيارة الإلنترا لمتابعة المواقع"
        cat, reason = rules_engine.match_exclusion(desc, "المركز الرئيسي")
        assert cat == ExclusionCategory.FUEL_EXPENSE

        desc2 = "بنزين للمولد الاحتياطي"
        cat2, _ = rules_engine.match_exclusion(desc2, "صيل 13")
        assert cat2 == ExclusionCategory.FUEL_EXPENSE

    def test_head_office_office_supplies_exclusion(self, rules_engine):
        desc = "أدوات مكتبية ورق تصوير وأقلام للمقر"
        cat, reason = rules_engine.match_exclusion(desc, "المركز الرئيسي")
        assert cat == ExclusionCategory.HEAD_OFFICE_ADMIN
        assert "مهمات ومصروفات إدارية" in reason


class TestLegitimatePurchasesWithMisleadingKeywords:
    @pytest.fixture
    def rules_engine(self):
        return BusinessRulesEngine()

    def test_electrical_contracting_not_excluded_as_electricity_bill(self, rules_engine):
        # Electrical contracting contains 'كهرب' but must NEVER be classified as electricity bill
        desc = "مؤسسة مقاولات أعمال الكهرباء والتمديدات فاتورة 401"
        cat, _ = rules_engine.match_exclusion(desc, "صيل 16")
        assert cat is None  # Legitimate project purchase!

        desc2 = "دفعة أعمال الكهرباء للدور الأول عظم"
        cat2, _ = rules_engine.match_exclusion(desc2, "صيل 13")
        assert cat2 is None

    def test_equipment_rental_not_excluded_as_facility_rent(self, rules_engine):
        # Scaffolding and equipment rentals contain 'إيجار' but must NOT be classified as facility rent
        desc = "سداد إيجار سقالات لمشروع صيل 13"
        cat, _ = rules_engine.match_exclusion(desc, "صيل 13")
        assert cat is None  # Legitimate purchase, not office rent!

        desc2 = "إيجار معدات خرسانة وكرين"
        cat2, _ = rules_engine.match_exclusion(desc2, "صيل 14")
        assert cat2 is None

    def test_materials_purchase_with_verb_sadad_not_excluded(self, rules_engine):
        # 'سداد' appears in legitimate purchases, must not trigger general bill exclusion
        desc = "سداد دفعة شراء حديد تسليح لمشروع صيل 16 فاتورة 882"
        cat, _ = rules_engine.match_exclusion(desc, "صيل 16")
        assert cat is None

    def test_project_office_supplies_non_head_office_not_excluded(self, rules_engine):
        # Office supplies in an actual project (not head office) is not auto-excluded
        desc = "أدوات مكتبية لمكتب الموقع الميداني"
        cat, _ = rules_engine.match_exclusion(desc, "صيل 16")
        assert cat is None  # Only Head Office admin is auto-excluded


class TestMultiTierClassification:
    @pytest.fixture
    def rules_engine(self):
        return BusinessRulesEngine()

    def test_clean_project_purchase(self, rules_engine):
        eligibility, ex_cat, reason, decision, exp_status = rules_engine.classify_transaction(
            raw_desc="شراء خرسانة جاهزة من شركة الخليج 4490",
            project_str="صيل 16",
            extraction_status=ExtractionStatus.VALIDATED,
            is_single_digit_invoice=False
        )
        assert eligibility == InclusionEligibility.ELIGIBLE_FOR_INCLUSION
        assert ex_cat is None
        assert decision == UserDecision.NOT_APPLICABLE
        assert exp_status == ExportStatus.READY_TO_WRITE

    def test_head_office_exclusion_takes_precedence_over_review(self, rules_engine):
        # Head office rent is excluded by rule first
        eligibility, ex_cat, reason, decision, exp_status = rules_engine.classify_transaction(
            raw_desc="سداد إيجار مقر إداري",
            project_str="المركز الرئيسي",
            extraction_status=ExtractionStatus.VALIDATED,
            is_single_digit_invoice=False
        )
        assert eligibility == InclusionEligibility.EXCLUDED_BY_RULE
        assert ex_cat == ExclusionCategory.RENT_PAYMENT
        assert exp_status == ExportStatus.SKIPPED

    def test_head_office_non_excluded_requires_user_review(self, rules_engine):
        # Head office project appraisal (legitimate expense) requires user decision
        eligibility, ex_cat, reason, decision, exp_status = rules_engine.classify_transaction(
            raw_desc="أتعاب تقييم عقاري لمشروع صيل 105",
            project_str="المركز الرئيسي",
            extraction_status=ExtractionStatus.VALIDATED,
            is_single_digit_invoice=False
        )
        assert eligibility == InclusionEligibility.REQUIRES_USER_REVIEW
        assert ex_cat is None
        assert decision == UserDecision.PENDING
        assert exp_status == ExportStatus.HELD_PENDING_REVIEW

    def test_single_digit_invoice_requires_user_review(self, rules_engine):
        # Contractor single-digit invoice (e.g. 8) requires visual confirmation
        eligibility, ex_cat, reason, decision, exp_status = rules_engine.classify_transaction(
            raw_desc="مؤسسة سعود بن معجب للمقاولات فاتورة رقم 8 (الدفعة الرابعة)",
            project_str="صيل 16",
            extraction_status=ExtractionStatus.MANUAL_REVIEW,
            is_single_digit_invoice=True,
            extraction_error_note="Single-digit invoice number requires manual field confirmation"
        )
        assert eligibility == InclusionEligibility.REQUIRES_USER_REVIEW
        assert decision == UserDecision.PENDING
        assert exp_status == ExportStatus.HELD_PENDING_REVIEW

    def test_technical_manual_review_independent_from_commercial_eligibility(self, rules_engine):
        # A valid project purchase with extraction uncertainty remains commercially ELIGIBLE_FOR_INCLUSION,
        # but its export is HELD_PENDING_REVIEW until fields are verified.
        eligibility, ex_cat, reason, decision, exp_status = rules_engine.classify_transaction(
            raw_desc="شراء مواد متنوعة لمشروع صيل 14",
            project_str="صيل 14",
            extraction_status=ExtractionStatus.MANUAL_REVIEW,
            is_single_digit_invoice=False,
            extraction_error_note="Font-spaced supplier name"
        )
        assert eligibility == InclusionEligibility.ELIGIBLE_FOR_INCLUSION
        assert exp_status == ExportStatus.HELD_PENDING_REVIEW
