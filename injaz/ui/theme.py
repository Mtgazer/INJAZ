"""
INJAZ (إنجاز) — Complete Brand Theme and Visual Styling System.
Supports both Light and Dark themes with full QSettings persistence,
high-contrast typography, seamless Arabic RTL layout, and modern desktop design.

Light Theme Palette:
- Primary Navy: #16324F
- Teal: #1D9A8A
- Background: #F5F7FA
- Surface: #FFFFFF
- Primary Text: #172033
- Secondary Text: #667085
- Borders: #E2E8F0
- Warning: #E8A23A
- Error: #D64545
- Success: #248B62

Dark Theme Palette:
- Primary background: #111827
- Secondary background: #18212D
- Surface: #202A36
- Primary text: #F1F5F9
- Secondary text: #B6C2D0
- Borders: #344152
- Teal accent: #35B8A6
- Warning: #F2B84B
- Error: #F06A73
- Success: #4CC38A
"""
import os
from dataclasses import dataclass
from typing import Optional, Dict

from PySide6.QtWidgets import QApplication, QWidget, QComboBox, QStyledItemDelegate
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import QSettings, Qt, Signal, QObject


FONT_FAMILY = '"Segoe UI", "IBM Plex Sans Arabic", "Noto Sans Arabic", "Tahoma", "Arial", sans-serif'


@dataclass
class ThemeTokens:
    name: str  # "light" | "dark"

    # Backgrounds & Surfaces
    bg: str
    bg_secondary: str
    surface: str
    surface_hover: str
    card_bg: str

    # Typography
    text_primary: str
    text_secondary: str
    text_muted: str

    # Borders
    border: str
    border_hover: str
    border_focus: str

    # Brand Colors & Accents
    primary_navy: str
    primary_navy_hover: str
    teal: str
    teal_hover: str
    teal_bg: str

    # Primary Action Buttons
    primary_btn_bg: str
    primary_btn_hover: str
    primary_btn_text: str

    # Secondary Action Buttons
    secondary_btn_bg: str
    secondary_btn_hover: str
    secondary_btn_border: str
    secondary_btn_text: str

    # Status Highlights
    success: str
    success_bg: str
    success_border: str

    warning: str
    warning_bg: str
    warning_border: str

    error: str
    error_bg: str
    error_border: str

    duplicate: str
    duplicate_bg: str
    duplicate_border: str

    # Tables
    table_bg: str
    table_grid: str
    table_header_bg: str
    table_header_text: str
    table_header_border: str
    table_alt_row: str
    table_selection_bg: str
    table_selection_text: str

    # Dropdown popup
    dropdown_bg: str
    dropdown_text: str
    dropdown_border: str
    dropdown_hover_bg: str
    dropdown_hover_text: str

    # Scrollbars
    scrollbar_handle: str
    scrollbar_handle_hover: str

    # Dialogs
    dialog_bg: str
    dialog_text: str
    dialog_border: str


LIGHT_THEME = ThemeTokens(
    name="light",
    bg="#F5F7FA",
    bg_secondary="#F8FAFC",
    surface="#FFFFFF",
    surface_hover="#F8FAFC",
    card_bg="#FFFFFF",

    text_primary="#172033",
    text_secondary="#667085",
    text_muted="#94A3B8",

    border="#E2E8F0",
    border_hover="#CBD5E1",
    border_focus="#1D9A8A",

    primary_navy="#16324F",
    primary_navy_hover="#1F4266",
    teal="#1D9A8A",
    teal_hover="#24B09E",
    teal_bg="#E6F4F1",

    primary_btn_bg="#16324F",
    primary_btn_hover="#1F4266",
    primary_btn_text="#FFFFFF",

    secondary_btn_bg="#FFFFFF",
    secondary_btn_hover="#F8FAFC",
    secondary_btn_border="#E2E8F0",
    secondary_btn_text="#16324F",

    success="#248B62",
    success_bg="#EAF7F1",
    success_border="#A7F3D0",

    warning="#E8A23A",
    warning_bg="#FEF6E9",
    warning_border="#FDE68A",

    error="#D64545",
    error_bg="#FDECEC",
    error_border="#FECACA",

    duplicate="#9A3412",
    duplicate_bg="#FFEDD5",
    duplicate_border="#FDBA74",

    table_bg="#FFFFFF",
    table_grid="#F1F5F9",
    table_header_bg="#F8FAFC",
    table_header_text="#16324F",
    table_header_border="#E2E8F0",
    table_alt_row="#FAFBFC",
    table_selection_bg="#E6F4F1",
    table_selection_text="#172033",

    dropdown_bg="#FFFFFF",
    dropdown_text="#172033",
    dropdown_border="#E2E8F0",
    dropdown_hover_bg="#E6F4F1",
    dropdown_hover_text="#16324F",

    scrollbar_handle="#CBD5E1",
    scrollbar_handle_hover="#94A3B8",

    dialog_bg="#FFFFFF",
    dialog_text="#172033",
    dialog_border="#E2E8F0",
)


