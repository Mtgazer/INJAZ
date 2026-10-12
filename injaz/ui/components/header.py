"""
Header component for INJAZ desktop application.
Displays brand identity logo, clean 3-step workflow breadcrumb, and Light/Dark mode toggle.
"""
import os
from typing import List, Tuple
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QFrame, QPushButton
)
from PySide6.QtGui import QPixmap, QCursor
from PySide6.QtCore import Qt, Signal

from injaz.ui.theme import (
    ThemeManager, get_theme
)


class HeaderWidget(QFrame):
    """
    Application header featuring the official brand logo, 3-step workflow progress stepper,
    and a Light / Dark theme toggle button.
    """
    theme_toggle_requested = Signal()
    step_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("headerFrame")
        self.setFixedHeight(75)

        self.theme_name = ThemeManager.instance().current_theme
        self.current_step = 1

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(16)

        # 1. Brand Logo on Right (RTL Start)
        brand_layout = QHBoxLayout()
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(0)

        self.logo_label = QLabel()
        self.logo_label.setObjectName("headerLogoLabel")
        self.logo_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        brand_layout.addWidget(self.logo_label)

        self.logo_fallback = QLabel("إنجاز — INJAZ")
        self.logo_fallback.setObjectName("headerLogoFallback")
        self.logo_fallback.setStyleSheet("font-size: 18px; font-weight: 800;")
        self.logo_fallback.setVisible(False)
        brand_layout.addWidget(self.logo_fallback)

        layout.addLayout(brand_layout)

        layout.addStretch()

        # 2. 3-Step Workflow Stepper
        steps_layout = QHBoxLayout()
        steps_layout.setSpacing(8)

        self.step_widgets: List[Tuple[QFrame, QLabel, QLabel]] = []
        self.arrow_labels: List[QLabel] = []
        step_names = [
            ("1", "كشف PDF"),
            ("2", "المراجعة"),
            ("3", "التصدير"),
        ]

        for i, (num, name) in enumerate(step_names):
            pill = QFrame()
            pill.setObjectName(f"stepPill_{i}")
            pill.setCursor(Qt.PointingHandCursor)
            pill_layout = QHBoxLayout(pill)
            pill_layout.setContentsMargins(12, 6, 14, 6)
            pill_layout.setSpacing(8)

            num_lbl = QLabel(num)
            num_lbl.setObjectName("numLabel")
            num_lbl.setAlignment(Qt.AlignCenter)
            num_lbl.setFixedSize(22, 22)
            pill_layout.addWidget(num_lbl)

            text_lbl = QLabel(name)
            text_lbl.setObjectName("textLabel")
            text_lbl.setAlignment(Qt.AlignCenter)
            # Remove any unwanted inner rectangle or border
            text_lbl.setStyleSheet("border: none; background: transparent; outline: none;")
            pill_layout.addWidget(text_lbl)

            # Click navigation on completed steps
            step_idx = i + 1
            pill.mousePressEvent = lambda event, s=step_idx: self._on_pill_clicked(s)

            steps_layout.addWidget(pill)
            self.step_widgets.append((pill, num_lbl, text_lbl))

            if i < len(step_names) - 1:
                arrow = QLabel("←")
                arrow.setObjectName("stepArrow")
                arrow.setStyleSheet("font-size: 14px; font-weight: bold;")
                steps_layout.addWidget(arrow)
                self.arrow_labels.append(arrow)

        layout.addLayout(steps_layout)

        layout.addSpacing(12)

        # 3. Theme Toggle Button on Left (RTL End)
        self.btn_theme_toggle = QPushButton()
        self.btn_theme_toggle.setObjectName("themeToggleBtn")
        self.btn_theme_toggle.setFixedSize(38, 38)
        self.btn_theme_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_theme_toggle.setFocusPolicy(Qt.TabFocus)
        self.btn_theme_toggle.clicked.connect(self.theme_toggle_requested.emit)
        layout.addWidget(self.btn_theme_toggle)

        # Initialize visual states
        self.set_theme(self.theme_name)
        self.set_current_step(1)

    def _on_pill_clicked(self, step_number: int):
        """Allows clicking earlier completed steps to navigate back."""
        if step_number < self.current_step:
            self.step_clicked.emit(step_number)

    def set_theme(self, theme_name: str):
        """Updates logo asset, stepper pill colors, and theme toggle button icon."""
        self.theme_name = theme_name
        theme = get_theme(theme_name)

        # Update Header Background & Border
        self.setStyleSheet(f"""
            QFrame#headerFrame {{
                background-color: {theme.surface};
                border-bottom: 1px solid {theme.border};
            }}
        """)

        # 1. Update Logo Asset
        from injaz.paths import get_assets_dir
        possible_dirs = [
            get_assets_dir(),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets")),
            os.path.join(os.getcwd(), "assets"),
        ]
        logo_filename = "dark_logo.png" if theme_name == "dark" else "light_logo.png"
        logo_path = None
        for ad in possible_dirs:
            candidate = os.path.join(ad, logo_filename)
            if os.path.exists(candidate):
                logo_path = candidate
                break

        if logo_path and os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            if not pix.isNull():
                # Preserve aspect ratio, compact clean height ~ 40px
                scaled_pix = pix.scaledToHeight(40, Qt.SmoothTransformation)
                self.logo_label.setPixmap(scaled_pix)
                self.logo_label.setVisible(True)
                self.logo_fallback.setVisible(False)
            else:
                self._show_logo_fallback(theme, f"Failed to decode image from {logo_path}")
        else:
            self._show_logo_fallback(theme, f"Logo asset file '{logo_filename}' not found in search paths")

        # 2. Update Theme Toggle Button
        if theme_name == "dark":
            self.btn_theme_toggle.setText("☀️")
            self.btn_theme_toggle.setToolTip("التبديل إلى الوضع الفاتح (Light Mode)")
        else:
            self.btn_theme_toggle.setText("🌙")
            self.btn_theme_toggle.setToolTip("التبديل إلى الوضع الداكن (Dark Mode)")

        # 3. Update Stepper Pills & Arrows
        self.set_current_step(self.current_step)

    def _show_logo_fallback(self, theme, error_msg: str):
        """Displays fallback brand text if logo asset cannot be loaded, and reports the issue."""
        print(f"[WARNING] {error_msg}. Displaying fallback brand header.")
        self.logo_label.setVisible(False)
        self.logo_fallback.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {theme.text_primary};")
        self.logo_fallback.setVisible(True)

    def set_current_step(self, step_number: int):
        """
        Updates visual styling of workflow pills (1-indexed).
        Guarantees NO unwanted inner rectangles around labels in both themes.
        """
        self.current_step = step_number
        theme = get_theme(self.theme_name)

        # Update Arrow colors
        arrow_color = "#64748B" if self.theme_name == "dark" else "#94A3B8"
        for arrow in self.arrow_labels:
            arrow.setStyleSheet(f"color: {arrow_color}; font-size: 14px; font-weight: bold; border: none; background: transparent;")

        for i, (pill, num_lbl, text_lbl) in enumerate(self.step_widgets, start=1):
            pill_id = f"stepPill_{i - 1}"

            if i == step_number:
                # Active step
                pill_bg = theme.teal_bg
                pill_border = f"1.5px solid {theme.teal}"
                num_bg = theme.teal
                num_text = "#111827" if self.theme_name == "dark" else "#FFFFFF"
                lbl_color = theme.text_primary

                pill.setStyleSheet(f"""
                    QFrame#{pill_id} {{
                        background-color: {pill_bg};
                        border: {pill_border};
                        border-radius: 16px;
                    }}
                """)
                num_lbl.setStyleSheet(f"""
                    background-color: {num_bg};
                    color: {num_text};
                    font-size: 11px;
                    font-weight: 800;
                    border-radius: 11px;
                    border: none;
                """)
                text_lbl.setStyleSheet(f"""
                    color: {lbl_color};
                    font-size: 12px;
                    font-weight: 700;
                    border: none;
                    background: transparent;
                    outline: none;
                """)

            elif i < step_number:
                # Completed step
                pill_bg = theme.bg_secondary
                pill_border = f"1px solid {theme.border}"
                num_bg = theme.teal
                num_text = "#111827" if self.theme_name == "dark" else "#FFFFFF"
                lbl_color = theme.text_primary

                pill.setStyleSheet(f"""
                    QFrame#{pill_id} {{
                        background-color: {pill_bg};
                        border: {pill_border};
                        border-radius: 16px;
                    }}
                    QFrame#{pill_id}:hover {{
                        border-color: {theme.teal};
                    }}
                """)
                num_lbl.setStyleSheet(f"""
                    background-color: {num_bg};
                    color: {num_text};
                    font-size: 11px;
                    font-weight: 700;
                    border-radius: 11px;
                    border: none;
                """)
                text_lbl.setStyleSheet(f"""
                    color: {lbl_color};
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                    background: transparent;
                    outline: none;
                """)

            else:
                # Pending step
                pill.setStyleSheet(f"""
                    QFrame#{pill_id} {{
                        background-color: transparent;
                        border: 1px solid transparent;
                        border-radius: 16px;
                    }}
                """)
                num_bg = "#2A3749" if self.theme_name == "dark" else "#E2E8F0"
                num_text = theme.text_muted
                lbl_color = theme.text_muted

                num_lbl.setStyleSheet(f"""
                    background-color: {num_bg};
                    color: {num_text};
                    font-size: 11px;
                    font-weight: 700;
                    border-radius: 11px;
                    border: none;
                """)
                text_lbl.setStyleSheet(f"""
                    color: {lbl_color};
                    font-size: 12px;
                    font-weight: 500;
                    border: none;
                    background: transparent;
                    outline: none;
                """)
