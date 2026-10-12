"""
Dedicated Modern Excel Workbook Exporter for INJAZ (إنجاز).
Generates a clean, brand-new .xlsx workbook from approved financial transactions from scratch,
using the exact same 6-column tabular structure as the CSV export.
Strictly adheres to fail-closed audit eligibility rules, atomic generation, and programmatic validation.
"""
import os
import tempfile
import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from injaz.models import TransactionRecord


class XlsxExportError(Exception):
    """Base exception for Excel export operations."""
    pass


class NoEligibleRecordsError(XlsxExportError):
    """Raised when no records are eligible for export, preventing false empty success files."""
    pass


class IneligibleXlsxExportError(XlsxExportError):
    """Raised when an unapproved or ineligible record is submitted with fail_on_ineligible=True."""
    pass


class XlsxProtectionError(XlsxExportError):
    """Raised when attempting to overwrite critical reference statement or template files."""
    pass


class XlsxValidationError(XlsxExportError):
    """Raised when the generated workbook fails post-generation round-trip validation."""
    pass


@dataclass
class XlsxExportSummary:
    """Summary metrics of a completed XLSX export run."""
    total_records_submitted: int
    records_exported: int
    records_rejected_ineligible: int
    output_path: str
    records_skipped_already_present: int = 0
    rejection_details: List[Dict[str, Any]] = field(default_factory=list)