DARK_THEME = ThemeTokens(
    name="dark",
    bg="#111827",
    bg_secondary="#18212D",
    surface="#202A36",
    surface_hover="#283545",
    card_bg="#202A36",

    text_primary="#F1F5F9",
    text_secondary="#B6C2D0",
    text_muted="#8E9DAE",

    border="#344152",
    border_hover="#475569",
    border_focus="#35B8A6",

    primary_navy="#35B8A6",
    primary_navy_hover="#44CEBB",
    teal="#35B8A6",
    teal_hover="#44CEBB",
    teal_bg="#17333B",

    primary_btn_bg="#35B8A6",
    primary_btn_hover="#44CEBB",
    primary_btn_text="#111827",

    secondary_btn_bg="#202A36",
    secondary_btn_hover="#283545",
    secondary_btn_border="#344152",
    secondary_btn_text="#F1F5F9",

    success="#4CC38A",
    success_bg="#133324",
    success_border="#1E5C3B",

    warning="#F2B84B",
    warning_bg="#332814",
    warning_border="#5C4517",

    error="#F06A73",
    error_bg="#381A1C",
    error_border="#5C262A",

    duplicate="#FB923C",
    duplicate_bg="#3D2111",
    duplicate_border="#6B3314",

    table_bg="#202A36",
    table_grid="#263342",
    table_header_bg="#18222F",
    table_header_text="#F1F5F9",
    table_header_border="#344152",
    table_alt_row="#1A232E",
    table_selection_bg="#1E3D45",
    table_selection_text="#FFFFFF",

    dropdown_bg="#202A36",
    dropdown_text="#F1F5F9",
    dropdown_border="#344152",
    dropdown_hover_bg="#2A3B4C",
    dropdown_hover_text="#FFFFFF",

    scrollbar_handle="#3B4B5E",
    scrollbar_handle_hover="#50657D",

    dialog_bg="#202A36",
    dialog_text="#F1F5F9",
    dialog_border="#344152",
)


# Global Color Constants for Backward Compatibility (Light theme defaults)
COLOR_NAVY = LIGHT_THEME.primary_navy
COLOR_NAVY_HOVER = LIGHT_THEME.primary_navy_hover
COLOR_TEAL = LIGHT_THEME.teal
COLOR_TEAL_HOVER = LIGHT_THEME.teal_hover
COLOR_BG = LIGHT_THEME.bg
COLOR_SURFACE = LIGHT_THEME.surface
COLOR_TEXT_PRIMARY = LIGHT_THEME.text_primary
COLOR_TEXT_SECONDARY = LIGHT_THEME.text_secondary
COLOR_BORDER = LIGHT_THEME.border
COLOR_BORDER_FOCUS = LIGHT_THEME.border_focus
COLOR_WARNING = LIGHT_THEME.warning
COLOR_WARNING_BG = LIGHT_THEME.warning_bg
COLOR_ERROR = LIGHT_THEME.error
COLOR_ERROR_BG = LIGHT_THEME.error_bg
COLOR_SUCCESS = LIGHT_THEME.success
COLOR_SUCCESS_BG = LIGHT_THEME.success_bg


class ThemeSignals(QObject):
    theme_changed = Signal(str)


_theme_signals = ThemeSignals()


