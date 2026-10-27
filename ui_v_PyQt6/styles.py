"""
AI Creator Studio - Professional Dark Theme Stylesheet (QSS) for PyQt6 / PySide6
Designed for ultra-smooth 60fps responsiveness, hardware-accelerated rendering,
and crisp Khmer & English Unicode typography.

Design Palette:
- Main background: #111318
- Secondary background: #191C23
- Panel background: #20242D
- Elevated surface: #292E39
- Primary accent: #6675FF
- Success: #2BC48A
- Warning: #F5B84B
- Error: #EF626C
- Primary text: #F1F3F8
- Secondary text: #A0A8B8
- Subtle borders: #343A46
"""

# Studio Color Palette Tokens
COLOR_MAIN_BG = "#111318"
COLOR_SECONDARY_BG = "#191C23"
COLOR_PANEL_BG = "#20242D"
COLOR_ELEVATED = "#292E39"
COLOR_ACCENT = "#6675FF"
COLOR_ACCENT_HOVER = "#7A87FF"
COLOR_SUCCESS = "#2BC48A"
COLOR_WARNING = "#F5B84B"
COLOR_ERROR = "#EF626C"
COLOR_TEXT_PRIMARY = "#F1F3F8"
COLOR_TEXT_SECONDARY = "#A0A8B8"
COLOR_BORDER = "#343A46"

