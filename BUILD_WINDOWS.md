# INJAZ (إنجاز) — Windows Build & Packaging Guide

This guide documents the verified process for building the standalone Windows executable (`onedir`) and user installer for **INJAZ (إنجاز)**.

---

## 1. Verified Build Environment

The packaging and verification workflow has been validated on:
- **Operating System**: Windows 11 Home / Pro (x86_64, Windows 10.0.26200+)
- **Python**: Python 3.12.10 (Standard CPython 64-bit)
- **Qt Toolkit**: PySide6 6.12.0 (Qt 6.12 runtime)
- **Installer Tool**: Inno Setup 6 (ISCC compiler)

> [!IMPORTANT]
> Always build within an isolated project virtual environment (`.venv`) created with standard CPython rather than a base Conda environment to avoid shipping unintended global libraries or conflicting C runtime DLLs.

---

## 2. Environment Setup

From the repository root, create and activate an isolated Python 3.12 virtual environment:

```powershell
# Create isolated environment
py -3.12 -m venv .venv

# Activate environment
.\.venv\Scripts\Activate.ps1

# Install runtime and packaging dependencies
pip install --upgrade pip
pip install PySide6==6.12.0 pymupdf==1.28.2 openpyxl==3.1.5 pyinstaller==6.22.3 pytest==9.1.1 Pillow==12.3.0
```

---

## 3. Building the Standalone Application (`onedir`)

The PyInstaller configuration is defined in [`INJAZ.spec`](INJAZ.spec).

### Packaging Command:

```powershell
.\.venv\Scripts\pyinstaller INJAZ.spec --noconfirm
Copy-Item -Path "assets" -Destination "dist/INJAZ/assets" -Recurse -Force
```

### Resulting Distribution:
- **Executable**: `dist/INJAZ/INJAZ.exe`
- **Internal Binaries**: `dist/INJAZ/_internal/`
- **Brand Assets**: `dist/INJAZ/_internal/assets/` and `dist/INJAZ/assets/`

### Features Bundled:
1. Complete PySide6 Qt6 runtime, QtCore, QtGui, QtWidgets, and Arabic text rendering plugins.
2. PyMuPDF (`fitz`) PDF extraction engine.
3. OpenPyXL workbook generator.
4. Embedded multi-resolution application icon (`app_icon.ico`) with 7 square frames (16x16 to 256x256).
5. High-contrast Light and Dark brand logos (`light_logo.png`, `dark_logo.png`).
6. Clean native Windows 10/11 ICU discovery, eliminating System32 DLL bundling and filtering out third-party/Anaconda ICU libraries.

---

## 4. Building the Windows Installer

The installer script is defined in [`installer.iss`](installer.iss) for Inno Setup 6.

### Installer Configuration Highlights:
- **Application Name**: `إنجاز - INJAZ`
- **Application Version**: `1.0.1`
- **Install Mode**: `PrivilegesRequired=lowest` (installs cleanly into `{localappdata}\Programs\INJAZ` without requiring Administrator privileges).
- **Shortcuts**: Start Menu shortcut and optional Desktop icon with authentic brand icon.
- **Uninstaller**: Standard Windows Control Panel registration with clean self-removal (`unins000.exe`).

### Installer Build Command:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

*(Ensure the path to `ISCC.exe` matches your Inno Setup 6 installation directory).*

### Resulting Setup Program:
- **Installer**: `dist_installer/INJAZ_Setup_1.0.1.exe`

---

## 5. Automated Verification & Testing

Both the standalone distribution and installed executable support automated non-interactive verification via the `--verify-e2e` CLI switch:

```powershell
# Test standalone distribution
& "dist\INJAZ\INJAZ.exe" --verify-e2e "$env:TEMP\injaz_test" "tests\fixtures\synthetic_statement.pdf"

# Test installed application
& "$env:LOCALAPPDATA\Programs\INJAZ\INJAZ.exe" --verify-e2e "$env:TEMP\injaz_test" "tests\fixtures\synthetic_statement.pdf"
```

### Verification Checks Performed:
1. **Window & RTL**: Validates window title `إنجاز - INJAZ` and Qt Right-to-Left Arabic layout.
2. **Icons & Logos**: Validates presence, dimensions, and pixel loads of `app_icon.png`, `light_logo.png`, and `dark_logo.png`.
3. **Theme Switching**: Toggles dynamically between Light and Dark themes.
4. **Theme Persistence**: Verifies `QSettings` read/write roundtrip across restarts.
5. **Arabic Error Handling**: Validates informative Arabic dialogs on invalid input.
6. **PDF Extraction**: Runs full CoreExtractionEngine on synthetic PDF statements without referencing any private files.
7. **Review & Suppliers**: Validates transaction table model population and supplier clustering.
8. **XLSX & CSV Export**: Generates `.xlsx` and `.csv` files and inspects worksheet cells, headers, and record counts.
9. **Bundle Isolation**: Confirms no temporary output files are written into the read-only application directory.

---

## 6. Known Limitations & Notes

- **PDF Statement Compatibility**: INJAZ is optimized for tabular Arabic account statements. Scanned bitmap PDFs without OCR text layers require text pre-processing.
- **Windows Path Encoding**: When invoking the application CLI from PowerShell, paths containing spaces should be quoted to prevent argument fragmentation.
