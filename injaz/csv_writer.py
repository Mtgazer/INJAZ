"""
CSV Export Fallback Engine for Injaz (إنجاز).
Provides a reliable, UTF-8-BOM encoded CSV alternative for financial data export
when Excel template population is unavailable or requires independent tabular data export.
Strictly adheres to fail-closed audit eligibility rules.
"""
import os
import csv
import tempfile
import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple

from injaz.models import TransactionRecord


class CsvExportError(Exception):
    """Base exception for CSV export operations."""
    pass


class IneligibleCsvExportError(CsvExportError):
    """Raised when an unapproved or ineligible record is submitted with fail_on_ineligible=True."""
    pass


class CsvProtectionError(CsvExportError):
    """Raised when attempting to overwrite critical source templates or statement files."""
    pass


class CsvValidationError(CsvExportError):
    """Raised when the generated CSV fails post-generation round-trip validation."""
    pass


@dataclass
class CsvExportSummary:
    """Summary metrics of a completed CSV export run."""
    total_records_submitted: int
    records_exported: int
    records_rejected_ineligible: int
    output_path: str
    records_skipped_already_present: int = 0
    rejection_details: List[Dict[str, Any]] = field(default_factory=list)



class CsvPopulationEngine:
    """
    Engine for exporting approved financial transaction records to CSV.
    Enforces UTF-8 BOM encoding for seamless Arabic rendering in Microsoft Excel,
    strict fail-closed eligibility checking, and programmatic round-trip verification.
    """
    HEADERS = ["م", "التاريخ", "المشروع", "رقم الفاتورة", "المورد", "الضريبة"]

    def export_transactions(
        self,
        output_path: str,
        records: List[TransactionRecord],
        overwrite: bool = False,
        fail_on_ineligible: bool = False
    ) -> CsvExportSummary:
        """
        Exports approved transactions to a UTF-8 with BOM CSV file.
        """
        if not output_path:
            raise ValueError("An explicit output_path is required.")

        abs_output = os.path.abspath(output_path)

        # File overwrite verification
        if os.path.exists(abs_output) and not overwrite:
            raise FileExistsError(
                f"Output CSV already exists at '{abs_output}'. "
                "Specify a different path or set overwrite=True."
            )

        # 1. Strict Fail-Closed Export Eligibility Verification
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
                    raise IneligibleCsvExportError(
                        f"Record index {r.record_index} is ineligible for CSV export: {reason}"
                    )

        output_dir = os.path.dirname(abs_output)
        os.makedirs(output_dir, exist_ok=True)

        # 2. Write to temporary file first for atomic safety and validation
        temp_fd, temp_path = tempfile.mkstemp(
            prefix="injaz_csv_",
            suffix=".csv",
            dir=output_dir
        )
        os.close(temp_fd)

        try:
            # Write with utf-8-sig (UTF-8 with BOM) for Arabic Excel compatibility
            with open(temp_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(self.HEADERS)

                for seq_num, rec in enumerate(eligible_records, start=1):
                    # Format date: ensure YYYY-MM-DD
                    dt_val = rec.date
                    if isinstance(dt_val, (datetime.date, datetime.datetime)):
                        date_str = dt_val.strftime("%Y-%m-%d")
                    else:
                        date_str = str(dt_val).strip()

                    # Tax amount preserving sign and 2 decimal places
                    if rec.tax_amount is not None:
                        tax_val = f"{float(rec.tax_amount):.2f}"
                    else:
                        tax_val = "0.00"

                    writer.writerow([
                        seq_num,
                        date_str,
                        rec.project or "",
                        rec.invoice_number or "",
                        rec.supplier_name or "",
                        tax_val
                    ])

            # 3. Post-Generation Integrity Validation: reopen and verify rows
            self._validate_generated_csv(temp_path, len(eligible_records))

            # 4. Atomic move/replace
            os.replace(temp_path, abs_output)

        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

        return CsvExportSummary(
            total_records_submitted=len(records),
            records_exported=len(eligible_records),
            records_rejected_ineligible=len(rejection_details),
            output_path=abs_output,
            rejection_details=rejection_details
        )

    def _validate_generated_csv(self, file_path: str, expected_record_count: int):
        """Reopens the generated CSV, verifies BOM presence, headers, and data row count."""
        # Check BOM in raw bytes
        with open(file_path, "rb") as raw_f:
            bom = raw_f.read(3)
            if bom != b'\xef\xbb\xbf':
                raise CsvValidationError("Generated CSV file lacks UTF-8 BOM signature.")

        # Reopen with utf-8-sig
        with open(file_path, "r", newline="", encoding="utf-8-sig") as f:
            reader = list(csv.reader(f))

        if not reader:
            raise CsvValidationError("Generated CSV file is empty.")

        headers = reader[0]
        if headers != self.HEADERS:
            raise CsvValidationError(
                f"Generated CSV headers {headers} do not match expected {self.HEADERS}."
            )

        data_rows = reader[1:]
        if len(data_rows) != expected_record_count:
            raise CsvValidationError(
                f"Generated CSV row count {len(data_rows)} does not match expected {expected_record_count}."
            )
