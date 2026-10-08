"""Dark SaaS-style theme (QSS)."""

# Palette
BG = "#12141a"
BG_PANEL = "#1a1d26"
BG_CARD = "#20242f"
BG_HOVER = "#2a2f3d"
BORDER = "#2e3340"
TEXT = "#e6e9f0"
TEXT_DIM = "#8b93a7"
ACCENT = "#6c5ce7"
ACCENT_HOVER = "#7d6ff0"
GREEN = "#00b894"
RED = "#e17055"
YELLOW = "#fdcb6e"

STYLESHEET = f"""
* {{
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}}
QMainWindow, QWidget {{
    background: {BG};
    color: {TEXT};
}}
/* ---------- sidebar ---------- */
#Sidebar {{
    background: {BG_PANEL};
    border-right: 1px solid {BORDER};
}}
#AppTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {TEXT};
    padding: 18px 16px 4px 16px;
}}
#AppSubtitle {{
    font-size: 11px;
    color: {TEXT_DIM};
    padding: 0 16px 14px 16px;
}}
QPushButton#NavButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    color: {TEXT_DIM};
    text-align: left;
    padding: 10px 14px;
    margin: 2px 8px;
    font-size: 13px;
}}
QPushButton#NavButton:hover {{
    background: {BG_HOVER};
    color: {TEXT};
}}
QPushButton#NavButton:checked {{
    background: {ACCENT};
    color: white;
    font-weight: 600;
}}
/* ---------- cards / panels ---------- */
QFrame#Card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#CardValue {{
    font-size: 26px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#CardTitle {{
    font-size: 11px;
    color: {TEXT_DIM};
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QLabel#PageTitle {{
    font-size: 20px;
    font-weight: 700;
    padding: 4px 0 10px 0;
}}
QLabel#SectionTitle {{
    font-size: 14px;
    font-weight: 600;
    padding: 8px 0 4px 0;
}}
QLabel#Hint {{
    color: {TEXT_DIM};
    font-size: 12px;
}}
/* ---------- inputs ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus,
QPlainTextEdit:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
}}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {BG_PANEL};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
/* ---------- buttons ---------- */
QPushButton {{
    background: {BG_HOVER};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; background: {BG_PANEL}; }}
QPushButton#Primary {{
    background: {ACCENT};
    border: none;
    color: white;
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#Danger {{ background: {RED}; border: none; color: white; }}
QPushButton#Success {{ background: {GREEN}; border: none; color: white; }}
/* ---------- tables ---------- */
QTableWidget, QTableView {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    alternate-background-color: {BG_PANEL};
}}
QHeaderView::section {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px;
    font-weight: 600;
}}
QTableWidget::item:selected {{ background: {ACCENT}; }}
/* ---------- misc ---------- */
QProgressBar {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    text-align: center;
    color: {TEXT};
    height: 18px;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 7px; }}
QScrollBar:vertical {{
    background: {BG}; width: 10px; border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; }}
QTabBar::tab {{
    background: {BG_PANEL}; color: {TEXT_DIM};
    padding: 8px 18px; border-top-left-radius: 8px; border-top-right-radius: 8px;
}}
QTabBar::tab:selected {{ background: {BG_CARD}; color: {TEXT}; }}
"""
