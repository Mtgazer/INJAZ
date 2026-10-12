"""
Duplicate detection preparation and key generation for Injaz (إنجاز).
Identifies potential collision between incoming transactions and existing records.
"""
import re
import unicodedata
from typing import Optional, List, Set
from injaz.models import TransactionRecord, DuplicateStatus


def generate_duplicate_key(
    date: str,
    invoice_number: Optional[str],
    supplier_name: Optional[str],
    tax_amount: Optional[float],
    project: str
) -> str:
    """
    Creates a normalized deterministic composite key for duplicate detection.
    Normalizes Arabic supplier and project names, invoice number, and rounds tax amount.
    """
    clean_date = (date or "").strip()
    clean_inv = (invoice_number or "NO_INV").strip()
    
    # Normalize supplier and project
    norm_supp = re.sub(r'\s+', '', unicodedata.normalize('NFKC', supplier_name or "NO_SUPP"))
    norm_proj = re.sub(r'\s+', '', unicodedata.normalize('NFKC', project or "NO_PROJ"))
    
    # Round tax amount to 2 decimal places
    tax_str = f"{tax_amount:.2f}" if tax_amount is not None else "0.00"
    
    return f"{clean_date}|{norm_proj}|{clean_inv}|{norm_supp}|{tax_str}"


def evaluate_batch_duplicates(records: List[TransactionRecord]) -> int:
    """
    Evaluates duplicate status across an incoming batch of transaction records.
    Assigns duplicate_key and marks DuplicateStatus.POTENTIAL_DUPLICATE if key repeats.
    Returns the count of detected duplicates.
    """
    seen_keys: Set[str] = set()
    dup_count = 0
    
    for r in records:
        key = generate_duplicate_key(
            date=r.date,
            invoice_number=r.invoice_number,
            supplier_name=r.supplier_name,
            tax_amount=r.tax_amount,
            project=r.project
        )
        r.duplicate_key = key
        
        # We only treat clean records with invoice as collision candidates
        if r.invoice_number and key in seen_keys:
            r.duplicate_status = DuplicateStatus.POTENTIAL_DUPLICATE
            dup_count += 1
        else:
            r.duplicate_status = DuplicateStatus.UNIQUE
            if r.invoice_number:
                seen_keys.add(key)
                
    return dup_count


def check_record_against_existing_keys(
    record: TransactionRecord,
    existing_keys: Set[str]
) -> bool:
    """
    Checks if a transaction record matches any key in an existing set of keys
    (such as keys loaded from an existing Excel sheet).
    Updates record.duplicate_status if matched.
    Returns True if duplicate detected.
    """
    key = record.duplicate_key or generate_duplicate_key(
        date=record.date,
        invoice_number=record.invoice_number,
        supplier_name=record.supplier_name,
        tax_amount=record.tax_amount,
        project=record.project
    )
    record.duplicate_key = key
    if record.invoice_number and key in existing_keys:
        record.duplicate_status = DuplicateStatus.POTENTIAL_DUPLICATE
        return True
    return False