class ThemeManager:
    """
    Central manager for Light / Dark visual themes and user persistence.
    """
    _instance: Optional["ThemeManager"] = None
    SETTINGS_ORG = "INJAZ"
    SETTINGS_APP = "InjazApp"
    SETTINGS_KEY = "theme"

    def __init__(self):
        self._settings = QSettings(self.SETTINGS_ORG, self.SETTINGS_APP)
        saved = self._settings.value(self.SETTINGS_KEY, "light")
        self._current_theme = saved if saved in ("light", "dark") else "light"

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    @property
    def current_theme(self) -> str:
        return self._current_theme

    @property
    def tokens(self) -> ThemeTokens:
        return DARK_THEME if self._current_theme == "dark" else LIGHT_THEME

    def is_dark(self) -> bool:
        return self._current_theme == "dark"

    def load_theme_preference(self) -> str:
        saved = self._settings.value(self.SETTINGS_KEY, "light")
        if saved in ("light", "dark"):
            self._current_theme = saved
        else:
            self._current_theme = "light"
        return self._current_theme

    def save_theme_preference(self, theme_name: str):
        if theme_name in ("light", "dark"):
            self._current_theme = theme_name
            self._settings.setValue(self.SETTINGS_KEY, theme_name)
            _theme_signals.theme_changed.emit(theme_name)

    def set_theme(self, theme_name: str):
        self.save_theme_preference(theme_name)

    def toggle_theme(self) -> str:
        new_theme = "light" if self._current_theme == "dark" else "dark"
        self.save_theme_preference(new_theme)
        return new_theme


def get_theme(theme_name: Optional[str] = None) -> ThemeTokens:
    if theme_name is None:
        theme_name = ThemeManager.instance().current_theme
    return DARK_THEME if theme_name == "dark" else LIGHT_THEME


def get_current_theme() -> ThemeTokens:
    return ThemeManager.instance().tokens


def get_palette(theme_name: Optional[str] = None) -> QPalette:
    theme = get_theme(theme_name)
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(theme.bg))
    pal.setColor(QPalette.WindowText, QColor(theme.text_primary))
    pal.setColor(QPalette.Base, QColor(theme.surface))
    pal.setColor(QPalette.AlternateBase, QColor(theme.table_alt_row))
    pal.setColor(QPalette.ToolTipBase, QColor(theme.surface))
    pal.setColor(QPalette.ToolTipText, QColor(theme.text_primary))
    pal.setColor(QPalette.Text, QColor(theme.text_primary))
    pal.setColor(QPalette.Button, QColor(theme.surface))
    pal.setColor(QPalette.ButtonText, QColor(theme.text_primary))
    pal.setColor(QPalette.Highlight, QColor(theme.dropdown_hover_bg))
    pal.setColor(QPalette.HighlightedText, QColor(theme.dropdown_hover_text))
    pal.setColor(QPalette.Mid, QColor(theme.border))
    pal.setColor(QPalette.Dark, QColor(theme.border))
    return pal


