"""
Injaz PDF Extraction Engine — Phase 2 Core Engine.
Extracts financial transactions from Arabic PDF account statements using
coordinate-aware layout analysis and delegates to normalizer and rules engine.
"""
import re
from typing import List, Dict, Any, Optional
import pymupdf

from injaz.models import (
    TransactionRecord,
    ExtractionStatus,
    InclusionEligibility,
)
from injaz.normalizer import (
    normalize_arabic_text,
    parse_numeric_amount,
    compute_tax_amount,
    extract_invoice_and_reference,
    extract_supplier_from_desc,
    validate_supplier_field,
)
from injaz.rules import (
    BusinessRulesEngine,
    is_head_office_project,
    DEFAULT_HEAD_OFFICE_PATTERNS,
)


# Column bounding horizontal ranges (in points) for standard 595pt width statement
COLUMNS = {
    'project': (50.0, 85.0),
    'balance': (80.0, 135.0),
    'credit': (130.0, 175.0),
    'debit': (170.0, 220.0),
    'reference': (215.0, 255.0),
    'description': (245.0, 480.0),
    'type': (470.0, 500.0),
    'date': (495.0, 540.0)
}


class PDFStatementExtractor:
    """
    Reads an Arabic financial statement PDF and extracts structured TransactionRecords.
    """
    def __init__(
        self,
        pdf_path: str,
        head_office_patterns: Optional[List[str]] = None,
        rules_engine: Optional[BusinessRulesEngine] = None
    ):
        self.pdf_path = pdf_path
        self.head_office_patterns = head_office_patterns or DEFAULT_HEAD_OFFICE_PATTERNS
        self.rules_engine = rules_engine or BusinessRulesEngine(
            head_office_patterns=self.head_office_patterns
        )
        
    def extract_transactions(self) -> List[TransactionRecord]:
        doc = pymupdf.open(self.pdf_path)
        records: List[TransactionRecord] = []
        
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            words = page.get_text("words")
            
            # Determine table vertical limits
            min_y = 260.0 if page_idx == 0 else 22.0
            # On page 6 (index 5), table summary/closing balance starts at y=705
            max_y = 705.0 if page_idx == 5 else 795.0
            
            table_words = [w for w in words if min_y <= w[1] <= max_y]
            if not table_words:
                continue
                
            # Date anchors in date column [495, 540]
            date_words = [w for w in table_words if 495 <= w[0] <= 540 and re.match(r'^\d{4}-\d{2}-', w[4])]
            date_words.sort(key=lambda w: w[1])
            
            for i, dw in enumerate(date_words):
                y_top = dw[1] - 3.5
                y_bottom = date_words[i+1][1] - 3.5 if i + 1 < len(date_words) else max_y
                row_words = [w for w in table_words if y_top <= w[1] < y_bottom]
                
                # Check for closing balance summary rows on final page
                if any("المجموع" in normalize_arabic_text(w[4]) or "الختامي" in normalize_arabic_text(w[4]) for w in row_words):
                    continue
                    
                cols: Dict[str, List[Any]] = {k: [] for k in COLUMNS}
                for w in row_words:
                    x_mid = (w[0] + w[2]) / 2.0
                    matched = False
                    for c_name, (x0, x1) in COLUMNS.items():
                        if x0 - 2.5 <= x_mid <= x1 + 2.5:
                            cols[c_name].append(w)
                            matched = True
                            break
                    if not matched:
                        closest = min(COLUMNS.keys(), key=lambda c: min(abs(x_mid - COLUMNS[c][0]), abs(x_mid - COLUMNS[c][1])))
                        cols[closest].append(w)
                        
                # Date
                d_parts = [w[4] for w in sorted(cols['date'], key=lambda w: w[1])]
                raw_date = "".join(d_parts)
                m_dt = re.search(r'\d{4}-\d{2}-\d{2}', raw_date)
                date_str = m_dt.group(0) if m_dt else raw_date
                
                # Type
                t_words = sorted(cols['type'], key=lambda w: (w[1], w[0]))
                type_str = normalize_arabic_text(" ".join([w[4] for w in t_words]))
                
                # Debit & Credit
                debit_raw = " ".join([w[4] for w in sorted(cols['debit'], key=lambda w: (w[1], w[0]))])
                credit_raw = " ".join([w[4] for w in sorted(cols['credit'], key=lambda w: (w[1], w[0]))])
                debit_val = parse_numeric_amount(debit_raw) or 0.0
                credit_val = parse_numeric_amount(credit_raw) or 0.0
                
                # Balance
                bal_words = sorted(cols['balance'], key=lambda w: (w[1], w[0]))
                balance_str = normalize_arabic_text(" ".join([w[4] for w in bal_words]))
                
                # Project
                p_words = sorted(cols['project'], key=lambda w: (w[1], -w[0]))
                project_str = normalize_arabic_text(" ".join([w[4] for w in p_words]))
                
                # Description (sort lines by y, words RTL)
                desc_lines: Dict[int, List[Any]] = {}
                for w in cols['description']:
                    ly = round(w[1] / 6.0) * 6
                    desc_lines.setdefault(ly, []).append(w)
                sorted_desc_words = []
                for ly in sorted(desc_lines.keys()):
                    sorted_desc_words.extend(sorted(desc_lines[ly], key=lambda w: w[0], reverse=True))
                raw_desc_str = normalize_arabic_text(" ".join([w[4] for w in sorted_desc_words]))
                
                # Reference
                ref_words = sorted(cols['reference'], key=lambda w: (w[1], w[0]))
                col_ref_str = normalize_arabic_text(" ".join([w[4] for w in ref_words]))
                
                # Separate invoice and reference
                inv_res = extract_invoice_and_reference(raw_desc_str, col_ref_str, return_single_digit_flag=True)
                inv_no = inv_res[0]
                final_ref = inv_res[1]
                desc_clean = inv_res[2]
                is_single_digit = inv_res[3]
                
                supplier = extract_supplier_from_desc(desc_clean, inv_no)
                
                # Tax amount calculation
                tax_amt, tax_err = compute_tax_amount(debit_val, credit_val)
                
                # 1. Technical Extraction Status & Multi-Field Validation
                review_reasons: List[str] = []
                is_tax_valid = True
                is_inv_valid = True
                is_supp_valid = True

                if tax_err:
                    is_tax_valid = False
                    review_reasons.append(tax_err)

                if not inv_no:
                    is_inv_valid = False
                    review_reasons.append("No identifiable invoice number in description")
                elif is_single_digit:
                    is_inv_valid = False
                    review_reasons.append("Single-digit invoice number requires manual field confirmation")

                supp_valid, supp_err = validate_supplier_field(supplier)
                if not supp_valid:
                    is_supp_valid = False
                    if supp_err:
                        review_reasons.append(supp_err)

                if review_reasons:
                    ext_status = ExtractionStatus.MANUAL_REVIEW
                    ext_reason = " | ".join(review_reasons)
                else:
                    ext_status = ExtractionStatus.VALIDATED
                    ext_reason = None
                    
                # 2. Business Inclusion Eligibility (via rules engine)
                eligibility, ex_cat, reason, decision, exp_status = self.rules_engine.classify_transaction(
                    raw_desc=raw_desc_str,
                    project_str=project_str,
                    extraction_status=ext_status,
                    is_single_digit_invoice=is_single_digit,
                    extraction_error_note=ext_reason
                )
                    
                records.append(TransactionRecord(
                    page_number=page_idx + 1,
                    record_index=len(records) + 1,
                    date=date_str,
                    transaction_type=type_str,
                    raw_description=raw_desc_str,
                    reference=final_ref,
                    debit=debit_val,
                    credit=credit_val,
                    balance=balance_str,
                    project=project_str,
                    invoice_number=inv_no,
                    supplier_name=supplier,
                    tax_amount=tax_amt,
                    extraction_status=ext_status,
                    inclusion_eligibility=eligibility,
                    exclusion_category=ex_cat,
                    classification_reason=reason,
                    user_decision=decision,
                    export_status=exp_status,
                    review_notes=ext_reason,
                    review_reasons=review_reasons,
                    is_invoice_valid=is_inv_valid,
                    is_tax_valid=is_tax_valid,
                    is_supplier_valid=is_supp_valid
                ))
                
        doc.close()
        return records
