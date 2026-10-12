"""
Unit tests for Injaz normalizer module (injaz.normalizer).
Tests Arabic text normalization, numeric amount parsing, tax amount rules,
single-digit invoice detection, and invoice/supplier separation.
"""
import pytest
from injaz.normalizer import (
    normalize_arabic_text,
    parse_numeric_amount,
    compute_tax_amount,
    is_single_digit_invoice,
    extract_invoice_and_reference,
    extract_supplier_from_desc,
    validate_supplier_field,
)


class TestArabicTextNormalization:
    def test_presentation_forms_and_ligatures(self):
        # Arabic presentation forms should be normalized via NFKC
        raw = "اﻟﻤﺴﺘﺤﻘﺔ اﻟﻤﻀﺎﻓﺔ \ue900"
        norm = normalize_arabic_text(raw)
        assert "\ue900" not in norm
        assert "المستحقة" in norm
        assert "المضافة" in norm

    def test_whitespace_collapse(self):
        raw = "   مشروع    صيل    16   "
        assert normalize_arabic_text(raw) == "مشروع صيل 16"

    def test_empty_and_none_text(self):
        assert normalize_arabic_text("") == ""
        assert normalize_arabic_text(None) == ""


class TestNumericAmountParsing:
    def test_positive_amounts(self):
        assert parse_numeric_amount("1,234.56") == 1234.56
        assert parse_numeric_amount("500") == 500.0

    def test_currency_symbol_removal(self):
        assert parse_numeric_amount("\ue900 58.70") == 58.70
        assert parse_numeric_amount("1,000.00 \ue900") == 1000.00

    def test_isolated_hyphen_placeholders(self):
        # Isolated hyphen placeholder in statement means 0.0
        assert parse_numeric_amount("-") == 0.0
        assert parse_numeric_amount("—") == 0.0
        assert parse_numeric_amount("–") == 0.0

    def test_legitimate_negative_amounts(self):
        # Must preserve legitimate negative signs
        assert parse_numeric_amount("- 415,264.69") == -415264.69
        assert parse_numeric_amount("-50.00") == -50.00
        assert parse_numeric_amount("(13.50)") == -13.50
        assert parse_numeric_amount("— 202,597.51") == -202597.51

    def test_zero_and_empty_inputs(self):
        assert parse_numeric_amount("0.00") == 0.0
        assert parse_numeric_amount("0") == 0.0
        assert parse_numeric_amount("") == 0.0
        assert parse_numeric_amount(None) == 0.0

    def test_invalid_non_numeric_input(self):
        assert parse_numeric_amount("نص غير رقمي") is None


class TestTaxAmountComputation:
    def test_positive_debit_produces_positive_tax(self):
        tax, err = compute_tax_amount(58.70, 0.00)
        assert tax == 58.70
        assert err is None

    def test_positive_credit_produces_negative_tax(self):
        tax, err = compute_tax_amount(0.00, 13.50)
        assert tax == -13.50
        assert err is None

    def test_large_credit_vat_refund(self):
        tax, err = compute_tax_amount(0.00, 171435.33)
        assert tax == -171435.33
        assert err is None

    def test_both_zero_requires_review(self):
        tax, err = compute_tax_amount(0.00, 0.00)
        assert tax is None
        assert "zero" in err.lower()

    def test_both_nonzero_requires_review(self):
        tax, err = compute_tax_amount(100.00, 50.00)
        assert tax is None
        assert "nonzero" in err.lower()


class TestSingleDigitInvoiceDetection:
    def test_single_digits(self):
        assert is_single_digit_invoice("6") is True
        assert is_single_digit_invoice("7") is True
        assert is_single_digit_invoice("8") is True
        assert is_single_digit_invoice("9") is True

    def test_multi_digits_and_none(self):
        assert is_single_digit_invoice("1462") is False
        assert is_single_digit_invoice("10") is False
        assert is_single_digit_invoice(None) is False
        assert is_single_digit_invoice("") is False


