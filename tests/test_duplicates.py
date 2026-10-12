"""
Unit tests for duplicate detection preparation in Injaz (injaz.duplicates).
Tests deterministic composite key generation, whitespace/Arabic normalization,
batch collision detection, and external existing-key matching.
"""
import pytest
from injaz.duplicates import (
    generate_duplicate_key,
    evaluate_batch_duplicates,
    check_record_against_existing_keys,
)
from injaz.models import TransactionRecord, DuplicateStatus


class TestDuplicateKeyGeneration:
    def test_key_format_and_determinism(self):
        key1 = generate_duplicate_key(
            date="2026-04-15",
            invoice_number="4206",
            supplier_name="شركة الأعمار التجارية",
            tax_amount=240.0,
            project="صيل 16"
        )
        key2 = generate_duplicate_key(
            date="2026-04-15",
            invoice_number="4206",
            supplier_name="  شركة   الأعمار   التجارية  ",
            tax_amount=240.0000,
            project="صيل 16"
        )
        assert key1 == key2
        assert "2026-04-15" in key1
        assert "4206" in key1
        assert "240.00" in key1

    def test_handling_missing_fields(self):
        key = generate_duplicate_key(
            date="",
            invoice_number=None,
            supplier_name=None,
            tax_amount=None,
            project=""
        )
        assert "NO_INV" in key
        assert "NO_SUPP" in key
        assert "0.00" in key


class TestBatchDuplicateEvaluation:
    def test_no_duplicates_in_clean_batch(self):
        r1 = TransactionRecord(
            page_number=1, record_index=1, date="2026-04-15", transaction_type="قيد",
            raw_description="توريد 1", reference="1001", debit=100.0, credit=0.0,
            balance="100", project="صيل 16", invoice_number="INV-1", supplier_name="مورد أ",
            tax_amount=100.0
        )
        r2 = TransactionRecord(
            page_number=1, record_index=2, date="2026-04-16", transaction_type="قيد",
            raw_description="توريد 2", reference="1002", debit=200.0, credit=0.0,
            balance="300", project="صيل 16", invoice_number="INV-2", supplier_name="مورد ب",
            tax_amount=200.0
        )
        dup_count = evaluate_batch_duplicates([r1, r2])
        assert dup_count == 0
        assert r1.duplicate_status == DuplicateStatus.UNIQUE
        assert r2.duplicate_status == DuplicateStatus.UNIQUE

    def test_duplicate_detected_in_batch(self):
        r1 = TransactionRecord(
            page_number=1, record_index=1, date="2026-04-15", transaction_type="قيد",
            raw_description="توريد 1", reference="1001", debit=100.0, credit=0.0,
            balance="100", project="صيل 16", invoice_number="INV-1", supplier_name="مورد أ",
            tax_amount=100.0
        )
        r2 = TransactionRecord(
            page_number=2, record_index=20, date="2026-04-15", transaction_type="قيد",
            raw_description="توريد 1 مكرر", reference="1025", debit=100.0, credit=0.0,
            balance="500", project="صيل 16", invoice_number="INV-1", supplier_name="مورد أ",
            tax_amount=100.0
        )
        dup_count = evaluate_batch_duplicates([r1, r2])
        assert dup_count == 1
        assert r1.duplicate_status == DuplicateStatus.UNIQUE
        assert r2.duplicate_status == DuplicateStatus.POTENTIAL_DUPLICATE