class XlsxExporter:
    """
    Dedicated exporter that generates a brand-new Excel workbook from scratch.
    Does NOT require, read, copy, or mutate any pre-existing Excel template.
    """
    SHEET_NAME = "المعاملات"
    HEADERS = ["م", "التاريخ", "المشروع", "رقم الفاتورة", "المورد", "الضريبة"]

    # Brand visual styling tokens
    COLOR_NAVY = "16324F"
    COLOR_WHITE = "FFFFFF"
    COLOR_BORDER = "CBD5E1"
    COLOR_ZEBRA = "F8FAFC"

    def export_transactions(
        self,
        output_path: str,
        records: List[TransactionRecord],
        overwrite: bool = False,
        fail_on_ineligible: bool = False
    ) -> XlsxExportSummary:
        """
        Creates a new formatted .xlsx workbook containing only approved, eligible transactions.
        """
        if not output_path:
            raise ValueError("An explicit output_path is required.")

        abs_output = os.path.abspath(output_path)

        # 1. Protection against overwriting critical reference and fixture files
        for ref_rel in [
            os.path.join("references", "sample_statement.pdf.pdf"),
            os.path.join("references", "excel_template.xlsx"),
            os.path.join("tests", "fixtures", "synthetic_statement.pdf"),
            os.path.join("tests", "fixtures", "synthetic_template.xlsx"),
        ]:
            ref_abs = os.path.abspath(ref_rel)
            if os.path.exists(ref_abs) and os.path.normcase(abs_output) == os.path.normcase(ref_abs):
                raise XlsxProtectionError(f"Cannot overwrite protected reference file: '{ref_rel}'.")

        # 2. File overwrite verification
        if os.path.exists(abs_output) and not overwrite:
            raise FileExistsError(
                f"Output Excel file already exists at '{abs_output}'. "
                "Specify a different path or set overwrite=True."
            )

        # 3. Strict Fail-Closed Export Eligibility Verification
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
                    raise IneligibleXlsxExportError(
                        f"Record index {r.record_index} is ineligible for export: {reason}"
                    )

        # 4. Refuse creating an empty workbook that would falsely report success
        if len(eligible_records) == 0:
            reasons_summary = "; ".join(d["reason"] for d in rejection_details[:3]) if rejection_details else "No records provided"
            raise NoEligibleRecordsError(
                f"No eligible records found for export ({len(records)} submitted, "
                f"{len(rejection_details)} rejected). Reasons: {reasons_summary}"
            )

        output_dir = os.path.dirname(abs_output)
        os.makedirs(output_dir, exist_ok=True)

        # 5. Atomic creation via temporary file
        temp_fd, temp_path = tempfile.mkstemp(
            prefix="injaz_export_",
            suffix=".xlsx",
            dir=output_dir
        )
        os.close(temp_fd)

        try:
            self._build_workbook(temp_path, eligible_records)
            self._validate_generated_workbook(temp_path, eligible_records)
            os.replace(temp_path, abs_output)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

        return XlsxExportSummary(
            total_records_submitted=len(records),
            records_exported=len(eligible_records),
            records_rejected_ineligible=len(rejection_details),
            output_path=abs_output,
            rejection_details=rejection_details
        )

    def _build_workbook(self, file_path: str, records: List[TransactionRecord]):
        """Builds a new workbook from scratch with approved INJAZ styling."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = self.SHEET_NAME

        # Enable Arabic Right-to-Left sheet view
        if hasattr(ws.views, "sheetView") and ws.views.sheetView:
            ws.views.sheetView[0].rightToLeft = True

        # Freeze panes below the header row
        ws.freeze_panes = "A2"

        # Styling objects
        header_fill = PatternFill(start_color=self.COLOR_NAVY, end_color=self.COLOR_NAVY, fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color=self.COLOR_WHITE)
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        border_side = Side(border_style="thin", color=self.COLOR_BORDER)
        cell_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)
        
        zebra_fill = PatternFill(start_color=self.COLOR_ZEBRA, end_color=self.COLOR_ZEBRA, fill_type="solid")

        # 1. Write Header Row
        ws.row_dimensions[1].height = 28
        for col_idx, header_text in enumerate(self.HEADERS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header_text)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
            cell.border = cell_border

        # 2. Write Data Rows
        for seq_num, rec in enumerate(records, start=1):
            row_idx = seq_num + 1
            ws.row_dimensions[row_idx].height = 22
            row_fill = zebra_fill if (seq_num % 2 == 0) else None

            # Col 1: Sequence number (starts at 1)
            c1 = ws.cell(row=row_idx, column=1, value=seq_num)
            c1.number_format = "0"
            c1.alignment = Alignment(horizontal="center", vertical="center")

            # Col 2: Date (Excel date cell)
            date_val = self._parse_date_value(rec.date)
            c2 = ws.cell(row=row_idx, column=2, value=date_val)
            if isinstance(date_val, (datetime.date, datetime.datetime)):
                c2.number_format = "yyyy-mm-dd"
            c2.alignment = Alignment(horizontal="center", vertical="center")

            # Col 3: Project name
            c3 = ws.cell(row=row_idx, column=3, value=str(rec.project or "").strip())
            c3.alignment = Alignment(horizontal="right", vertical="center")

            # Col 4: Invoice number
            c4 = ws.cell(row=row_idx, column=4, value=str(rec.invoice_number or "").strip())
            c4.alignment = Alignment(horizontal="center", vertical="center")

            # Col 5: Supplier name
            c5 = ws.cell(row=row_idx, column=5, value=str(rec.supplier_name or "").strip())
            c5.alignment = Alignment(horizontal="right", vertical="center")

            # Col 6: Tax amount (numeric, preserving debit + / credit - sign)
            tax_num = float(rec.tax_amount) if rec.tax_amount is not None else 0.0
            c6 = ws.cell(row=row_idx, column=6, value=tax_num)
            c6.number_format = "#,##0.00"
            c6.alignment = Alignment(horizontal="right", vertical="center")

            # Apply font, border, and optional zebra fill across all cells in row
            for cell in (c1, c2, c3, c4, c5, c6):
                cell.font = Font(name="Calibri", size=11)
                cell.border = cell_border
                if row_fill:
                    cell.fill = row_fill

        # 3. Autofilter over the exact data range
        total_rows = len(records) + 1
        ws.auto_filter.ref = f"A1:F{total_rows}"

        # 4. Comfortable Column Widths
        column_widths = {
            "A": 8,   # م
            "B": 15,  # التاريخ
            "C": 20,  # المشروع
            "D": 18,  # رقم الفاتورة
            "E": 38,  # المورد
            "F": 16,  # الضريبة
        }
        for col_letter, width in column_widths.items():
            ws.column_dimensions[col_letter].width = width

        wb.save(file_path)

    @staticmethod
    def _parse_date_value(date_val: Any) -> Any:
        """Parses string date into datetime.date so openpyxl writes a true Excel date cell."""
        if isinstance(date_val, (datetime.date, datetime.datetime)):
            return date_val
        if isinstance(date_val, str) and date_val.strip():
            cleaned = date_val.strip()
            # ISO format YYYY-MM-DD
            try:
                return datetime.date.fromisoformat(cleaned)
            except ValueError:
                pass
            # Alternate format YYYY/MM/DD
            try:
                return datetime.datetime.strptime(cleaned, "%Y/%m/%d").date()
            except ValueError:
                pass
            # DD/MM/YYYY
            try:
                return datetime.datetime.strptime(cleaned, "%d/%m/%Y").date()
            except ValueError:
                pass
        return date_val

    def _validate_generated_workbook(self, file_path: str, expected_records: List[TransactionRecord]):
        """
        Reopens the generated workbook, verifies worksheet name, headers,
        row count, sequence order, date types, and numeric values.
        """
        if not os.path.exists(file_path):
            raise XlsxValidationError(f"Generated file does not exist at '{file_path}'.")

        if os.path.getsize(file_path) == 0:
            raise XlsxValidationError(f"Generated file is 0 bytes at '{file_path}'.")

        wb = openpyxl.load_workbook(file_path, data_only=True)
        try:
            if self.SHEET_NAME not in wb.sheetnames:
                raise XlsxValidationError(
                    f"Worksheet '{self.SHEET_NAME}' not found. Available sheets: {wb.sheetnames}"
                )

            ws = wb[self.SHEET_NAME]

            # 1. Header order verification
            read_headers = [
                ws.cell(row=1, column=c).value for c in range(1, len(self.HEADERS) + 1)
            ]
            if read_headers != self.HEADERS:
                raise XlsxValidationError(
                    f"Workbook headers {read_headers} do not match required order {self.HEADERS}"
                )

            # 2. Row count verification (Header row + N data rows)
            expected_data_count = len(expected_records)
            if ws.max_row != expected_data_count + 1:
                raise XlsxValidationError(
                    f"Row count mismatch: sheet max_row is {ws.max_row}, "
                    f"expected {expected_data_count + 1} ({expected_data_count} data rows)."
                )

            # 3. Cell-level verification across all data rows
            for seq_num, rec in enumerate(expected_records, start=1):
                row_idx = seq_num + 1

                # Column 1: Sequence number
                val_seq = ws.cell(row=row_idx, column=1).value
                if val_seq != seq_num:
                    raise XlsxValidationError(
                        f"Row {row_idx} sequence mismatch: {val_seq} != {seq_num}"
                    )

                # Column 2: Date
                val_date = ws.cell(row=row_idx, column=2).value
                if not val_date:
                    raise XlsxValidationError(f"Row {row_idx} date cell is empty.")

                # Column 3: Project
                val_proj = ws.cell(row=row_idx, column=3).value
                if str(val_proj or "").strip() != str(rec.project or "").strip():
                    raise XlsxValidationError(
                        f"Row {row_idx} project mismatch: '{val_proj}' != '{rec.project}'"
                    )

                # Column 4: Invoice
                val_inv = ws.cell(row=row_idx, column=4).value
                if str(val_inv or "").strip() != str(rec.invoice_number or "").strip():
                    raise XlsxValidationError(
                        f"Row {row_idx} invoice mismatch: '{val_inv}' != '{rec.invoice_number}'"
                    )

                # Column 5: Supplier
                val_supp = ws.cell(row=row_idx, column=5).value
                if str(val_supp or "").strip() != str(rec.supplier_name or "").strip():
                    raise XlsxValidationError(
                        f"Row {row_idx} supplier mismatch: '{val_supp}' != '{rec.supplier_name}'"
                    )

                # Column 6: Tax amount (numeric, sign preserved)
                val_tax = ws.cell(row=row_idx, column=6).value
                if not isinstance(val_tax, (int, float)):
                    raise XlsxValidationError(
                        f"Row {row_idx} tax value '{val_tax}' is not a numeric Excel cell (type: {type(val_tax)})."
                    )
                expected_tax = float(rec.tax_amount) if rec.tax_amount is not None else 0.0
                if abs(float(val_tax) - expected_tax) > 0.001:
                    raise XlsxValidationError(
                        f"Row {row_idx} tax amount mismatch: {val_tax} != {expected_tax}"
                    )
        finally:
            wb.close()