DARK_STUDIO_QSS = """
/* Global Application Style */
QWidget {
    background-color: #20242D;
    color: #F1F3F8;
    font-family: 'Kantumruy Pro', 'Leelawadee UI', 'Khmer OS Siemreap', 'Segoe UI', 'Inter', sans-serif;
    font-size: 12px;
    selection-background-color: #6675FF;
    selection-color: #ffffff;
}

/* Main Window & Toolbars */
QMainWindow {
    background-color: #111318;
}

QMenuBar {
    background-color: #191C23;
    color: #F1F3F8;
    border-bottom: 1px solid #343A46;
    font-weight: 500;
}

QMenuBar::item {
    background: transparent;
    padding: 6px 12px;
    border-radius: 6px;
    margin: 2px 1px;
}

QMenuBar::item:selected {
    background-color: #292E39;
    color: #6675FF;
}

QMenu {
    background-color: #191C23;
    color: #F1F3F8;
    border: 1px solid #343A46;
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 24px 6px 14px;
    border-radius: 6px;
}

QMenu::item:selected {
    background-color: #6675FF;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background: #343A46;
    margin: 4px 6px;
}

/* Splitter (Butter-smooth resizing) */
QSplitter::handle {
    background-color: #191C23;
}

QSplitter::handle:horizontal {
    width: 4px;
}

QSplitter::handle:vertical {
    height: 4px;
}

QSplitter::handle:hover {
    background-color: #6675FF;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #343A46;
    background-color: #20242D;
    margin: 0px;
    padding: 0px;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #191C23;
    color: #A0A8B8;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: bold;
}

QTabBar::tab:selected {
    background-color: #20242D;
    color: #6675FF;
    border-bottom: 2px solid #6675FF;
}

QTabBar::tab:hover:!selected {
    background-color: #292E39;
    color: #F1F3F8;
}

/* Buttons - Sleek Compact Pro Studio Styling */
QPushButton {
    background-color: #292E39;
    color: #F1F3F8;
    border: 1px solid #343A46;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
    min-height: 12px;
}

QPushButton:hover {
    background-color: #343A46;
    border-color: #6675FF;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #191C23;
}

QPushButton:disabled {
    background-color: #191C23;
    color: #64748B;
    border-color: #292E39;
}

/* Primary Action Buttons */
QPushButton#btn_primary {
    background-color: #6675FF;
    border: 1px solid #7A87FF;
    color: #ffffff;
}

QPushButton#btn_primary:hover {
    background-color: #5563EE;
    border-color: #929DFF;
}

QPushButton#btn_success {
    background-color: #2BC48A;
    border: 1px solid #4ADE80;
    color: #ffffff;
}

QPushButton#btn_success:hover {
    background-color: #22A875;
}

QPushButton#btn_danger {
    background-color: #EF626C;
    border: 1px solid #F87171;
    color: #ffffff;
}

QPushButton#btn_danger:hover {
    background-color: #DC2626;
}

/* Input Fields & Text Edits */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #191C23;
    color: #F1F3F8;
    border: 1px solid #343A46;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #6675FF;
    background-color: #20242D;
}

/* Combo Boxes - Matched to QPushButton Size & Height */
QComboBox {
    background-color: #292E39;
    color: #F1F3F8;
    border: 1px solid #343A46;
    border-radius: 6px;
    padding: 3px 22px 3px 10px;
    font-size: 11px;
    font-weight: 500;
    min-height: 16px;
    max-height: 26px;
}

QComboBox:hover {
    border-color: #6675FF;
    background-color: #343A46;
}

QComboBox:focus {
    border-color: #6675FF;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #343A46;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox::down-arrow {
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #A0A8B8;
    margin-right: 2px;
}

QComboBox::down-arrow:hover {
    border-top: 5px solid #6675FF;
}

QComboBox QAbstractItemView {
    background-color: #191C23;
    color: #F1F3F8;
    border: 1px solid #343A46;
    border-radius: 6px;
    selection-background-color: #6675FF;
    selection-color: #ffffff;
    padding: 4px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 4px 10px;
    border-radius: 4px;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #6675FF;
    color: #ffffff;
}

/* Tables (Virtualized high-performance Subtitle Grid) */
QTableWidget {
    background-color: #191C23;
    gridline-color: #292E39;
    border: 1px solid #343A46;
    border-radius: 8px;
    color: #F1F3F8;
}

QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #20242D;
}

QTableWidget::item:selected {
    background-color: #292E39;
    color: #6675FF;
}

QTableWidget::item:hover:!selected {
    background-color: #20242D;
}

QHeaderView::section {
    background-color: #111318;
    color: #A0A8B8;
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid #343A46;
    font-weight: bold;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #111318;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #292E39;
    min-height: 25px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #6675FF;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #111318;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #292E39;
    min-width: 25px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #6675FF;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
/* Sliders - Sleek Modern Studio Pro Styling */
QSlider::groove:horizontal {
    border: 1px solid #232b38;
    height: 5px;
    background: #141822;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #ffffff, stop:0.7 #f1f5f9, stop:1 #cbd5e1);
    border: 2px solid #38bdf8;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #ffffff;
    border: 2px solid #7dd3fc;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #343A46;
    border-radius: 6px;
    background-color: #191C23;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
    height: 16px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6675FF, stop:1 #2BC48A);
    border-radius: 5px;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    color: #F1F3F8;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #343A46;
    background-color: #191C23;
}

QCheckBox::indicator:hover {
    border-color: #38bdf8;
}

QCheckBox::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
}

/* Status Bar */
QStatusBar {
    background-color: #111318;
    color: #A0A8B8;
    border-top: 1px solid #343A46;
}

/* Group Boxes (Clean Sectional Grouping) */
QGroupBox {
    background-color: #161922;
    border: 1px solid #262c3b;
    border-radius: 9px;
    margin-top: 12px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}

QGroupBox:hover {
    border-color: #343d52;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 3px 10px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a202c, stop:1 #222b3b);
    border: 1px solid #333f54;
    border-radius: 5px;
    color: #38bdf8;
    font-size: 11px;
    font-weight: bold;
}

/* Splitters & Professional Smooth Resize Handles */
QSplitter {
    background-color: transparent;
}

QSplitter::handle {
    background-color: #191C23;
}

QSplitter::handle:horizontal {
    width: 4px;
}

QSplitter::handle:vertical {
    height: 4px;
}

QSplitter::handle:hover {
    background-color: #6675FF;
}

QSplitter::handle:pressed {
    background-color: #5563EE;
}

/* Professional Dock Widgets (Premiere / CapCut Studio Docking) */
QDockWidget {
    color: #F1F3F8;
    font-size: 11px;
    font-weight: 600;
    border: 1px solid #343A46;
}

QDockWidget::title {
    background-color: #191C23;
    padding: 6px 12px;
    border-bottom: 1px solid #343A46;
    text-align: left;
    color: #6675FF;
    font-weight: bold;
}

QDockWidget::close-button, QDockWidget::float-button {
    background-color: transparent;
    border: none;
    padding: 3px;
    border-radius: 4px;
}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background-color: #292E39;
    color: #6675FF;
}
"""


def get_studio_qss(font_size_px: int = 12) -> str:
    """Returns dynamic dark studio QSS with scaled base font size."""
    small_px = max(9, font_size_px - 1)
    qss = DARK_STUDIO_QSS.replace("font-size: 12px;", f"font-size: {font_size_px}px;")
    qss = qss.replace("font-size: 11px;", f"font-size: {small_px}px;")
    return qss

