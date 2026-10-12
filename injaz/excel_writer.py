"""
Excel Population Engine & Integrity System for Injaz (إنجاز) — Phase 3.
Safely populates validated, approved transaction records into target Excel worksheets.
Preserves existing formulas, styles, worksheets, and summary totals without modifying the source template.
"""
import os
import shutil
import tempfile
import unicodedata
import re
import datetime
from copy import copy
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set, Tuple

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.utils import get_column_letter

from injaz.models import (
    TransactionRecord,
    InclusionEligibility,
    UserDecision,
    DuplicateStatus,
    ExportStatus,
)
from injaz.duplicates import generate_duplicate_key


# =============================================================================
# Custom Exception Hierarchy
# =============================================================================

class ExcelPopulationError(Exception):
    """Base exception for all Excel population errors."""
    pass


class TemplateProtectionError(ExcelPopulationError):
    """Raised when an operation risks modifying or resolving to the source template."""
    pass


class IncompatibleTemplateError(ExcelPopulationError):
    """Raised when a workbook lacks required worksheets or column headers."""
    pass


class IneligibleExportError(ExcelPopulationError):
    """Raised when an attempt is made to export unapproved or unresolved records."""
    pass


class WorkbookValidationError(ExcelPopulationError):
    """Raised when post-generation validation of the exported workbook fails."""
    pass


# =============================================================================
# Configuration & Summary Models
# =============================================================================

@dataclass
class ColumnMapping:
    """
    Configurable header names mapping logical fields to worksheet columns.
    Defaults match the official Injaz Arabic purchases worksheet.
    """
    sequence: str = "م"
    date: str = "التاريخ"
    project: str = "المشروع"
    invoice: str = "رقم الفاتورة"
    supplier: str = "المورد"
    value: str = "القيمة"
    tax: str = "الضريبة"
    total: str = "الإجمالي"
    status: str = "الحالة"
    review: str = "المراجعه"
    excel_tax: str = "الأكسيل الضريبة"
    notes: str = "ملاحظات"


@dataclass
class ExportSummary:
    """
    Structured outcome of an Excel export operation.
    """
    total_records_submitted: int
    records_exported: int
    records_skipped_already_present: int
    records_rejected_ineligible: int
    output_path: str
    rows_appended_indices: List[int] = field(default_factory=list)
    rejection_details: List[Dict[str, Any]] = field(default_factory=list)
    skipped_duplicate_keys: List[str] = field(default_factory=list)


# =============================================================================
# Style & Helper Utilities
# =============================================================================

def normalize_header(val: Any) -> str:
    """Normalizes header text by stripping whitespace and Unicode NFKC."""
    if val is None:
        return ""
    text = str(val).strip()
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))


def copy_cell_style(source_cell, target_cell):
    """Copies formatting and styling attributes from source cell to target cell."""
    if source_cell.has_style:
        target_cell.font = copy(source_cell.font)
        target_cell.border = copy(source_cell.border)
        target_cell.fill = copy(source_cell.fill)
        target_cell.number_format = copy(source_cell.number_format)
        target_cell.protection = copy(source_cell.protection)
        target_cell.alignment = copy(source_cell.alignment)


# =============================================================================
# Core Population Engine
# =============================================================================

