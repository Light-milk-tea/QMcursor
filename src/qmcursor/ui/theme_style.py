"""Bilibili-inspired light UI stylesheet for QMcursor."""

# Brand pink / page chrome close to bilibili.com
BILI_PINK = "#FB7299"
BILI_PINK_HOVER = "#FF85AD"
BILI_PINK_PRESSED = "#E85A85"
BILI_BLUE = "#00A1D6"
PAGE_BG = "#F4F5F7"
CARD_BG = "#FFFFFF"
TEXT_PRIMARY = "#18191C"
TEXT_SECONDARY = "#61666D"
TEXT_MUTED = "#9499A0"
BORDER = "#E3E5E7"
CHIP_BG = "#FFF1F5"
CHIP_BORDER = "#FFD6E3"


def main_window_stylesheet() -> str:
    return f"""
    QMainWindow {{
        background: {PAGE_BG};
    }}
    QWidget#root {{
        background: {PAGE_BG};
    }}
    QWidget#headerBar {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 12px;
    }}
    QLabel#brandTitle {{
        color: {TEXT_PRIMARY};
        font-size: 22px;
        font-weight: 700;
        letter-spacing: 0.2px;
    }}
    QLabel#brandSubtitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}
    QLabel#sectionTitle {{
        color: {TEXT_PRIMARY};
        font-size: 15px;
        font-weight: 600;
    }}
    QLabel#description {{
        color: {TEXT_SECONDARY};
        font-size: 12px;
    }}
    QLabel#currentTheme {{
        padding: 10px 14px;
        color: {BILI_PINK};
        background: {CHIP_BG};
        border: 1px solid {CHIP_BORDER};
        border-radius: 10px;
        font-weight: 600;
        font-size: 13px;
    }}
    QLabel#status {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}
    QLabel#sizeCaption {{
        color: {TEXT_SECONDARY};
        font-weight: 600;
    }}
    QLabel#sizeValue {{
        color: {BILI_PINK};
        font-weight: 700;
        background: {CHIP_BG};
        border: 1px solid {CHIP_BORDER};
        border-radius: 8px;
        padding: 4px 8px;
    }}
    QLabel#previewTitle {{
        color: {TEXT_PRIMARY};
        font-size: 15px;
        font-weight: 700;
    }}
    QLabel#previewMeta {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}
    QLabel#badgeApplied {{
        color: {BILI_PINK};
        background: {CHIP_BG};
        border: 1px solid {CHIP_BORDER};
        border-radius: 8px;
        padding: 3px 8px;
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#badgeIdle {{
        color: {TEXT_SECONDARY};
        background: #F0F1F2;
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 3px 8px;
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#emptyState {{
        color: {TEXT_MUTED};
        font-size: 13px;
        padding: 32px 24px;
    }}
    QLabel#roleTitle {{
        color: {TEXT_PRIMARY};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#roleFile {{
        color: {TEXT_MUTED};
        font-size: 11px;
    }}
    QLabel#filterCount {{
        color: {TEXT_MUTED};
        font-size: 11px;
        padding: 0 2px;
    }}
    QFrame#card, QWidget#footerBar, QWidget#previewPanel {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 12px;
    }}
    QWidget#previewHeader {{
        background: transparent;
    }}
    QFrame#previewCard {{
        background: #FAFBFC;
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
    QFrame#previewCard:hover {{
        background: #FFF7FA;
        border-color: {CHIP_BORDER};
    }}
    QLineEdit#themeSearch {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 7px 10px;
        color: {TEXT_PRIMARY};
        selection-background-color: #FFE4EC;
        selection-color: {TEXT_PRIMARY};
    }}
    QLineEdit#themeSearch:focus {{
        border-color: {BILI_PINK};
    }}
    QTreeWidget, QTableWidget {{
        background: transparent;
        border: none;
        outline: none;
        color: {TEXT_PRIMARY};
        alternate-background-color: #FAFBFC;
        selection-background-color: #FFE4EC;
        selection-color: {TEXT_PRIMARY};
        gridline-color: {BORDER};
    }}
    QTreeWidget::item {{
        padding: 8px 6px;
        border-radius: 6px;
        margin: 1px 4px;
    }}
    QTreeWidget::item:hover {{
        background: #FFF0F5;
    }}
    QTreeWidget::item:selected {{
        background: #FFE4EC;
        color: {TEXT_PRIMARY};
    }}
    QHeaderView::section {{
        background: #FAFBFC;
        color: {TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {BORDER};
        padding: 8px 10px;
        font-weight: 600;
    }}
    QTableWidget::item {{
        padding: 4px 8px;
    }}
    QPushButton {{
        padding: 8px 16px;
        border: 1px solid {BORDER};
        border-radius: 8px;
        background: {CARD_BG};
        color: {TEXT_PRIMARY};
        font-weight: 600;
    }}
    QPushButton:hover {{
        border-color: {BILI_PINK};
        color: {BILI_PINK};
        background: #FFF7FA;
    }}
    QPushButton:pressed {{
        background: {CHIP_BG};
    }}
    QPushButton:disabled {{
        color: {TEXT_MUTED};
        background: #F0F1F2;
        border-color: {BORDER};
    }}
    QPushButton#primaryButton {{
        color: white;
        background: {BILI_PINK};
        border-color: {BILI_PINK};
    }}
    QPushButton#primaryButton:hover {{
        background: {BILI_PINK_HOVER};
        border-color: {BILI_PINK_HOVER};
        color: white;
    }}
    QPushButton#primaryButton:pressed {{
        background: {BILI_PINK_PRESSED};
        border-color: {BILI_PINK_PRESSED};
        color: white;
    }}
    QPushButton#primaryButton:disabled {{
        color: white;
        background: #F7B0C4;
        border-color: #F7B0C4;
    }}
    QCheckBox {{
        color: {TEXT_SECONDARY};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid #C9CCD0;
        border-radius: 4px;
        background: white;
    }}
    QCheckBox::indicator:hover {{
        border-color: {BILI_PINK};
    }}
    QCheckBox::indicator:checked {{
        background: {BILI_PINK};
        border-color: {BILI_PINK};
    }}
    QSlider::groove:horizontal {{
        height: 6px;
        background: #E7E9EC;
        border-radius: 3px;
    }}
    QSlider::sub-page:horizontal {{
        background: {BILI_PINK};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 8px;
        background: white;
        border: 2px solid {BILI_PINK};
    }}
    QSlider::handle:horizontal:hover {{
        border-color: {BILI_PINK_HOVER};
    }}
    QMenu {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 8px 18px;
        border-radius: 6px;
        color: {TEXT_PRIMARY};
    }}
    QMenu::item:selected {{
        background: #FFE4EC;
        color: {BILI_PINK};
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 4px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: #C9CCD0;
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {BILI_PINK};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QSplitter::handle {{
        background: transparent;
        width: 8px;
    }}
    """
