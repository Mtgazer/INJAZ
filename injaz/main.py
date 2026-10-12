"""
Application Entry Point for INJAZ (إنجاز).
Configures Arabic RTL layout, high-DPI scaling, brand typography, and launches MainWindow.
"""
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont

from injaz.ui.main_window import MainWindow
from injaz.ui.theme import ThemeManager, apply_theme_to_app


def main() -> int:
    """Initializes and runs the INJAZ desktop application."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName("INJAZ")
    app.setApplicationDisplayName("إنجاز - INJAZ")

    # Check for automated packaging verification flag
    if "--verify-e2e" in sys.argv:
        from injaz.verify_cli import run_verification
        idx = sys.argv.index("--verify-e2e")
        out_dir = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else os.path.join(os.getcwd(), "test_outputs")
        pdf = " ".join(sys.argv[idx + 2:]) if len(sys.argv) > idx + 2 else ""
        return run_verification(out_dir, pdf)

    # 0. Windows explicit Application User Model ID for taskbar grouping & icon binding
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("INJAZ.Desktop.ArabicPDFAutomation.1.0.1")
        except Exception:
            pass

    # 1. Set application icon globally (prioritize multi-resolution .ico on Windows, fallback to .png)
    from injaz.paths import get_asset_path
    icon_path = get_asset_path("app_icon.ico")
    if not os.path.exists(icon_path):
        icon_path = get_asset_path("app_icon.png")
    if not os.path.exists(icon_path):
        icon_path = get_asset_path("icon_mark.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # 2. Set Right-to-Left (RTL) Arabic layout direction globally
    app.setLayoutDirection(Qt.RightToLeft)

    # 3. Typography configuration
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # 4. Restore saved theme preference before showing UI
    theme_name = ThemeManager.instance().load_theme_preference()
    apply_theme_to_app(app, theme_name)

    # 5. Instantiate and display main window
    window = MainWindow()
    window.show()

    return app.exec()



if __name__ == "__main__":
    sys.exit(main())