class TestInvoiceAndReferenceExtraction:
    def test_multi_digit_invoice(self):
        desc = "دار التغيير للمقاولات 1462"
        ref = "3105"
        inv, final_ref, clean_desc, single_d = extract_invoice_and_reference(desc, ref, return_single_digit_flag=True)
        assert inv == "1462"
        assert final_ref == "3105"
        assert single_d is False

    def test_invoice_with_arabic_fa(self):
        desc = "شركة ليفت هوم للمصاعد 917ف"
        ref = "3019"
        inv, final_ref, clean_desc, single_d = extract_invoice_and_reference(desc, ref, return_single_digit_flag=True)
        assert inv == "917"
        assert final_ref == "3019"
        assert single_d is False

    def test_single_digit_invoice_with_fa(self):
        desc = "مؤسسة سعود بن معجب للمقاولات ف 9"
        ref = "3365"
        inv, final_ref, clean_desc, single_d = extract_invoice_and_reference(desc, ref, return_single_digit_flag=True)
        assert inv == "9"
        assert final_ref == "3365"
        assert single_d is True

    def test_explicit_invoice_phrase_with_intra_word_spacing(self):
        # PDF font spacing: 'فاتو رة ر قم 8'
        desc = "مؤسسة سعو د بن معجب للمقا و لا ت فاتو رة ر قم 8 (الدفعة الرابعة)"
        ref = "3462"
        inv, final_ref, clean_desc, single_d = extract_invoice_and_reference(desc, ref, return_single_digit_flag=True)
        assert inv == "8"
        assert final_ref == "3462"
        assert single_d is True

    def test_attached_reference_at_boundary(self):
        # Touching boundary between Arabic text and 4-digit reference
        desc = "الأعمار التجارية 4206 عبق2994"
        ref = ""
        inv, final_ref, clean_desc = extract_invoice_and_reference(desc, ref)
        assert inv == "4206"
        assert final_ref == "2994"
        assert "2994" not in clean_desc

    def test_non_invoice_vat_refund(self):
        desc = "إسترداد ضريبة القيمة المضافة للربع الرابع لعام 2025"
        ref = "3125"
        inv, final_ref, clean_desc = extract_invoice_and_reference(desc, ref)
        assert inv is None
        assert final_ref == "3125"

    def test_non_invoice_utility_bill(self):
        desc = "سداد فاتورة عداد الكهرباء رقم 3001234567"
        ref = "3110"
        inv, final_ref, clean_desc = extract_invoice_and_reference(desc, ref)
        assert inv is None


class TestSupplierExtraction:
    def test_supplier_cleaning_standard(self):
        desc = "شراء مواد من مؤسسة الأعمار التجارية 4206"
        supp = extract_supplier_from_desc(desc, "4206")
        assert "4206" not in supp
        assert "شراء مواد من" not in supp
        assert "الأعمار التجارية" in supp

    def test_supplier_cleaning_with_milestones_and_parentheses(self):
        desc = "مؤسسة سعود بن معجب للمقاولات فاتورة رقم 8 (الدفعة الرابعة سقف الدور الأرضي) (عظم)"
        supp = extract_supplier_from_desc(desc, "8")
        assert "8" not in supp
        assert "فاتورة رقم" not in supp
        assert "الدفعة" not in supp
        assert "مؤسسة سعود بن معجب للمقاولات" in supp


class TestSupplierValidation:
    def test_clean_supplier_name(self):
        valid, err = validate_supplier_field("مؤسسة الأعمار التجارية")
        assert valid is True
        assert err is None

    def test_font_spaced_supplier_name_flagged_uncertain(self):
        # Letters with spaces between them (e.g. 'ا لأعما ر') must be flagged as uncertain
        valid, err = validate_supplier_field("ا لأعما ر ا لتجا ر ية")
        assert valid is False
        assert "font-spaced" in err.lower()

    def test_residual_reference_or_punctuation_flagged(self):
        valid, err = validate_supplier_field("الأعمار التجارية عبق")
        assert valid is False
        assert "residual" in err.lower()

    def test_missing_or_too_short_supplier(self):
        assert validate_supplier_field("")[0] is False
        assert validate_supplier_field(None)[0] is False
        assert validate_supplier_field("أ")[0] is False