def get_stylesheet(theme_name: Optional[str] = None) -> str:
    t = get_theme(theme_name)

    return f"""
/* =========================================================================
   INJAZ (إنجاز) — Complete Theme Stylesheet ({t.name.upper()})
   ========================================================================= */

QMainWindow, QStackedWidget, QWidget#pageRoot, QWidget#exportPage, QWidget#reviewPage, QWidget#newProcessPage {{
    background-color: {t.bg};
    font-family: {FONT_FAMILY};
}}

QWidget {{
    font-family: {FONT_FAMILY};
    color: {t.text_primary};
}}

/* Surface Card Container */
QFrame#cardFrame {{
    background-color: {t.card_bg};
    border: 1px solid {t.border};
    border-radius: 8px;
}}

/* Header Frame */
QFrame#headerFrame {{
    background-color: {t.surface};
    border-bottom: 1px solid {t.border};
}}

/* Typography */
QLabel#pageTitle {{
    font-size: 20px;
    font-weight: 700;
    color: {t.text_primary};
}}

QLabel#pageSubtitle {{
    font-size: 13px;
    color: {t.text_secondary};
}}

QLabel#sectionTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {t.text_primary};
}}

QLabel#fieldLabel {{
    font-size: 12px;
    font-weight: 600;
    color: {t.text_secondary};
}}

QLabel#statRowLabel {{
    font-size: 13px;
    color: {t.text_primary};
}}

/* Primary Buttons */
QPushButton#primaryButton {{
    background-color: {t.primary_btn_bg};
    color: {t.primary_btn_text};
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    padding: 8px 18px;
    min-height: 24px;
}}

QPushButton#primaryButton:hover {{
    background-color: {t.primary_btn_hover};
}}

QPushButton#primaryButton:disabled {{
    background-color: {t.border};
    color: {t.text_muted};
}}

/* Teal Accent Buttons */
QPushButton#tealButton {{
    background-color: {t.teal};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    padding: 7px 16px;
}}

QPushButton#tealButton:hover {{
    background-color: {t.teal_hover};
}}

/* Secondary / Outline Buttons */
QPushButton#secondaryButton {{
    background-color: {t.secondary_btn_bg};
    color: {t.secondary_btn_text};
    border: 1px solid {t.secondary_btn_border};
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    padding: 6px 14px;
}}

QPushButton#secondaryButton:hover {{
    background-color: {t.secondary_btn_hover};
    border-color: {t.border_hover};
}}

/* Danger Action Buttons */
QPushButton#dangerButton {{
    background-color: {t.error_bg};
    color: {t.error};
    border: 1px solid {t.error_border};
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    padding: 6px 14px;
}}

QPushButton#dangerButton:hover {{
    background-color: {t.error_border};
}}

/* Theme Toggle Button in Header */
QPushButton#themeToggleBtn {{
    background-color: {t.bg_secondary};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: 19px;
    font-size: 16px;
    min-width: 36px;
    min-height: 36px;
}}

QPushButton#themeToggleBtn:hover {{
    background-color: {t.surface_hover};
    border-color: {t.border_hover};
}}

/* Inputs (LineEdits) */
QLineEdit {{
    background-color: {t.surface};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 20px;
    selection-background-color: {t.teal};
    selection-color: #FFFFFF;
}}

QLineEdit:focus {{
    border: 1.5px solid {t.border_focus};
}}

/* Combobox (Dropdown) & Popup List View */
QComboBox {{
    background-color: {t.surface};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
    min-height: 22px;
    selection-background-color: {t.dropdown_hover_bg};
    selection-color: {t.dropdown_hover_text};
}}

QComboBox:focus, QComboBox:on {{
    border: 1.5px solid {t.border_focus};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top left;
    width: 24px;
    border: none;
    background: transparent;
}}

QComboBox::down-arrow {{
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t.text_secondary};
}}

QComboBox QAbstractItemView {{
    background-color: {t.dropdown_bg};
    color: {t.dropdown_text};
    border: 1px solid {t.dropdown_border};
    border-radius: 6px;
    padding: 4px;
    selection-background-color: {t.dropdown_hover_bg};
    selection-color: {t.dropdown_hover_text};
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 6px 10px;
    border-radius: 4px;
    color: {t.dropdown_text};
    background-color: transparent;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {t.dropdown_hover_bg};
    color: {t.dropdown_hover_text};
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {t.dropdown_hover_bg};
    color: {t.dropdown_hover_text};
}}

/* Data Tables */
QTableView, QTableWidget {{
    background-color: {t.table_bg};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: 6px;
    gridline-color: {t.table_grid};
    selection-background-color: {t.table_selection_bg};
    selection-color: {t.table_selection_text};
    font-size: 12px;
    outline: none;
}}

QTableView::item:alternate, QTableWidget::item:alternate {{
    background-color: {t.table_alt_row};
}}

QTableView::item:selected, QTableWidget::item:selected {{
    background-color: {t.table_selection_bg};
    color: {t.table_selection_text};
}}

QHeaderView::section {{
    background-color: {t.table_header_bg};
    color: {t.table_header_text};
    font-weight: 600;
    font-size: 12px;
    border: none;
    border-bottom: 1px solid {t.table_header_border};
    border-left: 1px solid {t.table_grid};
    padding: 8px 6px;
}}

/* Workflow Step Pills in Header — NO unwanted inner borders on text */
QFrame#stepPill_0 QLabel, QFrame#stepPill_1 QLabel, QFrame#stepPill_2 QLabel {{
    border: none;
    background: transparent;
    outline: none;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {t.scrollbar_handle};
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {t.scrollbar_handle_hover};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Dialogs & Message Boxes */
QDialog, QMessageBox {{
    background-color: {t.dialog_bg};
    color: {t.dialog_text};
}}

QMessageBox QLabel, QDialog QLabel {{
    background-color: transparent;
    color: {t.dialog_text};
    font-size: 13px;
}}

QMessageBox QPushButton {{
    background-color: {t.primary_btn_bg};
    color: {t.primary_btn_text};
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    padding: 7px 18px;
    min-width: 80px;
    min-height: 22px;
}}

QMessageBox QPushButton:hover {{
    background-color: {t.primary_btn_hover};
}}
"""


