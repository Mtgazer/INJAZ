"""
Normalization and parsing utilities for Injaz (إنجاز).
Handles Arabic text normalization, financial numeric parsing, and invoice extraction.
"""
import re
import unicodedata
from typing import Optional, Tuple


def normalize_arabic_text(text: Optional[str]) -> str:
    """
    Normalizes Arabic text by converting presentation forms to standard Unicode,
    stripping private-use glyphs (e.g. \\ue900), and collapsing multiple spaces.
    """
    if not text:
        return ""
    norm = unicodedata.normalize('NFKC', text)
    norm = norm.replace('\ue900', '')
    norm = re.sub(r'\s+', ' ', norm).strip()
    return norm


def parse_numeric_amount(raw_text: str) -> Optional[float]:
    """
    Safely parses a financial number from raw text.
    Preserves legitimate negative signs.
    Treats isolated placeholder hyphens ('-', '—', '–') as 0.0 only when no digits exist.
    Returns None if text cannot be parsed as a numeric value.
    """
    if not raw_text:
        return 0.0
    
    clean = raw_text.replace('\ue900', '').strip()
    
    # Isolated placeholder hyphen
    if clean in ('-', '—', '–'):
        return 0.0
        
    # Check for negative value format: '- 123.45' or '-123.45' or '(123.45)'
    is_negative = False
    if clean.startswith('-') or clean.startswith('—') or (clean.startswith('(') and clean.endswith(')')):
        is_negative = True
        
    clean_num = clean.replace(',', '').replace(' ', '')
    match = re.search(r'[-+]?\d+(?:\.\d+)?', clean_num)
    if not match:
        return None
        
    val = float(match.group(0))
    if is_negative and val > 0:
        val = -val
    return val


def compute_tax_amount(debit: float, credit: float) -> Tuple[Optional[float], Optional[str]]:
    """
    Applies the confirmed business rule:
    - Debit > 0 and Credit == 0: Tax is +Debit
    - Debit == 0 and Credit > 0: Tax is -Credit
    - Debit == 0 and Credit == 0: Requires review (returns None)
    - Debit > 0 and Credit > 0: Flag for review (returns None)
    """
    if debit > 0 and credit == 0:
        return debit, None
    elif debit == 0 and credit > 0:
        return -credit, None
    elif debit == 0 and credit == 0:
        return None, "Both Debit and Credit are zero"
    else:
        return None, f"Both Debit ({debit}) and Credit ({credit}) are nonzero"


def is_single_digit_invoice(inv_no: Optional[str]) -> bool:
    """True if invoice number is a single digit (requiring visual confirmation)."""
    return bool(inv_no and len(inv_no.strip()) == 1 and inv_no.strip().isdigit())


