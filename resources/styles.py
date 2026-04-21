# ============================================================
# filter_toolbox/resources/styles.py
# Light and Dark QSS theme strings loaded at runtime.
# ============================================================

LIGHT_QSS = """
QMainWindow, QWidget {
    background-color: #f4f6f9;
    color: #1e2230;
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #c8d0dc;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    font-weight: 600;
    color: #2d4070;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QLabel#lblTitle {
    font-size: 17px;
    font-weight: 700;
    color: #1a3a6e;
    padding: 6px 0;
}

QComboBox, QDoubleSpinBox, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #b0bccf;
    border-radius: 4px;
    padding: 3px 6px;
    min-height: 24px;
}
QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover {
    border-color: #3d7aed;
}
QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
    border-color: #1a5fe8;
    outline: none;
}

QPushButton {
    background-color: #2d5be3;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 6px 16px;
    font-weight: 600;
}
QPushButton:hover  { background-color: #1a4dcf; }
QPushButton:pressed{ background-color: #1038a8; }

QPushButton#btnToggleTheme {
    background-color: #6c757d;
}
QPushButton#btnToggleTheme:hover { background-color: #5a6268; }

QPushButton#btnResetZoom {
    background-color: #5a6a8a;
}
QPushButton#btnResetZoom:hover { background-color: #4a5a7a; }

QPushButton#btnSimulate {
    background-color: #1a8a42;
}
QPushButton#btnSimulate:hover { background-color: #147036; }

QPushButton#btnExportNetlist,
QPushButton#btnExportReport {
    background-color: #e67e22;
}
QPushButton#btnExportNetlist:hover,
QPushButton#btnExportReport:hover { background-color: #ca6f1e; }

QTabWidget::pane {
    border: 1px solid #c8d0dc;
    border-radius: 4px;
    background: #ffffff;
}
QTabBar::tab {
    background: #dce3ee;
    padding: 6px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #3a4a6a;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #1a3a6e;
    font-weight: 600;
}

QTableWidget {
    background-color: #ffffff;
    gridline-color: #dce3ee;
    border: 1px solid #c8d0dc;
}
QHeaderView::section {
    background-color: #dce3ee;
    font-weight: 600;
    padding: 4px;
    border: none;
}
QTableWidget::item:selected {
    background-color: #bdd3f9;
    color: #1e2230;
}

QMenuBar {
    background-color: #e8edf5;
}
QMenuBar::item:selected { background-color: #cdd7ea; }
QMenu { background-color: #ffffff; border: 1px solid #c8d0dc; }
QMenu::item:selected { background-color: #bdd3f9; }

QStatusBar { background-color: #e8edf5; }

QLabel#lblStatus { color: #3d5a8a; font-size: 12px; }

/* Left panel separator */
QWidget#leftPanel {
    background-color: #eaeef6;
    border-right: 1px solid #c8d0dc;
}

/* ── About dialog ── */
QLabel#lblAppTitle {
    font-size: 20px;
    font-weight: 700;
    color: #1a3a6e;
    padding-bottom: 4px;
}
QLabel#lblCourse {
    font-size: 13px;
    color: #3d5a8a;
}
QLabel#lblVersion {
    font-size: 11px;
    color: #7a8aaa;
}
QLabel#lblInstitution {
    font-size: 11px;
    color: #3d5a8a;
    font-style: italic;
}
QLabel#lblYear {
    font-size: 11px;
    color: #7a8aaa;
}
QGroupBox#gbInstructors, QGroupBox#gbStudents {
    font-size: 12px;
    font-weight: 700;
    color: #2d4070;
}
"""

DARK_QSS = """
QMainWindow, QWidget {
    background-color: #12151c;
    color: #d8dde8;
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #2e3650;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    font-weight: 600;
    color: #7eb4f8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QLabel#lblTitle {
    font-size: 17px;
    font-weight: 700;
    color: #8ec7ff;
    padding: 6px 0;
}

QComboBox, QDoubleSpinBox, QSpinBox {
    background-color: #1d2135;
    border: 1px solid #2e3650;
    border-radius: 4px;
    padding: 3px 6px;
    min-height: 24px;
    color: #d8dde8;
}
QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover {
    border-color: #4d94ff;
}
QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
    border-color: #2d7aff;
}
QComboBox QAbstractItemView {
    background-color: #1d2135;
    selection-background-color: #2d4580;
    color: #d8dde8;
}

QPushButton {
    background-color: #2d5be3;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 6px 16px;
    font-weight: 600;
}
QPushButton:hover  { background-color: #3d6cf0; }
QPushButton:pressed{ background-color: #1a40b0; }

QPushButton#btnToggleTheme {
    background-color: #4a5568;
}
QPushButton#btnToggleTheme:hover { background-color: #5a6780; }

QPushButton#btnResetZoom {
    background-color: #2e4060;
}
QPushButton#btnResetZoom:hover { background-color: #3a5278; }

QPushButton#btnSimulate {
    background-color: #1a7a3c;
}
QPushButton#btnSimulate:hover { background-color: #22a050; }

QPushButton#btnExportNetlist,
QPushButton#btnExportReport {
    background-color: #b5600f;
}
QPushButton#btnExportNetlist:hover,
QPushButton#btnExportReport:hover { background-color: #d07415; }

QTabWidget::pane {
    border: 1px solid #2e3650;
    border-radius: 4px;
    background: #161926;
}
QTabBar::tab {
    background: #1d2135;
    padding: 6px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #8a9ab8;
}
QTabBar::tab:selected {
    background: #161926;
    color: #8ec7ff;
    font-weight: 600;
}

QTableWidget {
    background-color: #161926;
    gridline-color: #252c44;
    border: 1px solid #2e3650;
    color: #d8dde8;
}
QHeaderView::section {
    background-color: #1d2135;
    font-weight: 600;
    padding: 4px;
    border: none;
    color: #8ec7ff;
}
QTableWidget::item:selected {
    background-color: #2d4580;
    color: #ffffff;
}

QMenuBar {
    background-color: #161926;
    color: #d8dde8;
}
QMenuBar::item:selected { background-color: #1d2d50; }
QMenu { background-color: #1d2135; border: 1px solid #2e3650; color: #d8dde8; }
QMenu::item:selected { background-color: #2d4580; }

QStatusBar { background-color: #161926; color: #8a9ab8; }

QLabel#lblStatus { color: #6a9cd8; font-size: 12px; }

QWidget#leftPanel {
    background-color: #161926;
    border-right: 1px solid #2e3650;
}

/* ── About dialog ── */
QLabel#lblAppTitle {
    font-size: 20px;
    font-weight: 700;
    color: #8ec7ff;
    padding-bottom: 4px;
}
QLabel#lblCourse {
    font-size: 13px;
    color: #7eb4f8;
}
QLabel#lblVersion {
    font-size: 11px;
    color: #4a6080;
}
QLabel#lblInstitution {
    font-size: 11px;
    color: #7eb4f8;
    font-style: italic;
}
QLabel#lblYear {
    font-size: 11px;
    color: #4a6080;
}
QGroupBox#gbInstructors, QGroupBox#gbStudents {
    font-size: 12px;
    font-weight: 700;
    color: #7eb4f8;
}
"""