class TestExternalExistingKeysCheck:
    def test_record_collision_with_existing_database(self):
        existing_keys = {
            "2026-04-15|صيل16|INV-99|موردسابق|500.00"
        }
        r = TransactionRecord(
            page_number=1, record_index=1, date="2026-04-15", transaction_type="قيد",
            raw_description="توريد", reference="1001", debit=500.0, credit=0.0,
            balance="500", project="صيل 16", invoice_number="INV-99", supplier_name="مورد سابق",
            tax_amount=500.0
        )
        is_dup = check_record_against_existing_keys(r, existing_keys)
        assert is_dup is True
        assert r.duplicate_status == DuplicateStatus.POTENTIAL_DUPLICATE

    def test_unique_record_does_not_collide(self):
        existing_keys = {
            "2026-04-15|صيل16|INV-99|موردسابق|500.00"
        }
        r = TransactionRecord(
            page_number=1, record_index=1, date="2026-04-15", transaction_type="قيد",
            raw_description="توريد جديد", reference="1002", debit=500.0, credit=0.0,
            balance="500", project="صيل 16", invoice_number="INV-100", supplier_name="مورد جديد",
            tax_amount=500.0
        )
        is_dup = check_record_against_existing_keys(r, existing_keys)
        assert is_dup is False
        assert r.duplicate_status == DuplicateStatus.UNIQUE

    def test_same_vendor_invoice_different_amounts_not_duplicate(self):
        # Different tax amounts produce distinct keys and do not collide
        r1 = TransactionRecord(
            page_number=1, record_index=1, date="2026-04-15", transaction_type="قيد",
            raw_description="توريد دفعة 1", reference="1001", debit=100.0, credit=0.0,
            balance="100", project="صيل 16", invoice_number="INV-55", supplier_name="مورد أ",
            tax_amount=100.0
        )
        r2 = TransactionRecord(
            page_number=1, record_index=2, date="2026-04-15", transaction_type="قيد",
            raw_description="توريد دفعة 2", reference="1002", debit=250.0, credit=0.0,
            balance="350", project="صيل 16", invoice_number="INV-55", supplier_name="مورد أ",
            tax_amount=250.0
        )
        dup_count = evaluate_batch_duplicates([r1, r2])
        assert dup_count == 0
        assert r1.duplicate_key != r2.duplicate_key
        assert r1.duplicate_status == DuplicateStatus.UNIQUE
        assert r2.duplicate_status == DuplicateStatus.UNIQUE

    def test_missing_invoice_records_do_not_falsely_collide(self):
        # Missing invoice records (e.g. utility bills or VAT refunds) should not falsely collide
        r1 = TransactionRecord(
            page_number=1, record_index=1, date="2026-04-15", transaction_type="قيد",
            raw_description="فاتورة هاتف", reference="1001", debit=50.0, credit=0.0,
            balance="50", project="صيل 16", invoice_number=None, supplier_name="شركة الاتصالات",
            tax_amount=50.0
        )
        r2 = TransactionRecord(
            page_number=1, record_index=2, date="2026-04-15", transaction_type="قيد",
            raw_description="فاتورة هاتف خط آخر", reference="1002", debit=50.0, credit=0.0,
            balance="100", project="صيل 16", invoice_number=None, supplier_name="شركة الاتصالات",
            tax_amount=50.0
        )
        dup_count = evaluate_batch_duplicates([r1, r2])
        assert dup_count == 0
        assert r1.duplicate_status == DuplicateStatus.UNIQUE
        assert r2.duplicate_status == DuplicateStatus.UNIQUE

    def test_potential_duplicates_are_never_silently_discarded(self):
        # The engine must preserve both records in the batch for human review
        r1 = TransactionRecord(
            page_number=3, record_index=93, date="2026-05-02", transaction_type="قيد",
            raw_description="دار التغيير للمقاولات 2004", reference="3241", debit=58.70, credit=0.0,
            balance="58.70", project="صيل 14", invoice_number="2004", supplier_name="دار التغيير",
            tax_amount=58.70
        )
        r2 = TransactionRecord(
            page_number=4, record_index=97, date="2026-05-02", transaction_type="قيد",
            raw_description="دار التغيير للمقاولات 2004", reference="3310", debit=58.70, credit=0.0,
            balance="117.40", project="صيل 14", invoice_number="2004", supplier_name="دار التغيير",
            tax_amount=58.70
        )
        batch = [r1, r2]
        dup_count = evaluate_batch_duplicates(batch)
        assert dup_count == 1
        assert len(batch) == 2  # Neither record is deleted or discarded
        assert batch[0].duplicate_status == DuplicateStatus.UNIQUE
        assert batch[1].duplicate_status == DuplicateStatus.POTENTIAL_DUPLICATE