def extract_invoice_and_reference(
    raw_desc: str,
    col_ref: str,
    return_single_digit_flag: bool = False
) -> Tuple:
    """
    Separates invoice number, internal reference, and supplier description.
    Returns:
        (invoice_number, final_reference, clean_description) by default,
        or (invoice_number, final_reference, clean_description, is_single_digit)
        if return_single_digit_flag is True.
    """
    clean_desc = normalize_arabic_text(raw_desc)
    clean_ref = normalize_arabic_text(col_ref)
    is_single_digit = False
    
    # Check if reference touched Arabic text on boundary: e.g. 'عبق2994'
    if not clean_ref:
        m_touch = re.search(r'([^\d\s]+)(\d{4})\b', clean_desc)
        if m_touch:
            clean_ref = m_touch.group(2)
            clean_desc = clean_desc[:m_touch.start()] + m_touch.group(1) + clean_desc[m_touch.end():]
            clean_desc = clean_desc.strip()

    def _pack(inv, ref, desc, single_d):
        if return_single_digit_flag:
            return inv, ref, desc, single_d
        return inv, ref, desc

    # Explicit phrase 'فاتورة رقم X' or 'فاتوره رقم X' (handles single and multi-digit, and intra-word spacing)
    m_explicit = re.search(r'ف\s*ا\s*ت\s*و\s*ر\s*[ةه]\s*ر\s*ق\s*م\s*(\d+)|فاتور[ةه]\s*رقم\s*(\d+)', clean_desc)
    if m_explicit:
        inv = m_explicit.group(1) or m_explicit.group(2)
        if inv != clean_ref:
            if len(inv) == 1:
                is_single_digit = True
            return _pack(inv, clean_ref, clean_desc, is_single_digit)

    # Non-invoice transaction patterns
    non_invoice_patterns = [
        "إسترداد ضريبة", "استرداد ضريبة",
        "سداد إيجار", "سداد ايجار",
        "سداد فاتور كهرب", "سداد فاتورة عداد الكهرباء", "سداد فاتورة كهرب",
        "وقود", "أدوات مكتبية"
    ]
    if any(pat in clean_desc for pat in non_invoice_patterns):
        return _pack(None, clean_ref, clean_desc, False)

    # Invoice with Arabic 'ف' (e.g. '917ف', 'ف917')
    m_f = re.search(r'\b(\d{1,7})\s*ف\b|\bف\s*(\d{1,7})\b', clean_desc)
    if m_f:
        inv = m_f.group(1) or m_f.group(2)
        if inv != clean_ref:
            if len(inv) == 1:
                is_single_digit = True
            return _pack(inv, clean_ref, clean_desc, is_single_digit)

    # Standalone digits of length 2 to 6, excluding reference number and years
    all_numbers = re.findall(r'\b\d{2,6}\b', clean_desc)
    valid_invs = [n for n in all_numbers if n != clean_ref and n not in ('2025', '2026')]
    if valid_invs:
        return _pack(valid_invs[0], clean_ref, clean_desc, False)

    return _pack(None, clean_ref, clean_desc, False)


def extract_supplier_from_desc(desc: str, inv_no: Optional[str]) -> str:
    """
    Cleans description to isolate the supplier name.
    Removes invoice numbers, milestone notes in parentheses, and transaction verbs.
    """
    s = desc
    if inv_no:
        s = re.sub(rf'ف\s*ا\s*ت\s*و\s*ر\s*[ةه]\s*ر\s*ق\s*م\s*{inv_no}', '', s)
        s = re.sub(rf'فاتور[ةه]\s*رقم\s*{inv_no}', '', s)
        s = re.sub(rf'\b{inv_no}\s*ف?\b', '', s)
        s = re.sub(rf'\bف\s*{inv_no}\b', '', s)
        
    # Remove parenthesized phrases like '(بلك )' or '(الدفعة ...)' or ') الدفعة ... )'
    s = re.sub(r'[\(\)].*?[\(\)]', '', s)
    s = re.sub(r'\(.*?\)', '', s)
    
    # Remove keywords
    s = re.sub(r'\bمرتجع\b', '', s)
    s = re.sub(r'\bشراء مواد من\b', '', s)
    s = re.sub(r'\bسداد\b', '', s)
    
    return normalize_arabic_text(s)


def validate_supplier_field(supplier: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validates extracted supplier name for completeness and font rendering artifacts.
    Checks for:
    - Missing or insufficient supplier name
    - Font-spaced Arabic characters (isolated single letters with whitespace between them)
    - Residual reference bleed (e.g. 'عبق') or unmatched punctuation artifacts
    Does NOT modify the original string (no destructive global collapsing).
    Returns (is_valid, issue_description).
    """
    if not supplier or len(supplier.strip()) < 3:
        return False, "Missing or insufficient supplier name"
        
    norm_supp = normalize_arabic_text(supplier)
    
    # Check for isolated Arabic letters (font spacing artifact from PDF rendering)
    if re.search(r'\b[أ-ي]\s+[أ-ي]\b', norm_supp):
        return False, "Supplier name contains font-spaced Arabic glyph artifacts"
        
    # Check for residual reference tokens or unmatched punctuation
    if any(tok in norm_supp for tok in ('عبق', ') ف', 'ف )', '..')):
        return False, "Supplier name contains residual reference or punctuation artifacts"
        
    return True, None