def get_dialog_stylesheet(theme_name: Optional[str] = None) -> str:
    t = get_theme(theme_name)
    return f"""
QDialog {{
    background-color: {t.surface};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: 10px;
}}

QLabel {{
    color: {t.text_primary};
    background: transparent;
}}

QLabel#dialogTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {t.text_primary};
}}

QLabel#dialogSubtitle {{
    font-size: 12px;
    color: {t.text_secondary};
}}

QFrame#infoCard {{
    background-color: {t.bg};
    border: 1px solid {t.border};
    border-radius: 8px;
    padding: 12px;
}}

QTableWidget {{
    background-color: {t.surface};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: 6px;
    gridline-color: {t.table_grid};
    selection-background-color: {t.table_selection_bg};
    selection-color: {t.table_selection_text};
}}

QTableWidget::item:alternate {{
    background-color: {t.table_alt_row};
}}

QHeaderView::section {{
    background-color: {t.table_header_bg};
    color: {t.text_primary};
    border: none;
    border-bottom: 1px solid {t.border};
    padding: 6px 4px;
    font-weight: 600;
}}

QPushButton#btnPrimaryConfirm {{
    background-color: {t.teal};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    padding: 9px 20px;
    min-height: 20px;
}}

QPushButton#btnPrimaryConfirm:hover {{
    background-color: {t.teal_hover};
}}

QPushButton#btnPrimaryNavy {{
    background-color: {t.primary_btn_bg};
    color: {t.primary_btn_text};
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    padding: 9px 18px;
    min-height: 20px;
}}

QPushButton#btnPrimaryNavy:hover {{
    background-color: {t.primary_btn_hover};
}}

QPushButton#btnCancelNeutral {{
    background-color: {t.secondary_btn_bg};
    color: {t.secondary_btn_text};
    border: 1px solid {t.secondary_btn_border};
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 18px;
    min-height: 20px;
}}

QPushButton#btnCancelNeutral:hover {{
    background-color: {t.secondary_btn_hover};
    border-color: {t.border_hover};
}}
"""


def style_combo_box(combo: QComboBox, theme_name: Optional[str] = None):
    """
    Applies custom high-contrast delegate and palette to QComboBox popup to eliminate
    any OS fallback to illegible colors.
    """
    theme = get_theme(theme_name)
    combo.setItemDelegate(QStyledItemDelegate(combo))
    view = combo.view()
    if view:
        pal = view.palette()
        pal.setColor(QPalette.Base, QColor(theme.dropdown_bg))
        pal.setColor(QPalette.Text, QColor(theme.dropdown_text))
        pal.setColor(QPalette.Highlight, QColor(theme.dropdown_hover_bg))
        pal.setColor(QPalette.HighlightedText, QColor(theme.dropdown_hover_text))
        view.setPalette(pal)


def apply_theme_to_app(app: QApplication, theme_name: Optional[str] = None):
    """Applies stylesheet and system palette to QApplication instance."""
    theme = get_theme(theme_name)
    app.setStyleSheet(get_stylesheet(theme.name))
    app.setPalette(get_palette(theme.name))


# Default APP_STYLESHEET for backward compatibility
APP_STYLESHEET = get_stylesheet("light")
DIALOG_BASE_STYLE = get_dialog_stylesheet("light")
