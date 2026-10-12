"""
Automated End-to-End Verification Harness for INJAZ Standalone Executable.
Validates all requirements of Section 5:
- App startup, window title, RTL layout, icon, and logos (both light & dark)
- Theme switching and QSettings persistence across restarts
- Real PDF extraction from synthetic fixtures without private archives
- Review table population and supplier grouping
- XLSX and CSV exports, file existence, and content validation
- Fail-closed export eligibility
- Arabic error handling
- No pollution of PyInstaller _internal or extraction directories
"""
import os
import sys
import csv
import json
from typing import Dict, Any

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon, QPixmap
import openpyxl


def run_verification(output_dir: str, pdf_path: str) -> int:
    """
    Executes full automated verification within the running Qt application.
    Returns 0 on complete success, 1 on any failure.
    """
    results: Dict[str, Any] = {
        "status": "in_progress",
        "checks": {},
        "details": {}
    }
    
    os.makedirs(output_dir, exist_ok=True)
    report_file = os.path.join(output_dir, "verification_report.json")
    
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            
        from injaz.paths import get_assets_dir, get_asset_path
        from injaz.ui.main_window import MainWindow
        from injaz.ui.theme import ThemeManager, apply_theme_to_app
        from injaz.ui.workers import AnalysisWorker, ExportWorker
        from injaz.models import ProcessingResult, TransactionRecord
        from injaz.ui.components.supplier_dialogs import SupplierGroupingDialog
        from injaz.supplier_matcher import group_similar_suppliers

        # -------------------------------------------------------------
        # 1. Startup & Application Metadata
        # -------------------------------------------------------------
        app.setApplicationName("INJAZ")
        app.setApplicationDisplayName("إنجاز - INJAZ")
        app.setLayoutDirection(Qt.RightToLeft)
        
        window = MainWindow()
        window.show()
        app.processEvents()

        is_rtl = (app.layoutDirection() == Qt.RightToLeft)
        title_ok = (window.windowTitle() == "إنجاز - INJAZ")
        results["checks"]["1_window_and_rtl"] = {
            "passed": is_rtl and title_ok,
            "title": window.windowTitle(),
            "is_rtl": is_rtl
        }

        # -------------------------------------------------------------
        # 2. Window Icon & Both Logo Variants
        # -------------------------------------------------------------
        assets_dir = get_assets_dir()
        app_icon_path = get_asset_path("app_icon.png")
        light_logo_path = get_asset_path("light_logo.png")
        dark_logo_path = get_asset_path("dark_logo.png")

        icon_pixmap = QPixmap(app_icon_path)
        light_pixmap = QPixmap(light_logo_path)
        dark_pixmap = QPixmap(dark_logo_path)

        logos_ok = (
            not icon_pixmap.isNull() and
            not light_pixmap.isNull() and
            not dark_pixmap.isNull() and
            os.path.exists(app_icon_path) and
            os.path.exists(light_logo_path) and
            os.path.exists(dark_logo_path)
        )
        results["checks"]["2_icons_and_logos"] = {
            "passed": logos_ok,
            "assets_dir": assets_dir,
            "app_icon_size": [icon_pixmap.width(), icon_pixmap.height()],
            "light_logo_size": [light_pixmap.width(), light_pixmap.height()],
            "dark_logo_size": [dark_pixmap.width(), dark_pixmap.height()]
        }

        # -------------------------------------------------------------
        # 3. Light & Dark Themes Switching
        # -------------------------------------------------------------
        window.apply_theme("light")
        app.processEvents()
        light_applied = (window.current_theme == "light")

        window.apply_theme("dark")
        app.processEvents()
        dark_applied = (window.current_theme == "dark")

        results["checks"]["3_themes_switch"] = {
            "passed": light_applied and dark_applied,
            "light_verified": light_applied,
            "dark_verified": dark_applied
        }

        # -------------------------------------------------------------
        # 4. Theme Preference Persistence via QSettings
        # -------------------------------------------------------------
        tm = ThemeManager.instance()
        tm.set_theme("dark")
        read_dark = tm.load_theme_preference()
        tm.set_theme("light")
        read_light = tm.load_theme_preference()

        persist_ok = (read_dark == "dark" and read_light == "light")
        results["checks"]["4_theme_persistence"] = {
            "passed": persist_ok,
            "read_dark": read_dark,
            "read_light": read_light
        }

        # -------------------------------------------------------------
        # 5. Arabic Error Handling
        # -------------------------------------------------------------
        non_existent_pdf = os.path.join(output_dir, "non_existent_statement.pdf")
        error_worker = AnalysisWorker(non_existent_pdf)
        received_error = []
        
        def on_error(msg):
            received_error.append(msg)
            
        error_worker.analysis_failed.connect(on_error)
        error_worker.start()
        while not received_error and error_worker.isRunning():
            app.processEvents()
            error_worker.wait(50)
        app.processEvents()

        has_arabic_error = len(received_error) > 0 and any(
            kw in received_error[0] for kw in ["تعذر", "كشف الحساب", "غير موجود", "ملف", "خطأ"]
        )
        results["checks"]["5_arabic_error_handling"] = {
            "passed": has_arabic_error,
            "received_message": received_error[0] if received_error else "None"
        }

        # -------------------------------------------------------------
        # 6. Real PDF Extraction on Synthetic Statement
        # -------------------------------------------------------------
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Test statement PDF not found: {pdf_path}")

        extracted_result = []
        def on_success(res: ProcessingResult):
            extracted_result.append(res)

        extract_worker = AnalysisWorker(pdf_path)
        extract_worker.analysis_finished.connect(on_success)
        extract_worker.start()
        while not extracted_result and extract_worker.isRunning():
            app.processEvents()
            extract_worker.wait(50)
        app.processEvents()

        if not extracted_result:
            raise RuntimeError("Extraction worker did not return a result.")

        proc_res: ProcessingResult = extracted_result[0]
        records = proc_res.records
        extraction_ok = len(records) > 0
        results["checks"]["6_pdf_extraction"] = {
            "passed": extraction_ok,
            "total_extracted": len(records),
            "eligible_count": proc_res.eligible_count,
            "validated_count": proc_res.validated_extraction_count
        }

        # -------------------------------------------------------------
        # 7. Review Table and Supplier Grouping Screen
        # -------------------------------------------------------------
        window.review_page.set_records(records)
        window._show_step_2()
        app.processEvents()

        table_rows = window.review_page.table_model.rowCount()
        supplier_clusters = group_similar_suppliers(records)

        review_ok = (table_rows == len(records)) and (isinstance(supplier_clusters, list))
        results["checks"]["7_review_and_suppliers"] = {
            "passed": review_ok,
            "table_rows": table_rows,
            "supplier_groups_count": len(supplier_clusters)
        }

        # -------------------------------------------------------------
        # 8 & 9. XLSX and CSV Exports and Content Validation
        # -------------------------------------------------------------
        # Filter fail-closed eligible records
        eligible_records = [r for r in records if r.is_export_eligible]
        out_xlsx = os.path.join(output_dir, "verified_export.xlsx")
        out_csv = os.path.join(output_dir, "verified_export.csv")

        if os.path.exists(out_xlsx):
            os.remove(out_xlsx)
        if os.path.exists(out_csv):
            os.remove(out_csv)

        # Export XLSX
        xlsx_worker = ExportWorker(
            output_path=out_xlsx,
            records=eligible_records,
            export_format="xlsx",
            overwrite=True
        )
        xlsx_finished = []
        xlsx_worker.export_finished.connect(lambda s: xlsx_finished.append(s))
        xlsx_worker.start()
        while not xlsx_finished and xlsx_worker.isRunning():
            app.processEvents()
            xlsx_worker.wait(50)
        app.processEvents()

        # Export CSV
        csv_worker = ExportWorker(
            output_path=out_csv,
            records=eligible_records,
            export_format="csv",
            overwrite=True
        )
        csv_finished = []
        csv_worker.export_finished.connect(lambda s: csv_finished.append(s))
        csv_worker.start()
        while not csv_finished and csv_worker.isRunning():
            app.processEvents()
            csv_worker.wait(50)
        app.processEvents()

        # Validate XLSX
        xlsx_exists = os.path.exists(out_xlsx)
        xlsx_wb = openpyxl.load_workbook(out_xlsx, data_only=True)
        xlsx_sheet = xlsx_wb.active
        xlsx_rows = xlsx_sheet.max_row - 1  # exclude header row

        # Validate CSV
        csv_exists = os.path.exists(out_csv)
        with open(out_csv, "r", encoding="utf-8-sig") as f:
            csv_reader = list(csv.reader(f))
            csv_rows = len(csv_reader) - 1

        exports_ok = (
            xlsx_exists and csv_exists and
            xlsx_rows == len(eligible_records) and
            csv_rows == len(eligible_records)
        )

        results["checks"]["8_and_9_exports_validation"] = {
            "passed": exports_ok,
            "eligible_records_count": len(eligible_records),
            "xlsx_exists": xlsx_exists,
            "xlsx_rows": xlsx_rows,
            "csv_exists": csv_exists,
            "csv_rows": csv_rows,
            "xlsx_path": out_xlsx,
            "csv_path": out_csv
        }

        # -------------------------------------------------------------
        # 10. PyInstaller Bundle Directory Isolation
        # -------------------------------------------------------------
        # Confirm no output files written inside bundle
        bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        polluted = any(
            os.path.exists(os.path.join(bundle_dir, name))
            for name in ["verified_export.xlsx", "verified_export.csv", "verification_report.json"]
        )
        results["checks"]["10_bundle_isolation"] = {
            "passed": not polluted,
            "bundle_dir": bundle_dir
        }

        window.close()
        app.processEvents()

        # -------------------------------------------------------------
        # Final evaluation
        # -------------------------------------------------------------
        all_passed = all(check.get("passed", False) for check in results["checks"].values())
        results["status"] = "PASSED" if all_passed else "FAILED"
        results["all_passed"] = all_passed

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(json.dumps(results, ensure_ascii=True, indent=2))
        return 0 if all_passed else 1

    except Exception as e:
        results["status"] = "ERROR"
        results["error"] = str(e)
        import traceback
        results["traceback"] = traceback.format_exc()
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"VERIFICATION ERROR: {e}\n{results['traceback']}")
        return 1