class ExcelPopulationEngine:
    """
    Engine for safe, fail-closed population of transaction records into Excel workbooks.
    """
    def __init__(
        self,
        column_mapping: Optional[ColumnMapping] = None,
        sheet_name: str = "تحليلي مشتريات",
        header_row: Optional[int] = 2
    ):
        self.column_mapping = column_mapping or ColumnMapping()
        self.sheet_name = sheet_name
        self.header_row = header_row

    def locate_headers(self, ws: Worksheet) -> Tuple[int, Dict[str, int]]:
        """
        Locates the header row and maps logical column keys to 1-based column indices.
        If header_row is None, scans the first 10 rows to locate the header row.
        """
        required_targets = {
            "date": normalize_header(self.column_mapping.date),
            "project": normalize_header(self.column_mapping.project),
            "invoice": normalize_header(self.column_mapping.invoice),
            "supplier": normalize_header(self.column_mapping.supplier),
            "tax": normalize_header(self.column_mapping.tax),
        }
        optional_targets = {
            "sequence": normalize_header(self.column_mapping.sequence),
            "value": normalize_header(self.column_mapping.value),
            "total": normalize_header(self.column_mapping.total),
            "status": normalize_header(self.column_mapping.status),
            "review": normalize_header(self.column_mapping.review),
            "excel_tax": normalize_header(self.column_mapping.excel_tax),
            "notes": normalize_header(self.column_mapping.notes),
        }

        search_rows = [self.header_row] if self.header_row is not None else list(range(1, 11))
        
        found_row: Optional[int] = None
        col_map: Dict[str, int] = {}

        for r in search_rows:
            row_headers: Dict[str, int] = {}
            for col_idx in range(1, ws.max_column + 1):
                raw_val = ws.cell(r, col_idx).value
                norm_val = normalize_header(raw_val)
                if norm_val:
                    row_headers[norm_val] = col_idx

            # Check if all required headers are present in this row
            if all(req in row_headers for req in required_targets.values()):
                found_row = r
                for key, target in required_targets.items():
                    col_map[key] = row_headers[target]
                for key, target in optional_targets.items():
                    if target in row_headers:
                        col_map[key] = row_headers[target]
                break

        if found_row is None:
            # Check what's missing in the expected row
            checked_r = self.header_row if self.header_row is not None else 1
            present = [normalize_header(ws.cell(checked_r, c).value) for c in range(1, ws.max_column + 1)]
            missing = [k for k, target in required_targets.items() if target not in present]
            raise IncompatibleTemplateError(
                f"Worksheet '{ws.title}' is missing required header(s): {missing}. "
                f"Checked row: {checked_r}."
            )

        return found_row, col_map

    @staticmethod
    def _is_populated_transaction_row(
        val_date: Any,
        val_proj: Any,
        val_inv: Any,
        val_supp: Any,
        val_tax: Any
    ) -> bool:
        """
        Determines whether a row represents an actual populated business transaction
        rather than a blank placeholder slot.
        A row with only a sequence number or empty fields is an empty transaction slot.
        """
        if val_date is None or str(val_date).strip() == '':
            return False

        has_proj = val_proj is not None and str(val_proj).strip() != ''
        has_inv = val_inv is not None and str(val_inv).strip() != ''
        has_supp = val_supp is not None and str(val_supp).strip() != ''
        has_tax = False
        if val_tax is not None:
            try:
                has_tax = float(val_tax) != 0.0
            except (ValueError, TypeError):
                has_tax = False

        return bool(has_proj or has_inv or has_supp or has_tax)

    def inspect_existing_state(
        self,
        ws: Worksheet,
        col_map: Dict[str, int],
        header_row_idx: int
    ) -> Tuple[int, Optional[int], Set[str], int]:
        """
        Inspects existing rows to identify:
        - last_data_row: row index of the last actual populated transaction.
        - summary_row: row index of the summary/total row (if present).
        - existing_keys: set of normalized composite keys of all existing transactions.
        - max_sequence: highest sequence number among actual populated transactions.
        """
        last_data_row = header_row_idx
        summary_row: Optional[int] = None
        existing_keys: Set[str] = set()
        max_sequence = 0

        col_date = col_map["date"]
        col_tax = col_map["tax"]
        col_proj = col_map["project"]
        col_inv = col_map["invoice"]
        col_supp = col_map["supplier"]
        col_seq = col_map.get("sequence")

        for r in range(header_row_idx + 1, ws.max_row + 1):
            val_a = str(ws.cell(r, 1).value or '')
            val_val_col = str(ws.cell(r, col_map.get("value", 6)).value or '')

            # Detect summary row (e.g. contains 'الإجمالي' or SUBTOTAL/SUM formula)
            if "الإجمالي" in val_a or "SUBTOTAL" in val_val_col or "SUM" in val_val_col:
                summary_row = r
                break

            val_date = ws.cell(r, col_date).value
            val_tax = ws.cell(r, col_tax).value
            val_inv = ws.cell(r, col_inv).value
            val_supp = ws.cell(r, col_supp).value
            val_proj = ws.cell(r, col_proj).value

            is_populated = self._is_populated_transaction_row(val_date, val_proj, val_inv, val_supp, val_tax)

            if is_populated:
                last_data_row = r
                if col_seq:
                    val_seq = ws.cell(r, col_seq).value
                    if isinstance(val_seq, int):
                        max_sequence = max(max_sequence, val_seq)

                dt_str = str(val_date)[:10]
                inv_str = str(val_inv) if val_inv is not None else None
                supp_str = str(val_supp) if val_supp is not None else None
                proj_str = str(val_proj) if val_proj is not None else ""
                try:
                    tax_num = float(val_tax) if val_tax is not None else 0.0
                except (ValueError, TypeError):
                    tax_num = 0.0
                key = generate_duplicate_key(dt_str, inv_str, supp_str, tax_num, proj_str)
                existing_keys.add(key)

        return last_data_row, summary_row, existing_keys, max_sequence

    def _generate_formulas_for_row(
        self,
        ws: Worksheet,
        col_map: Dict[str, int],
        target_row: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Determines appropriate Value and Total formulas for a newly added row
        based on the pattern of previous rows.
        """
        val_formula: Optional[str] = None
        tot_formula: Optional[str] = None
        prev_row = target_row - 1

        col_val = col_map.get("value")
        col_tax = col_map.get("tax")
        col_tot = col_map.get("total")

        if col_val and col_tax:
            prev_val = ws.cell(prev_row, col_val).value
            if isinstance(prev_val, str) and prev_val.startswith("="):
                if "[#This Row]" in prev_val or "Table" in prev_val:
                    val_formula = prev_val
                else:
                    tax_col_letter = get_column_letter(col_tax)
                    val_formula = f"={tax_col_letter}{target_row}/0.15"
            else:
                tax_col_letter = get_column_letter(col_tax)
                val_formula = f"={tax_col_letter}{target_row}/0.15"

        if col_tot and col_val and col_tax:
            prev_tot = ws.cell(prev_row, col_tot).value
            if isinstance(prev_tot, str) and prev_tot.startswith("="):
                if "[#This Row]" in prev_tot or "Table" in prev_tot:
                    tot_formula = prev_tot
                else:
                    val_col_letter = get_column_letter(col_val)
                    tax_col_letter = get_column_letter(col_tax)
                    tot_formula = f"={val_col_letter}{target_row}+{tax_col_letter}{target_row}"
            else:
                val_col_letter = get_column_letter(col_val)
                tax_col_letter = get_column_letter(col_tax)
                tot_formula = f"={val_col_letter}{target_row}+{tax_col_letter}{target_row}"

        return val_formula, tot_formula

    def export_transactions(
        self,
        template_path: str,
        output_path: str,
        records: List[TransactionRecord],
        overwrite: bool = False,
        backup_existing: bool = True,
        fail_on_ineligible: bool = False,
    ) -> ExportSummary:
        """
        Main entry point for exporting approved records to Excel.
        Enforces strict template protection, fail-closed eligibility, formula preservation,
        and post-generation validation.
        """
        if not output_path:
            raise ValueError("An explicit output_path is required.")

        abs_template = os.path.abspath(template_path)
        abs_output = os.path.abspath(output_path)

        # 1. Protection against overwriting or modifying source template
        if not os.path.exists(abs_template):
            raise FileNotFoundError(f"Source template not found: {abs_template}")

        real_template = os.path.normcase(os.path.realpath(abs_template))
        real_output = os.path.normcase(os.path.realpath(abs_output))
        if real_template == real_output:
            raise TemplateProtectionError(
                f"Output path resolves to the source template file: '{abs_output}'. "
                "The source template must NEVER be modified."
            )

        if os.path.exists(abs_output):
            if os.path.samefile(abs_template, abs_output):
                raise TemplateProtectionError("Output path is the same physical file as the source template.")
            if not overwrite:
                raise FileExistsError(
                    f"Output file already exists at '{abs_output}'. "
                    "Specify a different path or set overwrite=True."
                )

        # 2. Strict Fail-Closed Export Eligibility Verification
        eligible_records: List[TransactionRecord] = []
        rejection_details: List[Dict[str, Any]] = []

        for r in records:
            can_exp, reason = r.check_export_eligibility()
            if can_exp:
                eligible_records.append(r)
            else:
                rejection_details.append({
                    "record_index": r.record_index,
                    "date": r.date,
                    "project": r.project,
                    "invoice": r.invoice_number,
                    "reason": reason
                })
                if fail_on_ineligible:
                    raise IneligibleExportError(
                        f"Record index {r.record_index} is ineligible for export: {reason}"
                    )

        output_dir = os.path.dirname(abs_output)
        os.makedirs(output_dir, exist_ok=True)

        # 3. Create temporary file in same directory for safe validation
        temp_fd, temp_path = tempfile.mkstemp(
            prefix="injaz_export_",
            suffix=".xlsx",
            dir=output_dir
        )
        os.close(temp_fd)

        exported_count = 0
        skipped_already_present = 0
        skipped_keys: List[str] = []
        appended_rows: List[int] = []
        actually_exported_records: List[TransactionRecord] = []

        try:
            # Load template without data_only=True so formulas are retained
            wb = openpyxl.load_workbook(abs_template, data_only=False)

            if self.sheet_name not in wb.sheetnames:
                raise IncompatibleTemplateError(
                    f"Worksheet '{self.sheet_name}' not found in workbook. "
                    f"Available sheets: {wb.sheetnames}"
                )

            ws = wb[self.sheet_name]
            header_row_idx, col_map = self.locate_headers(ws)
            last_data_row, summary_row, existing_keys, max_seq = self.inspect_existing_state(
                ws, col_map, header_row_idx
            )

            # Check for Table objects to update their boundaries if rows are inserted
            table_obj = None
            if hasattr(ws, "tables"):
                for tbl in ws.tables.values():
                    table_obj = tbl
                    break

            current_insert_row = last_data_row + 1

            for rec in eligible_records:
                # Conservative duplicate prevention against existing worksheet records
                rec_key = rec.duplicate_key or generate_duplicate_key(
                    rec.date, rec.invoice_number, rec.supplier_name, rec.tax_amount, rec.project
                )

                if rec_key in existing_keys:
                    skipped_already_present += 1
                    skipped_keys.append(rec_key)
                    continue

                # Determine whether to use an existing placeholder row or insert a new row
                if summary_row is not None and current_insert_row >= summary_row:
                    target_row = summary_row

                    # Shift all merged cell ranges starting at or below summary_row
                    # to prevent openpyxl from keeping old merged coordinates on the new data row
                    if hasattr(ws, "merged_cells") and hasattr(ws.merged_cells, "ranges"):
                        for rng in list(ws.merged_cells.ranges):
                            if rng.min_row >= summary_row:
                                ws.merged_cells.ranges.remove(rng)
                                rng.shift(row_shift=1)
                                ws.merged_cells.add(rng)

                    # Must insert row before the summary row to avoid overwriting totals
                    ws.insert_rows(summary_row, 1)
                    summary_row += 1
                    
                    # Update Table boundary if Table exists
                    if table_obj and getattr(table_obj, 'ref', None):
                        m = re.match(r'([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)', table_obj.ref)
                        if m:
                            s_col, s_row, e_col, e_row = m.groups()
                            table_obj.ref = f"{s_col}{s_row}:{e_col}{int(e_row) + 1}"

                    # Copy styling and formulas from row above
                    prev_row = target_row - 1
                    for col_idx in range(1, ws.max_column + 1):
                        copy_cell_style(ws.cell(prev_row, col_idx), ws.cell(target_row, col_idx))
                    
                    val_formula, tot_formula = self._generate_formulas_for_row(ws, col_map, target_row)
                    if col_map.get("value") and val_formula:
                        ws.cell(target_row, col_map["value"]).value = val_formula
                    if col_map.get("total") and tot_formula:
                        ws.cell(target_row, col_map["total"]).value = tot_formula
                else:
                    target_row = current_insert_row

                # Populate approved values (Never overwrite existing formulas)
                # Sequence column
                # Reuse existing valid sequence number in a placeholder row,
                # or assign the next sequential number.
                col_seq = col_map.get("sequence")
                if col_seq:
                    existing_seq = ws.cell(target_row, col_seq).value
                    if (
                        isinstance(existing_seq, int)
                        and existing_seq > 0
                        and (max_seq == 0 or existing_seq == max_seq + 1)
                    ):
                        max_seq = existing_seq
                    else:
                        max_seq += 1
                        ws.cell(target_row, col_seq).value = max_seq

                # Date column
                col_date = col_map["date"]
                try:
                    dt_obj = datetime.date.fromisoformat(rec.date)
                except (ValueError, TypeError):
                    dt_obj = rec.date
                ws.cell(target_row, col_date).value = dt_obj
                ws.cell(target_row, col_date).number_format = 'yyyy-mm-dd'

                # Project column
                ws.cell(target_row, col_map["project"]).value = rec.project

                # Invoice column (integer if purely numeric, else string)
                col_inv = col_map["invoice"]
                if rec.invoice_number and rec.invoice_number.isdigit() and not (len(rec.invoice_number) > 1 and rec.invoice_number.startswith('0')):
                    ws.cell(target_row, col_inv).value = int(rec.invoice_number)
                else:
                    ws.cell(target_row, col_inv).value = rec.invoice_number

                # Supplier column
                ws.cell(target_row, col_map["supplier"]).value = rec.supplier_name

                # Tax column
                col_tax = col_map["tax"]
                ws.cell(target_row, col_tax).value = float(rec.tax_amount)
                ws.cell(target_row, col_tax).number_format = '_(* #,##0.00_);_(* \\(#,##0.00\\);_(* "-"??_);_(@_)'

                # Formula columns (Value and Total)
                # NEVER overwrite a cell if it already contains a formula!
                col_val = col_map.get("value")
                if col_val:
                    c_val = ws.cell(target_row, col_val)
                    if not (isinstance(c_val.value, str) and c_val.value.startswith('=')):
                        val_formula, _ = self._generate_formulas_for_row(ws, col_map, target_row)
                        if val_formula:
                            c_val.value = val_formula
                    c_val.number_format = '_(* #,##0.00_);_(* \\(#,##0.00\\);_(* "-"??_);_(@_)'

                col_tot = col_map.get("total")
                if col_tot:
                    c_tot = ws.cell(target_row, col_tot)
                    if not (isinstance(c_tot.value, str) and c_tot.value.startswith('=')):
                        _, tot_formula = self._generate_formulas_for_row(ws, col_map, target_row)
                        if tot_formula:
                            c_tot.value = tot_formula
                    c_tot.number_format = '_(* #,##0.00_);_(* \\(#,##0.00\\);_(* "-"??_);_(@_)'

                existing_keys.add(rec_key)
                appended_rows.append(target_row)
                actually_exported_records.append(rec)
                exported_count += 1
                current_insert_row = target_row + 1

            # Configure Excel recalculation on workbook open
            if hasattr(wb, "calculation") and wb.calculation is not None:
                wb.calculation.fullCalcOnLoad = True

            # Save temporary workbook
            wb.save(temp_path)
            wb.close()

            # 4. Rigorous Post-Generation Integrity Validation
            self._validate_generated_workbook(
                temp_path=temp_path,
                template_path=abs_template,
                sheet_name=self.sheet_name,
                col_map=col_map,
                exported_records=actually_exported_records,
                appended_rows=appended_rows,
                expected_summary_row=summary_row
            )

            # 5. Safe Finalization
            if os.path.exists(abs_output) and backup_existing:
                backup_path = abs_output + ".bak"
                shutil.copy2(abs_output, backup_path)

            # Atomic move/replace on same filesystem
            os.replace(temp_path, abs_output)

        except Exception:
            # Clean up temporary file upon any failure
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

        return ExportSummary(
            total_records_submitted=len(records),
            records_exported=exported_count,
            records_skipped_already_present=skipped_already_present,
            records_rejected_ineligible=len(rejection_details),
            output_path=abs_output,
            rows_appended_indices=appended_rows,
            rejection_details=rejection_details,
            skipped_duplicate_keys=skipped_keys
        )

    def _validate_generated_workbook(
        self,
        temp_path: str,
        template_path: str,
        sheet_name: str,
        col_map: Dict[str, int],
        exported_records: List[TransactionRecord],
        appended_rows: List[int],
        expected_summary_row: Optional[int]
    ):
        """
        Reopens and validates the temporary workbook before atomic finalization.
        Ensures sheets, formulas, data cells, and summary rows are intact.
        """
        try:
            wb_check = openpyxl.load_workbook(temp_path, data_only=False)
        except Exception as e:
            raise WorkbookValidationError(f"Generated workbook cannot be opened: {e}")

        try:
            # 1. Verify sheet names preserved from template
            wb_orig = openpyxl.load_workbook(template_path, data_only=False, read_only=True)
            orig_sheets = list(wb_orig.sheetnames)
            wb_orig.close()

            for s in orig_sheets:
                if s not in wb_check.sheetnames:
                    raise WorkbookValidationError(f"Original worksheet '{s}' was lost during population.")

            if sheet_name not in wb_check.sheetnames:
                raise WorkbookValidationError(f"Target worksheet '{sheet_name}' is missing.")

            ws = wb_check[sheet_name]

            # 2. Verify all appended rows contain the exact approved data and formula cells
            if len(exported_records) != len(appended_rows):
                raise WorkbookValidationError(
                    f"Mismatch between exported records count ({len(exported_records)}) "
                    f"and appended rows count ({len(appended_rows)})."
                )

            for rec, r_idx in zip(exported_records, appended_rows):
                # Verify date
                val_date = ws.cell(r_idx, col_map["date"]).value
                dt_str = str(val_date)[:10] if val_date else ""
                if dt_str != rec.date:
                    raise WorkbookValidationError(
                        f"Row {r_idx} date mismatch: expected '{rec.date}', found '{dt_str}'."
                    )

                # Verify project
                val_proj = ws.cell(r_idx, col_map["project"]).value
                if str(val_proj or "").strip() != rec.project.strip():
                    raise WorkbookValidationError(
                        f"Row {r_idx} project mismatch: expected '{rec.project}', found '{val_proj}'."
                    )

                # Verify invoice
                val_inv = str(ws.cell(r_idx, col_map["invoice"]).value or "")
                if val_inv != str(rec.invoice_number or ""):
                    raise WorkbookValidationError(
                        f"Row {r_idx} invoice mismatch: expected '{rec.invoice_number}', found '{val_inv}'."
                    )

                # Verify tax
                val_tax = ws.cell(r_idx, col_map["tax"]).value
                if val_tax is None or abs(float(val_tax) - rec.tax_amount) > 0.001:
                    raise WorkbookValidationError(
                        f"Row {r_idx} tax mismatch: expected {rec.tax_amount}, found {val_tax}."
                    )

                # Verify Value formula
                col_val = col_map.get("value")
                if col_val:
                    c_val = str(ws.cell(r_idx, col_val).value or "")
                    if not c_val.startswith("="):
                        raise WorkbookValidationError(
                            f"Row {r_idx} Value formula is missing or corrupted: '{c_val}'."
                        )

                # Verify Total formula
                col_tot = col_map.get("total")
                if col_tot:
                    c_tot = str(ws.cell(r_idx, col_tot).value or "")
                    if not c_tot.startswith("="):
                        raise WorkbookValidationError(
                            f"Row {r_idx} Total formula is missing or corrupted: '{c_tot}'."
                        )

            # 3. Verify Summary Row intact if one was detected
            if expected_summary_row is not None and expected_summary_row <= ws.max_row:
                val_summary = str(ws.cell(expected_summary_row, 1).value or "")
                if "الإجمالي" not in val_summary:
                    raise WorkbookValidationError(
                        f"Summary row at index {expected_summary_row} was altered: '{val_summary}'."
                    )

        finally:
            wb_check.close()
