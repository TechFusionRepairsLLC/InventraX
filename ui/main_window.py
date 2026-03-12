from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QAction, QMessageBox, QLabel, QVBoxLayout,
    QWidget, QTabWidget, QLineEdit, QFormLayout, QSpinBox, QPushButton,
    QHBoxLayout, QTextEdit, QFileDialog, QListWidget, QListWidgetItem,
    QComboBox, QFrame, QSizePolicy, QScrollArea, QGroupBox, QDialog,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QCheckBox, QSplitter
)
from PyQt5.QtGui import QPixmap, QFont, QColor, QPalette, QIcon, QBrush
from PyQt5.QtCore import Qt, pyqtSignal
from config.settings import (
    APP_TITLE, APP_VERSION, APP_WEBSITE, APP_DONATE_URL, APP_GITHUB,
    APP_DEFAULTS, APP_INFO, LOW_STOCK_THRESHOLD as _DEFAULT_LOW_STOCK,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
)
import webbrowser
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import pandas as pd
from core.barcode_tools import generate_qr, generate_qr_pixmap, open_scanner_dialog

# ── In-memory data stores ─────────────────────────────────────────────────────
inventory_data = {}
asset_data     = []
LOW_STOCK_THRESHOLD = 5

# ── App Settings ──────────────────────────────────────────────────────────────
APP_SETTINGS = {
    "theme":               "Teal Dark",
    "low_stock_threshold": 5,
    "font_size":           10,
    "confirm_deletes":     True,
    "startup_warning":     True,
}

# ── Theme Presets ─────────────────────────────────────────────────────────────
THEMES = {
    "Teal Dark": {
        "bg_dark": "#0F1117", "bg_panel": "#181C27", "bg_card": "#1E2333",
        "bg_input": "#252A3D", "accent": "#00D4AA", "accent_hover": "#00FFCC",
        "accent_dim": "#00897B", "danger": "#FF4757", "warning": "#FFB800",
        "text_primary": "#E8EAF6", "text_secondary": "#8892B0",
        "border": "#2D3454", "border_light": "#3D4470",
    },
    "Midnight Blue": {
        "bg_dark": "#080E1C", "bg_panel": "#0D1526", "bg_card": "#111E33",
        "bg_input": "#172440", "accent": "#4D9FFF", "accent_hover": "#7AB8FF",
        "accent_dim": "#2563EB", "danger": "#FF4757", "warning": "#FBBF24",
        "text_primary": "#E2E8F0", "text_secondary": "#7A8BAA",
        "border": "#1E3258", "border_light": "#2A4A7A",
    },
    "Purple Haze": {
        "bg_dark": "#0D0B14", "bg_panel": "#13101E", "bg_card": "#1A1628",
        "bg_input": "#221D35", "accent": "#A855F7", "accent_hover": "#C084FC",
        "accent_dim": "#7C3AED", "danger": "#F87171", "warning": "#FBBF24",
        "text_primary": "#EDE9FE", "text_secondary": "#9D8EC0",
        "border": "#2D2548", "border_light": "#3D3565",
    },
    "Crimson Night": {
        "bg_dark": "#0F0A0A", "bg_panel": "#1A0F0F", "bg_card": "#231414",
        "bg_input": "#2D1A1A", "accent": "#EF4444", "accent_hover": "#F87171",
        "accent_dim": "#B91C1C", "danger": "#FF6B6B", "warning": "#FBBF24",
        "text_primary": "#FEE2E2", "text_secondary": "#A87070",
        "border": "#3D1E1E", "border_light": "#5A2E2E",
    },
    "Amber Forge": {
        "bg_dark": "#0F0C07", "bg_panel": "#1A1409", "bg_card": "#231C0E",
        "bg_input": "#2D2412", "accent": "#F59E0B", "accent_hover": "#FCD34D",
        "accent_dim": "#B45309", "danger": "#EF4444", "warning": "#FDE68A",
        "text_primary": "#FEF3C7", "text_secondary": "#A88A4A",
        "border": "#3D2E10", "border_light": "#5A4418",
    },
    "Arctic Light": {
        "bg_dark": "#F0F4F8", "bg_panel": "#E2E8F0", "bg_card": "#FFFFFF",
        "bg_input": "#EDF2F7", "accent": "#0EA5E9", "accent_hover": "#38BDF8",
        "accent_dim": "#0284C7", "danger": "#EF4444", "warning": "#F59E0B",
        "text_primary": "#1A202C", "text_secondary": "#4A5568",
        "border": "#CBD5E0", "border_light": "#A0AEC0",
    },
    "Forest Green": {
        "bg_dark": "#060F08", "bg_panel": "#0A1A0D", "bg_card": "#0F2414",
        "bg_input": "#152E1A", "accent": "#22C55E", "accent_hover": "#4ADE80",
        "accent_dim": "#16A34A", "danger": "#EF4444", "warning": "#FBBF24",
        "text_primary": "#DCFCE7", "text_secondary": "#6EAA80",
        "border": "#1A3D22", "border_light": "#245530",
    },
}

COLORS = THEMES["Teal Dark"].copy()


def build_stylesheet(C, font_size=10):
    fs = font_size
    fs_sm = max(fs - 1, 8)
    return f"""
    QMainWindow, QWidget {{
        background-color: {C['bg_dark']};
        color: {C['text_primary']};
        font-family: 'Segoe UI', 'SF Pro Display', Arial, sans-serif;
        font-size: {fs}pt;
    }}
    QMenuBar {{
        background-color: {C['bg_panel']};
        color: {C['text_primary']};
        border-bottom: 1px solid {C['border']};
        padding: 2px 6px;
    }}
    QMenuBar::item:selected {{ background-color: {C['bg_input']}; color: {C['accent']}; border-radius: 4px; }}
    QMenu {{
        background-color: {C['bg_card']}; color: {C['text_primary']};
        border: 1px solid {C['border_light']}; border-radius: 6px; padding: 4px;
    }}
    QMenu::item:selected {{ background-color: {C['accent_dim']}; color: white; border-radius: 4px; }}
    QTabWidget::pane {{
        border: 1px solid {C['border']}; border-radius: 8px;
        background-color: {C['bg_panel']}; top: -1px;
    }}
    QTabBar::tab {{
        background-color: {C['bg_dark']}; color: {C['text_secondary']};
        border: 1px solid {C['border']}; border-bottom: none;
        padding: 10px 22px; margin-right: 2px;
        border-top-left-radius: 8px; border-top-right-radius: 8px; font-weight: 500;
    }}
    QTabBar::tab:selected {{ background-color: {C['bg_panel']}; color: {C['accent']}; border-color: {C['border_light']}; font-weight: 700; }}
    QTabBar::tab:hover:!selected {{ background-color: {C['bg_card']}; color: {C['text_primary']}; }}
    QLineEdit, QSpinBox, QTextEdit, QComboBox {{
        background-color: {C['bg_input']}; color: {C['text_primary']};
        border: 1px solid {C['border']}; border-radius: 6px;
        padding: 7px 11px; font-size: {fs}pt;
        selection-background-color: {C['accent_dim']};
    }}
    QLineEdit:focus, QSpinBox:focus, QTextEdit:focus, QComboBox:focus {{ border: 1.5px solid {C['accent']}; }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QComboBox QAbstractItemView {{
        background-color: {C['bg_card']}; color: {C['text_primary']};
        border: 1px solid {C['border_light']}; selection-background-color: {C['accent_dim']}; border-radius: 6px;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{ background-color: {C['bg_card']}; border: none; width: 18px; }}
    QPushButton {{
        background-color: {C['accent']}; color: {C['bg_dark']}; border: none;
        border-radius: 6px; padding: 8px 18px; font-weight: 700; font-size: {fs}pt;
    }}
    QPushButton:hover {{ background-color: {C['accent_hover']}; }}
    QPushButton:pressed {{ background-color: {C['accent_dim']}; }}
    QPushButton#danger_btn {{ background-color: transparent; color: {C['danger']}; border: 1.5px solid {C['danger']}; }}
    QPushButton#danger_btn:hover {{ background-color: {C['danger']}; color: white; }}
    QPushButton#secondary_btn {{ background-color: transparent; color: {C['accent']}; border: 1.5px solid {C['accent']}; }}
    QPushButton#secondary_btn:hover {{ background-color: {C['accent']}; color: {C['bg_dark']}; }}
    QPushButton#neutral_btn {{ background-color: {C['bg_card']}; color: {C['text_primary']}; border: 1px solid {C['border_light']}; }}
    QPushButton#neutral_btn:hover {{ background-color: {C['bg_input']}; }}
    QLabel {{ color: {C['text_primary']}; background-color: transparent; }}
    QListWidget {{
        background-color: {C['bg_input']}; color: {C['text_primary']};
        border: 1px solid {C['border']}; border-radius: 6px; padding: 4px;
        alternate-background-color: {C['bg_card']};
    }}
    QListWidget::item {{ padding: 8px 10px; border-radius: 4px; }}
    QListWidget::item:selected {{ background-color: {C['accent_dim']}; color: white; }}
    QListWidget::item:hover {{ background-color: {C['bg_card']}; }}
    QTableWidget {{
        background-color: {C['bg_input']}; color: {C['text_primary']};
        border: 1px solid {C['border']}; border-radius: 6px;
        gridline-color: {C['border']}; alternate-background-color: {C['bg_card']};
        selection-background-color: {C['accent_dim']};
    }}
    QTableWidget::item {{ padding: 6px 8px; }}
    QTableWidget::item:selected {{ background-color: {C['accent_dim']}; color: white; }}
    QHeaderView::section {{
        background-color: {C['bg_panel']}; color: {C['text_secondary']};
        border: none; border-bottom: 2px solid {C['accent']};
        padding: 6px 10px; font-weight: 700; font-size: {fs_sm}pt; letter-spacing: 0.8px;
    }}
    QGroupBox {{
        border: 1px solid {C['border']}; border-radius: 8px; margin-top: 14px;
        padding: 10px 8px 8px 8px; color: {C['text_secondary']};
        font-size: {fs_sm}pt; font-weight: 600; letter-spacing: 0.8px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; subcontrol-position: top left;
        padding: 0 8px; color: {C['accent']}; letter-spacing: 1.2px;
    }}
    QScrollBar:vertical {{ background: {C['bg_dark']}; width: 8px; border-radius: 4px; }}
    QScrollBar::handle:vertical {{ background: {C['border_light']}; border-radius: 4px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {C['accent_dim']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: {C['bg_dark']}; height: 8px; border-radius: 4px; }}
    QScrollBar::handle:horizontal {{ background: {C['border_light']}; border-radius: 4px; }}
    QFormLayout QLabel {{
        color: {C['text_secondary']}; font-size: {fs_sm}pt;
        font-weight: 600; letter-spacing: 0.5px;
    }}
    QDialog {{ background-color: {C['bg_panel']}; }}
    QCheckBox {{ color: {C['text_primary']}; spacing: 8px; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px; border: 1.5px solid {C['border_light']};
        border-radius: 3px; background-color: {C['bg_input']};
    }}
    QCheckBox::indicator:checked {{ background-color: {C['accent']}; border-color: {C['accent']}; }}
    QSplitter::handle {{ background-color: {C['border']}; width: 2px; height: 2px; }}
    """


def open_url(url):
    webbrowser.open(url)


# ── Reusable Components ───────────────────────────────────────────────────────

class SectionHeader(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        C = COLORS
        self.setStyleSheet(
            f"color:{C['text_primary']};font-size:13pt;font-weight:700;"
            f"border-bottom:2px solid {C['accent']};padding-bottom:6px;background:transparent;"
        )


class StatusBadge(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self._neutral()

    def _neutral(self):
        C = COLORS
        self.setStyleSheet(f"color:{C['text_secondary']};font-size:9pt;background:transparent;border:none;padding:2px 6px;")

    def set_error(self, text):
        self.setText(text)
        C = COLORS
        self.setStyleSheet(f"color:{C['danger']};font-size:9pt;font-weight:600;"
                           f"background:rgba(255,71,87,0.12);border:1px solid {C['danger']};"
                           f"border-radius:4px;padding:3px 8px;")

    def set_success(self, text):
        self.setText(text)
        C = COLORS
        self.setStyleSheet(f"color:{C['accent']};font-size:9pt;font-weight:600;"
                           f"background:rgba(0,212,170,0.12);border:1px solid {C['accent_dim']};"
                           f"border-radius:4px;padding:3px 8px;")

    def set_warning(self, text):
        self.setText(text)
        C = COLORS
        self.setStyleSheet(f"color:{C['warning']};font-size:9pt;font-weight:600;"
                           f"background:rgba(255,184,0,0.12);border:1px solid {C['warning']};"
                           f"border-radius:4px;padding:3px 8px;")


def stat_card(title, value, color=None):
    C = COLORS
    color = color or C['accent']
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background-color: {C['bg_card']};
            border: 1px solid {C['border']};
            border-left: 3px solid {color};
            border-radius: 8px;
        }}
    """)
    layout = QVBoxLayout()
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(2)
    t = QLabel(title.upper())
    t.setStyleSheet(f"color:{C['text_secondary']};font-size:8pt;font-weight:700;"
                    f"letter-spacing:1px;background:transparent;border:none;")
    v = QLabel(str(value))
    v.setStyleSheet(f"color:{color};font-size:20pt;font-weight:800;background:transparent;border:none;")
    layout.addWidget(t)
    layout.addWidget(v)
    card.setLayout(layout)
    return card, v


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS DIALOG
# ══════════════════════════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    theme_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings — InventraX")
        self.setMinimumWidth(560)
        self.setMinimumHeight(500)
        self._build_ui()

    def _build_ui(self):
        C = COLORS
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(16)

        title = QLabel("⚙   Application Settings")
        title.setStyleSheet(
            f"font-size:14pt;font-weight:800;color:{C['text_primary']};"
            f"background:transparent;border-bottom:2px solid {C['accent']};padding-bottom:6px;"
        )
        layout.addWidget(title)

        # ── Theme ──────────────────────────────────────────────────────────
        theme_group = QGroupBox("UI Color Theme")
        tg = QVBoxLayout(); tg.setSpacing(10)

        hint = QLabel("Select a preset theme. The preview updates instantly.")
        hint.setStyleSheet(f"color:{C['text_secondary']};font-size:9pt;background:transparent;border:none;")
        tg.addWidget(hint)

        self._theme_btns = {}
        row1 = QHBoxLayout(); row1.setSpacing(8)
        row2 = QHBoxLayout(); row2.setSpacing(8)
        names = list(THEMES.keys())

        for i, name in enumerate(names):
            p = THEMES[name]
            btn = QPushButton(f"● {name}")
            btn.setCheckable(True)
            btn.setChecked(APP_SETTINGS["theme"] == name)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {p['bg_card']};
                    color: {p['accent']};
                    border: 2px solid {p['border_light']};
                    border-radius: 6px;
                    padding: 9px 8px;
                    font-size: 8.5pt;
                    font-weight: 600;
                    min-width: 110px;
                }}
                QPushButton:checked {{ border: 2.5px solid {p['accent']}; }}
                QPushButton:hover   {{ border-color: {p['accent']}; }}
            """)
            btn.clicked.connect(lambda _, n=name: self._select_theme(n))
            self._theme_btns[name] = btn
            if i < 4: row1.addWidget(btn)
            else:      row2.addWidget(btn)

        row2.addStretch()
        tg.addLayout(row1)
        tg.addLayout(row2)
        theme_group.setLayout(tg)
        layout.addWidget(theme_group)

        # ── General ────────────────────────────────────────────────────────
        gen_group = QGroupBox("General Settings")
        gen = QFormLayout(); gen.setSpacing(10); gen.setLabelAlignment(Qt.AlignRight)

        self.low_stock_spin = QSpinBox()
        self.low_stock_spin.setRange(1, 200)
        self.low_stock_spin.setValue(APP_SETTINGS["low_stock_threshold"])
        self.low_stock_spin.setFixedWidth(100)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 16)
        self.font_spin.setValue(APP_SETTINGS["font_size"])
        self.font_spin.setFixedWidth(100)
        self.font_spin.setSuffix(" pt")

        self.confirm_chk = QCheckBox("Ask for confirmation before deleting items or assets")
        self.confirm_chk.setChecked(APP_SETTINGS["confirm_deletes"])

        self.startup_chk = QCheckBox("Show save reminder on startup")
        self.startup_chk.setChecked(APP_SETTINGS["startup_warning"])

        gen.addRow("Low Stock Alert ≤", self.low_stock_spin)
        gen.addRow("Interface Font Size:", self.font_spin)
        gen.addRow("", self.confirm_chk)
        gen.addRow("", self.startup_chk)
        gen_group.setLayout(gen)
        layout.addWidget(gen_group)

        # ── About ──────────────────────────────────────────────────────────
        about_group = QGroupBox("About")
        about_layout = QVBoxLayout()
        about_text = QLabel(
            "InventraX  —  Inventory & Asset Management Platform\n"
            "Created by Alejandro X. Solis  ·  TechFusion Repairs LLC  ·  Version 2.0"
        )
        about_text.setStyleSheet(f"color:{C['text_secondary']};font-size:9pt;background:transparent;border:none;")
        about_layout.addWidget(about_text)
        about_group.setLayout(about_layout)
        layout.addWidget(about_group)

        # ── Buttons ────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("neutral_btn")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("Apply & Close")
        apply_btn.setFixedWidth(150)
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def _select_theme(self, name):
        for n, btn in self._theme_btns.items():
            btn.setChecked(n == name)
        COLORS.update(THEMES[name])
        APP_SETTINGS["theme"] = name
        self.theme_changed.emit()

    def _apply(self):
        global LOW_STOCK_THRESHOLD
        APP_SETTINGS["low_stock_threshold"] = self.low_stock_spin.value()
        APP_SETTINGS["font_size"]           = self.font_spin.value()
        APP_SETTINGS["confirm_deletes"]     = self.confirm_chk.isChecked()
        APP_SETTINGS["startup_warning"]     = self.startup_chk.isChecked()
        LOW_STOCK_THRESHOLD = APP_SETTINGS["low_stock_threshold"]
        self.accept()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class _BarcodePreviewDialog(QDialog):
    """Small dialog that shows the generated QR code with the item name."""
    def __init__(self, item_name: str, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"QR Code — {item_name}")
        self.setFixedSize(320, 380)
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        title = QLabel(item_name)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:12pt; font-weight:700;")
        layout.addWidget(title)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        # Try to load from file first; fall back to generating pixmap in-memory
        pix = QPixmap(image_path)
        if pix.isNull():
            pix = generate_qr_pixmap(item_name, size=220)
        if pix and not pix.isNull():
            img_label.setPixmap(pix.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            img_label.setText("(preview unavailable)")
        img_label.setStyleSheet(
            "background:#FFFFFF; border:1px solid #2D3454; border-radius:8px; padding:10px;")
        layout.addWidget(img_label)

        path_label = QLabel(image_path)
        path_label.setAlignment(Qt.AlignCenter)
        path_label.setWordWrap(True)
        path_label.setStyleSheet("font-size:8pt; color:#8892B0;")
        layout.addWidget(path_label)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)
        self.setLayout(layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)
        self._apply_theme()
        self.init_ui()
        self._setup_shortcuts()
        if APP_SETTINGS.get("startup_warning", True):
            self.show_startup_warning()
        # Defer DB load until after window is fully painted
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(200, self._load_db_into_memory)
        QTimer.singleShot(500, self.update_dashboard_summary)

    def _load_db_into_memory(self):
        """Load persisted data from SQLite then refresh all tables."""
        try:
            from core.inventory     import load_inventory_to_memory
            from core.asset_manager import load_assets_to_memory
            n_inv   = load_inventory_to_memory(inventory_data)
            n_asset = load_assets_to_memory(asset_data)
            import logging
            logging.getLogger(__name__).info(
                "Loaded %d inventory items and %d assets from DB", n_inv, n_asset
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Could not load from DB: %s", exc)
        # Refresh tables regardless of whether DB load succeeded
        try: self.refresh_inventory_table()
        except Exception: pass
        try: self.refresh_asset_table()
        except Exception: pass

    def _apply_theme(self):
        self.setStyleSheet(build_stylesheet(COLORS, APP_SETTINGS.get("font_size", 10)))

    def show_startup_warning(self):
        if not APP_SETTINGS.get("startup_warning", True):
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Welcome to InventraX")
        msg.setText(
            "InventraX saves your data automatically when you close.\n\n"
            "\u2022 Data stored in:   data/inventrax.db\n"
            "\u2022 Backups in:        backups/\n"
            "\u2022 Manual export:     File \u2192 Download Inventory File"
        )
        msg.setIcon(QMessageBox.Information)
        msg.addButton("Got it", QMessageBox.AcceptRole)
        dont_show = QCheckBox("Don\u2019t show this again")
        msg.setCheckBox(dont_show)
        msg.exec_()
        if dont_show.isChecked():
            APP_SETTINGS["startup_warning"] = False

    def init_ui(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        file_menu.addAction(self._action("Upload Inventory File",   self.upload_inventory_file))
        file_menu.addAction(self._action("Download Inventory File", self.download_inventory_file))

        support_menu = menubar.addMenu("Support")
        support_menu.addAction(self._action("Contact Us",    self.show_contact_dialog))
        support_menu.addAction(self._action("Visit Website", lambda: open_url(APP_INFO["website"])))
        support_menu.addAction(self._action("Donate",        lambda: open_url(APP_INFO["donate"])))
        support_menu.addAction(self._action("GitHub",        lambda: open_url(APP_INFO["github"])))

        settings_menu = menubar.addMenu("⚙  Settings")
        settings_menu.addAction(self._action("Open Settings…", self.open_settings))

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.create_dashboard_tab(), "  Dashboard  ")
        self.tabs.addTab(self.create_inventory_tab(), "  Inventory  ")
        self.tabs.addTab(self.create_assets_tab(),    "  Assets  ")
        self.tabs.addTab(self.create_reports_tab(),   "  Reports  ")

        root = QWidget()
        rl = QVBoxLayout()
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self.tabs)
        rl.addWidget(self._build_footer())
        root.setLayout(rl)
        self.setCentralWidget(root)

    def _action(self, label, slot):
        a = QAction(label, self)
        a.triggered.connect(slot)
        return a

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.theme_changed.connect(self._apply_theme)
        dlg.exec_()
        self._apply_theme()
        self.update_dashboard_summary()

    # ── Footer ────────────────────────────────────────────────────────────────
    def _build_footer(self):
        C = COLORS
        f = QFrame()
        f.setFixedHeight(44)
        f.setStyleSheet(f"QFrame{{background-color:{C['bg_panel']};border-top:1px solid {C['border']};}}")
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 0, 16, 0)
        logo = QLabel()
        pix = QPixmap("assets/icons/TechFusion.png")
        if not pix.isNull():
            logo.setPixmap(pix.scaled(26, 26, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(logo)
        credit = QLabel("Created by  <b>Alejandro X. Solis</b>  ·  TechFusion Repairs LLC")
        credit.setStyleSheet(f"color:{C['text_secondary']};font-size:9pt;background:transparent;border:none;")
        layout.addWidget(credit)
        layout.addStretch()
        ver = QLabel("InventraX  v2.0")
        ver.setStyleSheet(f"color:{C['border_light']};font-size:8pt;background:transparent;border:none;")
        layout.addWidget(ver)
        f.setLayout(layout)
        return f

    # ── Dialogs ───────────────────────────────────────────────────────────────
    def show_contact_dialog(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Contact & Support")
        msg.setText("<b>TechFusion Repairs LLC</b><br><br>"
                    "📧  TechFusionRepairs@gmail.com<br>"
                    "🌐  alejandroxsolis93.wixsite.com<br>"
                    "💸  PayPal Donation<br>"
                    "🔗  github.com/TechFusionRepairsLLC")
        pix = QPixmap("assets/icons/TechFusion.png")
        if not pix.isNull():
            msg.setIconPixmap(pix.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        msg.exec_()

    def _info(self, text):
        m = QMessageBox(self); m.setWindowTitle("InventraX")
        m.setText(text); m.setIcon(QMessageBox.Information); m.exec_()

    def _warn(self, text):
        m = QMessageBox(self); m.setWindowTitle("InventraX")
        m.setText(text); m.setIcon(QMessageBox.Warning); m.exec_()

    def _confirm(self, text):
        if not APP_SETTINGS.get("confirm_deletes", True):
            return True
        r = QMessageBox.question(self, "Confirm Delete", text,
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return r == QMessageBox.Yes

    # ── File I/O ──────────────────────────────────────────────────────────────
    def upload_inventory_file(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Open Inventory File", "", "Excel Files (*.xlsx *.xls)")
        if fn:
            try:
                df = pd.read_excel(fn)
                for _, row in df.iterrows():
                    name = str(row['Item Name']).strip()
                    inventory_data[name] = {
                        'category':     str(row.get('Category', '')),
                        'quantity':     int(row.get('Quantity', 0)),
                        'location':     str(row.get('Location', '')),
                        'usage_count':  int(row.get('Usage Count', 0)),
                        'price':        float(row.get('Price', 0.0)),
                        'sku':          str(row.get('SKU', '')),
                        'sold_count':   int(row.get('Sold Count', 0)),
                        'sold_revenue': float(row.get('Sold Revenue', 0.0)),
                    }
                self._info(f"Loaded {len(df)} items into inventory.")
                self.refresh_inventory_table()
                self.update_dashboard_summary()
            except Exception as e:
                self._warn(f"Failed to load file:\n{e}")

    def download_inventory_file(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Save Inventory File", "inventory.xlsx", "Excel Files (*.xlsx)")
        if fn:
            rows = [{
                'Item Name': n, 'Category': d['category'], 'Quantity': d['quantity'],
                'Location': d['location'], 'Usage Count': d.get('usage_count', 0),
                'Price': d.get('price', 0.0), 'SKU': d.get('sku', ''),
                'Sold Count': d.get('sold_count', 0), 'Sold Revenue': d.get('sold_revenue', 0.0),
            } for n, d in inventory_data.items()]
            pd.DataFrame(rows).to_excel(fn, index=False)
            self._info("Inventory exported successfully.")

    # ══════════════════════════════════════════════════════════════════════════
    # DASHBOARD TAB
    # ══════════════════════════════════════════════════════════════════════════
    def create_dashboard_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Header
        hrow = QHBoxLayout()
        logo = QLabel()
        pix = QPixmap("assets/icons/inventrax_logo.png")
        if not pix.isNull():
            logo.setPixmap(pix.scaled(68, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        hrow.addWidget(logo)
        tc = QVBoxLayout(); tc.setSpacing(2)
        t1 = QLabel("InventraX")
        t1.setStyleSheet(f"color:{COLORS['text_primary']};font-size:26pt;font-weight:800;background:transparent;")
        t2 = QLabel("Inventory & Asset Management Platform")
        t2.setStyleSheet(f"color:{COLORS['text_secondary']};font-size:11pt;background:transparent;")
        tc.addWidget(t1); tc.addWidget(t2)
        hrow.addLayout(tc); hrow.addStretch()
        layout.addLayout(hrow)

        div = QFrame(); div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"color:{COLORS['border']};"); layout.addWidget(div)

        # Stats
        sr = QHBoxLayout(); sr.setSpacing(12)
        self._oos_card,   self._oos_val   = stat_card("Out of Stock",  "0", COLORS['danger'])
        self._low_card,   self._low_val   = stat_card("Low Stock",     "0", COLORS['warning'])
        self._total_card, self._total_val = stat_card("Total Items",   "0", COLORS['accent'])
        self._rev_card,   self._rev_val   = stat_card("Sales Revenue", "$0", COLORS['accent'])
        for c in [self._oos_card, self._low_card, self._total_card, self._rev_card]:
            sr.addWidget(c)
        layout.addLayout(sr)

        # Popular items
        pg = QGroupBox("Top Popular Items")
        pl = QVBoxLayout()
        self._popular_label = QLabel("No data yet.")
        self._popular_label.setStyleSheet(
            f"color:{COLORS['text_secondary']};font-size:10pt;background:transparent;border:none;")
        self._popular_label.setWordWrap(True)
        pl.addWidget(self._popular_label)
        pg.setLayout(pl)
        layout.addWidget(pg)

        # ── Live mini-chart (Step 8) ──────────────────────────────────────
        try:
            self._dash_fig, self._dash_ax = plt.subplots(figsize=(6, 2.4),
                                                           facecolor="#1E2333")
            self._dash_ax.set_facecolor("#252A3D")
            self._dash_canvas = FigureCanvas(self._dash_fig)
            self._dash_canvas.setMinimumHeight(160)
            self._dash_canvas.setMaximumHeight(200)
            layout.addWidget(SectionHeader("Inventory by Category"))
            layout.addWidget(self._dash_canvas)
            # Defer the first draw until after window is shown
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(300, self._refresh_dash_chart)
        except Exception:
            pass   # chart is optional — never block startup

        # Guide
        gg = QGroupBox("Getting Started")
        gl = QVBoxLayout(); gl.setSpacing(8)
        steps = [
            ("1  Add Inventory",  "Inventory tab → fill in fields → Save Item."),
            ("2  Edit Items",     "Click any table row to load it for editing, then Save."),
            ("3  Track Assets",   "Assets tab → assign assets to users/departments."),
            ("4  Edit Assets",    "Click any asset row to load it for quick editing or status change."),
            ("5  Run Reports",    "Reports tab → select chart type → Generate Report."),
            ("6  Save Your Work", "File → Download Inventory File  (Excel)."),
            ("7  Change Theme",   "⚙ Settings menu → pick any of 7 color themes instantly."),
        ]
        for st, sd in steps:
            row = QHBoxLayout()
            tl = QLabel(st); tl.setFixedWidth(160)
            tl.setStyleSheet(
                f"color:{COLORS['accent']};font-weight:700;font-size:9pt;background:transparent;border:none;")
            dl = QLabel(sd); dl.setWordWrap(True)
            dl.setStyleSheet(
                f"color:{COLORS['text_secondary']};font-size:9pt;background:transparent;border:none;")
            row.addWidget(tl); row.addWidget(dl)
            gl.addLayout(row)
        gg.setLayout(gl)
        layout.addWidget(gg)
        layout.addStretch()

        page.setLayout(layout)
        scroll.setWidget(page)
        self.update_dashboard_summary()
        return scroll

    def update_dashboard_summary(self):
        oos   = sum(1 for d in inventory_data.values() if d['quantity'] == 0)
        low   = sum(1 for d in inventory_data.values() if 0 < d['quantity'] <= LOW_STOCK_THRESHOLD)
        total = len(inventory_data)
        rev   = sum(d.get('sold_revenue', 0) for d in inventory_data.values())
        if hasattr(self, '_oos_val'):
            self._oos_val.setText(str(oos))
            self._low_val.setText(str(low))
            self._total_val.setText(str(total))
            self._rev_val.setText(f"${rev:,.2f}")
        popular = sorted(inventory_data.items(), key=lambda x: x[1].get('usage_count', 0), reverse=True)[:3]
        if hasattr(self, '_popular_label'):
            self._popular_label.setText(
                "   ·   ".join([f"{n}  ({d.get('usage_count', 0)} uses)" for n, d in popular])
                if popular else "No usage data available yet."
            )
        # Step 8: refresh live dashboard chart
        if hasattr(self, '_dash_canvas'):
            self._refresh_dash_chart()

    def _refresh_dash_chart(self):
        """Redraw the dashboard mini bar-chart from current inventory_data."""
        try:
            ax = self._dash_ax
            ax.clear()
            ax.set_facecolor("#252A3D")
            for spine in ax.spines.values():
                spine.set_color("#2D3454")
            ax.tick_params(colors="#8892B0", labelsize=8)

            # Build category totals
            totals = {}
            for d in inventory_data.values():
                cat = d.get("category") or "Other"
                totals[cat] = totals.get(cat, 0) + int(d.get("quantity", 0))

            if totals:
                # Show top 8 categories to keep chart readable
                top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:8]
                cats, qtys = zip(*top)
                colours = [
                    "#00D4AA","#FFB800","#FF4757","#4D9FFF",
                    "#A855F7","#22C55E","#F59E0B","#EF4444",
                ]
                bars = ax.bar(cats, qtys, color=colours[:len(cats)], width=0.6)
                for bar in bars:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + 0.05,
                            str(int(bar.get_height())),
                            ha="center", va="bottom",
                            color="#E8EAF6", fontsize=7)
                ax.set_ylabel("Qty", color="#8892B0", fontsize=8)
                ax.tick_params(axis="x", rotation=20)
            else:
                ax.text(0.5, 0.5, "Add inventory items to see the chart",
                        ha="center", va="center",
                        color="#4D5A8A", fontsize=9,
                        transform=ax.transAxes)

            self._dash_fig.tight_layout(pad=0.8)
            self._dash_canvas.draw()
        except Exception:
            pass   # never crash the dashboard on a chart error

    # ══════════════════════════════════════════════════════════════════════════
    # INVENTORY TAB — click-to-edit table
    # ══════════════════════════════════════════════════════════════════════════
    def create_inventory_tab(self):
        C = COLORS
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        # Left: form panel
        lw = QWidget(); lw.setMinimumWidth(290); lw.setMaximumWidth(360)
        left = QVBoxLayout(); left.setContentsMargins(16, 16, 12, 16); left.setSpacing(10)

        self._inv_mode_label = QLabel("➕  New Item")
        self._inv_mode_label.setStyleSheet(
            f"color:{C['accent']};font-size:11pt;font-weight:700;background:transparent;")
        left.addWidget(self._inv_mode_label)

        fg = QGroupBox("Item Details")
        form = QFormLayout(); form.setSpacing(8); form.setLabelAlignment(Qt.AlignRight)
        self.item_name_input  = QLineEdit(); self.item_name_input.setPlaceholderText("e.g. USB-C Hub")
        self.category_input   = QLineEdit(); self.category_input.setPlaceholderText("e.g. Electronics")
        self.quantity_input   = QSpinBox();  self.quantity_input.setRange(0, 99999)
        self.location_input   = QLineEdit(); self.location_input.setPlaceholderText("e.g. Shelf A-3")
        self.price_input      = QLineEdit(); self.price_input.setPlaceholderText("0.00")
        self.sku_input        = QLineEdit(); self.sku_input.setPlaceholderText("SKU-00001")
        self.sold_count_input = QSpinBox();  self.sold_count_input.setRange(0, 99999)
        form.addRow("Item Name",  self.item_name_input)
        form.addRow("Category",   self.category_input)
        form.addRow("Quantity",   self.quantity_input)
        form.addRow("Location",   self.location_input)
        form.addRow("Price ($)",  self.price_input)
        form.addRow("SKU",        self.sku_input)
        form.addRow("Sold Qty",   self.sold_count_input)
        fg.setLayout(form)
        left.addWidget(fg)

        btn_scan = QPushButton("📷  Scan Barcode / QR Code")
        btn_scan.setObjectName("secondary_btn")
        btn_scan.clicked.connect(self._scan_inventory_item)
        btn_scan.setToolTip("Scan a barcode or QR code to look up and load the matching item")
        left.addWidget(btn_scan)

        _div1 = QFrame(); _div1.setFrameShape(QFrame.HLine)
        _div1.setStyleSheet(f"color:{C['border']};"); left.addWidget(_div1)

        btn_save    = QPushButton("💾  Save Item");     btn_save.clicked.connect(self.add_or_update_inventory)
        btn_clear   = QPushButton("✕  Clear Form");        btn_clear.setObjectName("neutral_btn"); btn_clear.clicked.connect(self._clear_inv_form)
        btn_remove  = QPushButton("🗑  Delete Item");   btn_remove.setObjectName("danger_btn");  btn_remove.clicked.connect(self.remove_inventory_item)
        btn_barcode = QPushButton("QR  Generate Barcode");     btn_barcode.setObjectName("secondary_btn"); btn_barcode.clicked.connect(self.generate_barcode_for_item)
        for b in [btn_save, btn_clear, btn_remove, btn_barcode]:
            left.addWidget(b)

        self.inventory_status = StatusBadge("Click a row to edit, or fill in details to add a new item.")
        left.addWidget(self.inventory_status)
        left.addStretch()
        lw.setLayout(left)

        # Right: search + table
        rw = QWidget()
        right = QVBoxLayout(); right.setContentsMargins(12, 16, 16, 16); right.setSpacing(10)
        right.addWidget(SectionHeader("Inventory Items"))

        self.inv_search = QLineEdit()
        self.inv_search.setPlaceholderText("🔍  Filter by name, category, location, or SKU…")
        self.inv_search.textChanged.connect(self._filter_inventory_table)
        right.addWidget(self.inv_search)

        self.inv_table = QTableWidget()
        self.inv_table.setColumnCount(8)
        self.inv_table.setHorizontalHeaderLabels(
            ["Item Name", "Category", "Qty", "Location", "Price", "SKU", "Sold", "Revenue"])
        self.inv_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.inv_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.inv_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.inv_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.inv_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.inv_table.setAlternatingRowColors(True)
        self.inv_table.verticalHeader().setVisible(False)
        self.inv_table.setSortingEnabled(True)
        self.inv_table.itemSelectionChanged.connect(self._on_inv_row_selected)
        self.inv_table.itemDoubleClicked.connect(self._on_inv_row_double_clicked)
        right.addWidget(self.inv_table)

        tip = QLabel("💡 Click any row to load it into the form for editing.")
        tip.setStyleSheet(f"color:{C['text_secondary']};font-size:8pt;background:transparent;")
        right.addWidget(tip)

        rw.setLayout(right)
        splitter.addWidget(lw)
        splitter.addWidget(rw)
        splitter.setStretchFactor(1, 3)
        self.refresh_inventory_table()
        return splitter

    def refresh_inventory_table(self):
        C = COLORS
        self.inv_table.setSortingEnabled(False)
        self.inv_table.setRowCount(0)
        for name, d in inventory_data.items():
            r = self.inv_table.rowCount()
            self.inv_table.insertRow(r)
            qty = d['quantity']
            cells = [name, d['category'], str(qty), d['location'],
                     f"${d.get('price',0):.2f}", d.get('sku',''),
                     str(d.get('sold_count',0)), f"${d.get('sold_revenue',0):.2f}"]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                if qty == 0:
                    item.setForeground(QBrush(QColor(C['danger'])))
                elif qty <= LOW_STOCK_THRESHOLD:
                    item.setForeground(QBrush(QColor(C['warning'])))
                self.inv_table.setItem(r, col, item)
        self.inv_table.setSortingEnabled(True)

    def _filter_inventory_table(self):
        term = self.inv_search.text().strip().lower()
        for r in range(self.inv_table.rowCount()):
            match = any(
                term in (self.inv_table.item(r, c).text().lower() if self.inv_table.item(r, c) else "")
                for c in range(self.inv_table.columnCount())
            )
            self.inv_table.setRowHidden(r, not match)

    def _on_inv_row_selected(self):
        rows = self.inv_table.selectionModel().selectedRows()
        if not rows: return
        r = rows[0].row()
        name = self.inv_table.item(r, 0).text() if self.inv_table.item(r, 0) else ""
        if name not in inventory_data: return
        d = inventory_data[name]
        self.item_name_input.setText(name)
        self.category_input.setText(d['category'])
        self.quantity_input.setValue(d['quantity'])
        self.location_input.setText(d['location'])
        self.price_input.setText(str(d.get('price', '')))
        self.sku_input.setText(d.get('sku', ''))
        self.sold_count_input.setValue(d.get('sold_count', 0))
        self._inv_mode_label.setText(f"✏️  Editing:  {name}")
        self.inventory_status.set_success(f"Loaded '{name}' — modify fields and click Save.")

    def _on_inv_row_double_clicked(self, item):
        """Step 7: Open full ItemEditorDialog on double-click."""
        row = item.row()
        name_item = self.inv_table.item(row, 0)
        if not name_item:
            return
        name = name_item.text()
        if name not in inventory_data:
            return
        try:
            from ui.item_editor import ItemEditorDialog
            from PyQt5.QtWidgets import QDialog
            dlg = ItemEditorDialog(parent=self, item_name=name,
                                   item_data=inventory_data[name])
            if dlg.exec_() == QDialog.Accepted:
                new_name = dlg.result_name()
                new_data = dlg.result_data()
                if dlg.was_renamed() and new_name != name:
                    del inventory_data[name]
                inventory_data[new_name] = new_data
                self.refresh_inventory_table()
                self.update_dashboard_summary()
                self.inventory_status.set_success(
                    f"Saved '{new_name}'" + (f" (renamed from '{name}')"
                    if dlg.was_renamed() else "")
                )
        except Exception as exc:
            self.inventory_status.set_error(f"Editor error: {exc}")

    def _clear_inv_form(self):
        for w in [self.item_name_input, self.category_input, self.location_input,
                  self.price_input, self.sku_input]:
            w.clear()
        self.quantity_input.setValue(0)
        self.sold_count_input.setValue(0)
        self.inv_table.clearSelection()
        self._inv_mode_label.setText("➕  New Item")
        self.inventory_status._neutral()
        self.inventory_status.setText("Fill in details to add a new item.")

    def _scan_inventory_item(self):
        """Open scanner dialog; if the scanned value matches an inventory item, load it into the form."""
        value = open_scanner_dialog(
            parent=self,
            prompt="Scan the item's barcode or QR code to look it up in inventory."
        )
        if not value:
            return
        # Direct name match
        if value in inventory_data:
            self._load_inv_item(value)
            self.inventory_status.set_success(f"Loaded '{value}' from scan.")
            return
        # SKU match
        for name, d in inventory_data.items():
            if d.get('sku', '').strip() == value:
                self._load_inv_item(name)
                self.inventory_status.set_success(f"Loaded '{name}' via SKU scan.")
                return
        # Partial / case-insensitive name match
        lower = value.lower()
        for name in inventory_data:
            if lower in name.lower():
                self._load_inv_item(name)
                self.inventory_status.set_success(f"Loaded '{name}' (partial match for '{value}').")
                return
        # Not found — pre-fill the name field so the user can add it
        self.item_name_input.setText(value)
        self._inv_mode_label.setText("➕  New Item (from scan)")
        self.inventory_status.set_warning(f"'{value}' not found — fill in details and save to add it.")

    def _load_inv_item(self, name: str):
        """Load inventory item data into the left-side form."""
        d = inventory_data[name]
        self.item_name_input.setText(name)
        self.category_input.setText(d['category'])
        self.quantity_input.setValue(d['quantity'])
        self.location_input.setText(d['location'])
        self.price_input.setText(str(d.get('price', '')))
        self.sku_input.setText(d.get('sku', ''))
        self.sold_count_input.setValue(d.get('sold_count', 0))
        self._inv_mode_label.setText(f"✏️  Editing:  {name}")
        # Also highlight the matching table row
        for r in range(self.inv_table.rowCount()):
            item = self.inv_table.item(r, 0)
            if item and item.text() == name:
                self.inv_table.selectRow(r)
                self.inv_table.scrollToItem(item)
                break

    def generate_barcode_for_item(self):
        name = self.item_name_input.text().strip()
        if not name:
            self.inventory_status.set_error("Enter an item name first.")
            return
        output_path = f"barcodes/{name}_barcode.png"
        ok = generate_qr(name, output_path)
        if ok:
            self.inventory_status.set_success(f"QR saved: {output_path}")
            # Show preview dialog
            dlg = _BarcodePreviewDialog(name, output_path, parent=self)
            dlg.exec_()
        else:
            self.inventory_status.set_error(
                "qrcode library not installed.  Run:  pip install qrcode[pil]")

    def add_or_update_inventory(self):
        name       = self.item_name_input.text().strip()
        category   = self.category_input.text().strip()
        quantity   = self.quantity_input.value()
        location   = self.location_input.text().strip()
        price_text = self.price_input.text().strip()
        sku        = self.sku_input.text().strip()
        sold_count = self.sold_count_input.value()
        try:
            price = float(price_text) if price_text else 0.0
        except ValueError:
            self.inventory_status.set_error("Invalid price — enter a number.")
            return
        if not name:
            self.inventory_status.set_error("Item name is required.")
            return

        if name in inventory_data:
            old = inventory_data[name]
            inventory_data[name].update({
                'quantity': quantity, 'category': category, 'location': location,
                'price': price, 'sku': sku, 'sold_count': sold_count,
                'sold_revenue': price * sold_count,
                'usage_count': old.get('usage_count', 0) + 1,
            })
            self.inventory_status.set_success(f"Updated '{name}'")
        else:
            inventory_data[name] = {
                'category': category, 'quantity': quantity, 'location': location,
                'usage_count': 1, 'price': price, 'sku': sku,
                'sold_count': sold_count, 'sold_revenue': price * sold_count,
            }
            self.inventory_status.set_success(f"Added '{name}'")

        if quantity == 0:
            self._warn(f"'{name}' is now out of stock!")
        elif quantity <= LOW_STOCK_THRESHOLD:
            self.inventory_status.set_warning(f"Low stock: '{name}' has only {quantity} left.")

        self.refresh_inventory_table()
        self.update_dashboard_summary()
        self._clear_inv_form()

    def remove_inventory_item(self):
        name = self.item_name_input.text().strip()
        if not name:
            self.inventory_status.set_error("Select a row or enter an item name first.")
            return
        if name not in inventory_data:
            self.inventory_status.set_error(f"'{name}' not found.")
            return
        if self._confirm(f"Permanently delete '{name}' from inventory?"):
            del inventory_data[name]
            self.inventory_status.set_success(f"Deleted '{name}'")
            self.refresh_inventory_table()
            self.update_dashboard_summary()
            self._clear_inv_form()

    # ══════════════════════════════════════════════════════════════════════════
    # ASSETS TAB — click-to-edit table
    # ══════════════════════════════════════════════════════════════════════════
    def create_assets_tab(self):
        C = COLORS
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        # Left: form
        lw = QWidget(); lw.setMinimumWidth(290); lw.setMaximumWidth(360)
        left = QVBoxLayout(); left.setContentsMargins(16, 16, 12, 16); left.setSpacing(10)

        self._asset_mode_label = QLabel("➕  New Asset")
        self._asset_mode_label.setStyleSheet(
            f"color:{C['accent']};font-size:11pt;font-weight:700;background:transparent;")
        left.addWidget(self._asset_mode_label)

        ag = QGroupBox("Asset Details")
        form = QFormLayout(); form.setSpacing(8); form.setLabelAlignment(Qt.AlignRight)
        self.asset_name_input     = QLineEdit(); self.asset_name_input.setPlaceholderText("e.g. MacBook Pro")
        self.assigned_to_input    = QLineEdit(); self.assigned_to_input.setPlaceholderText("e.g. John Doe")
        self.asset_location_input = QLineEdit(); self.asset_location_input.setPlaceholderText("e.g. Office 3B")
        self.asset_notes_input    = QLineEdit(); self.asset_notes_input.setPlaceholderText("Optional notes…")
        self.asset_status_combo   = QComboBox()
        self.asset_status_combo.addItems(["Active", "In Repair", "Retired", "Lost", "Available"])
        form.addRow("Asset Name",  self.asset_name_input)
        form.addRow("Assigned To", self.assigned_to_input)
        form.addRow("Location",    self.asset_location_input)
        form.addRow("Notes",       self.asset_notes_input)
        form.addRow("Status",      self.asset_status_combo)
        ag.setLayout(form)
        left.addWidget(ag)

        btn_scan_asset = QPushButton("📷  Scan Asset Barcode")
        btn_scan_asset.setObjectName("secondary_btn")
        btn_scan_asset.clicked.connect(self._scan_asset_item)
        btn_scan_asset.setToolTip("Scan an asset\'s QR code to look it up and load it for editing")
        left.addWidget(btn_scan_asset)

        _adiv = QFrame(); _adiv.setFrameShape(QFrame.HLine)
        _adiv.setStyleSheet(f"color:{C['border']};"); left.addWidget(_adiv)

        btn_save   = QPushButton("💾  Save Asset");  btn_save.clicked.connect(self.save_asset)
        btn_clear  = QPushButton("✕  Clear Form");      btn_clear.setObjectName("neutral_btn"); btn_clear.clicked.connect(self._clear_asset_form)
        btn_remove = QPushButton("🗑  Delete Asset"); btn_remove.setObjectName("danger_btn");  btn_remove.clicked.connect(self.delete_asset)
        for b in [btn_save, btn_clear, btn_remove]:
            left.addWidget(b)

        self.asset_status_badge = StatusBadge("Click an asset row to edit, or fill in fields to add new.")
        left.addWidget(self.asset_status_badge)
        left.addStretch()
        lw.setLayout(left)

        # Right: search + table
        rw = QWidget()
        right = QVBoxLayout(); right.setContentsMargins(12, 16, 16, 16); right.setSpacing(10)
        right.addWidget(SectionHeader("Assigned Assets"))

        self.asset_search = QLineEdit()
        self.asset_search.setPlaceholderText("🔍  Filter assets…")
        self.asset_search.textChanged.connect(self._filter_asset_table)
        right.addWidget(self.asset_search)

        self.asset_table = QTableWidget()
        self.asset_table.setColumnCount(5)
        self.asset_table.setHorizontalHeaderLabels(["Asset", "Assigned To", "Location", "Status", "Notes"])
        self.asset_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.asset_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.asset_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.asset_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.asset_table.setAlternatingRowColors(True)
        self.asset_table.verticalHeader().setVisible(False)
        self.asset_table.setSortingEnabled(True)
        self.asset_table.itemSelectionChanged.connect(self._on_asset_row_selected)
        right.addWidget(self.asset_table)

        tip = QLabel("💡 Click any row to load it into the form for editing.")
        tip.setStyleSheet(f"color:{C['text_secondary']};font-size:8pt;background:transparent;")
        right.addWidget(tip)

        rw.setLayout(right)
        splitter.addWidget(lw)
        splitter.addWidget(rw)
        splitter.setStretchFactor(1, 3)
        self._editing_asset_index = None
        self.refresh_asset_table()
        return splitter

    def refresh_asset_table(self):
        C = COLORS
        STATUS_COLORS = {
            "Active":    C['accent'],   "In Repair": C['warning'],
            "Retired":   C['text_secondary'], "Lost": C['danger'],
            "Available": "#7AB8FF",
        }
        self.asset_table.setSortingEnabled(False)
        self.asset_table.setRowCount(0)
        for entry in asset_data:
            r = self.asset_table.rowCount()
            self.asset_table.insertRow(r)
            status = entry.get('status', 'Active')
            color  = STATUS_COLORS.get(status, C['text_primary'])
            for col, val in enumerate([entry['asset'], entry['assigned_to'],
                                        entry['location'], status, entry.get('notes', '')]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                if col == 3:
                    item.setForeground(QBrush(QColor(color)))
                self.asset_table.setItem(r, col, item)
        self.asset_table.setSortingEnabled(True)

    def _filter_asset_table(self):
        term = self.asset_search.text().strip().lower()
        for r in range(self.asset_table.rowCount()):
            match = any(
                term in (self.asset_table.item(r, c).text().lower() if self.asset_table.item(r, c) else "")
                for c in range(self.asset_table.columnCount())
            )
            self.asset_table.setRowHidden(r, not match)

    def _on_asset_row_selected(self):
        rows = self.asset_table.selectionModel().selectedRows()
        if not rows: return
        r = rows[0].row()
        asset_name  = self.asset_table.item(r, 0).text() if self.asset_table.item(r, 0) else ""
        assigned_to = self.asset_table.item(r, 1).text() if self.asset_table.item(r, 1) else ""
        for idx, entry in enumerate(asset_data):
            if entry['asset'] == asset_name and entry['assigned_to'] == assigned_to:
                self._editing_asset_index = idx
                self.asset_name_input.setText(entry['asset'])
                self.assigned_to_input.setText(entry['assigned_to'])
                self.asset_location_input.setText(entry['location'])
                self.asset_notes_input.setText(entry.get('notes', ''))
                si = self.asset_status_combo.findText(entry.get('status', 'Active'))
                if si >= 0: self.asset_status_combo.setCurrentIndex(si)
                self._asset_mode_label.setText(f"✏️  Editing:  {asset_name}")
                self.asset_status_badge.set_success(f"Loaded '{asset_name}' — modify and click Save.")
                break

    def _scan_asset_item(self):
        """Open scanner dialog; if scanned value matches an asset, load it into the form."""
        value = open_scanner_dialog(
            parent=self,
            prompt="Scan the asset's barcode or QR code to look it up."
        )
        if not value:
            return
        for idx, entry in enumerate(asset_data):
            if entry['asset'] == value or entry['asset'].lower() == value.lower():
                self._editing_asset_index = idx
                self.asset_name_input.setText(entry['asset'])
                self.assigned_to_input.setText(entry['assigned_to'])
                self.asset_location_input.setText(entry['location'])
                self.asset_notes_input.setText(entry.get('notes', ''))
                si = self.asset_status_combo.findText(entry.get('status', 'Active'))
                if si >= 0: self.asset_status_combo.setCurrentIndex(si)
                self._asset_mode_label.setText(f"✏️  Editing:  {entry['asset']}")
                self.asset_status_badge.set_success(f"Loaded '{entry['asset']}' from scan.")
                # Highlight row
                for r in range(self.asset_table.rowCount()):
                    item = self.asset_table.item(r, 0)
                    if item and item.text() == entry['asset']:
                        self.asset_table.selectRow(r)
                        self.asset_table.scrollToItem(item)
                        break
                return
        # Not found
        self.asset_name_input.setText(value)
        self._asset_mode_label.setText("➕  New Asset (from scan)")
        self.asset_status_badge.set_warning(f"'{value}' not found — fill in details and save to add it.")

    def _clear_asset_form(self):
        for w in [self.asset_name_input, self.assigned_to_input,
                  self.asset_location_input, self.asset_notes_input]:
            w.clear()
        self.asset_status_combo.setCurrentIndex(0)
        self.asset_table.clearSelection()
        self._editing_asset_index = None
        self._asset_mode_label.setText("➕  New Asset")
        self.asset_status_badge._neutral()
        self.asset_status_badge.setText("Fill in details to add a new asset.")

    def save_asset(self):
        asset_name  = self.asset_name_input.text().strip()
        assigned_to = self.assigned_to_input.text().strip()
        location    = self.asset_location_input.text().strip()
        notes       = self.asset_notes_input.text().strip()
        status      = self.asset_status_combo.currentText()
        if not asset_name:
            self.asset_status_badge.set_error("Asset name is required.")
            return
        entry = {'asset': asset_name, 'assigned_to': assigned_to,
                 'location': location, 'notes': notes, 'status': status,
                 'category': asset_name}
        if self._editing_asset_index is not None and self._editing_asset_index < len(asset_data):
            asset_data[self._editing_asset_index] = entry
            self.asset_status_badge.set_success(f"Updated '{asset_name}'")
        else:
            inventory_data.setdefault(asset_name, {
                'category': asset_name, 'quantity': 0, 'location': location,
                'usage_count': 0, 'price': 0.0, 'sku': '', 'sold_count': 0, 'sold_revenue': 0.0
            })
            asset_data.append(entry)
            self.asset_status_badge.set_success(f"Added '{asset_name}'")
        self.refresh_asset_table()
        self._clear_asset_form()

    def delete_asset(self):
        if self._editing_asset_index is None:
            self.asset_status_badge.set_error("Select an asset row to delete.")
            return
        idx = self._editing_asset_index
        if idx >= len(asset_data): return
        name = asset_data[idx]['asset']
        if self._confirm(f"Delete asset '{name}'?"):
            asset_data.pop(idx)
            self.asset_status_badge.set_success(f"Deleted '{name}'")
            self.refresh_asset_table()
            self._clear_asset_form()

    # ══════════════════════════════════════════════════════════════════════════
    # REPORTS TAB
    # ══════════════════════════════════════════════════════════════════════════
    def create_reports_tab(self):
        C = COLORS
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(SectionHeader("Inventory Reports"))

        ctrl = QHBoxLayout()
        lbl = QLabel("Chart Type:")
        lbl.setStyleSheet(f"color:{C['text_secondary']};background:transparent;")
        self.graph_type_combo = QComboBox()
        self.graph_type_combo.addItems(["Bar Chart", "Pie Chart", "Line Chart"])
        self.graph_type_combo.setFixedWidth(180)
        self.graph_type_combo.currentIndexChanged.connect(self.generate_report)
        btn_gen = QPushButton("Generate Report")
        btn_gen.setFixedWidth(160)
        btn_gen.clicked.connect(self.generate_report)
        ctrl.addWidget(lbl); ctrl.addWidget(self.graph_type_combo)
        ctrl.addSpacing(12); ctrl.addWidget(btn_gen); ctrl.addStretch()
        layout.addLayout(ctrl)

        content = QHBoxLayout(); content.setSpacing(14)
        self.report_display = QTextEdit()
        self.report_display.setReadOnly(True)
        self.report_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C['bg_input']}; color: {C['text_primary']};
                border: 1px solid {C['border']}; border-radius: 6px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt; padding: 10px;
            }}
        """)
        self.report_display.setMinimumWidth(280)

        plt.style.use('dark_background')
        fig = plt.Figure(figsize=(6, 4), facecolor=C['bg_card'])
        self.graph_canvas = FigureCanvas(fig)
        self.graph_canvas.setStyleSheet(f"background-color:{C['bg_card']};border-radius:8px;")

        content.addWidget(self.report_display, 2)
        content.addWidget(self.graph_canvas, 3)
        layout.addLayout(content)
        page.setLayout(layout)
        return page

    def generate_report(self):
        C = COLORS
        lines = ["INVENTORY REPORT\n" + "─" * 50]
        categories, oos, low_s, total_rev = {}, [], [], 0.0
        for item, d in inventory_data.items():
            qty = d['quantity']
            lines.append(
                f"  {item}\n    Cat:{d['category']}  Qty:{'OUT' if qty==0 else qty}  "
                f"Loc:{d['location']}\n    ${d.get('price',0):.2f}  Sold:{d.get('sold_count',0)}\n"
            )
            categories[d['category']] = categories.get(d['category'], 0) + qty
            if qty == 0: oos.append(item)
            elif qty <= LOW_STOCK_THRESHOLD: low_s.append(item)
            total_rev += d.get('sold_revenue', 0)

        lines.append("\nASSET ASSIGNMENTS\n" + "─" * 50)
        for a in asset_data:
            lines.append(f"  {a['asset']}  →  {a['assigned_to']}  @  {a['location']}  [{a.get('status','Active')}]")

        lines.append("\nRESTOCK ALERTS\n" + "─" * 50)
        lines.append("Out of Stock: " + (", ".join(oos) or "None"))
        lines.append("Low Stock:    " + (", ".join(low_s) or "None"))

        popular = sorted(inventory_data.items(), key=lambda x: x[1].get('usage_count', 0), reverse=True)[:5]
        lines.append("\nTOP 5 POPULAR ITEMS\n" + "─" * 50)
        for n, d in popular:
            lines.append(f"  {n}  ({d.get('usage_count',0)} uses)")
        lines.append(f"\nTOTAL SALES REVENUE:  ${total_rev:,.2f}")
        self.report_display.setText("\n".join(lines))

        self.graph_canvas.figure.clear()
        ax = self.graph_canvas.figure.add_subplot(111)
        ax.set_facecolor(C['bg_input'])
        for sp in ax.spines.values(): sp.set_color(C['border_light'])
        ax.tick_params(colors=C['text_secondary'], labelsize=8)
        ax.xaxis.label.set_color(C['text_secondary'])
        ax.yaxis.label.set_color(C['text_secondary'])
        ax.title.set_color(C['text_primary'])

        gt = self.graph_type_combo.currentText()
        if gt == "Bar Chart":
            if categories:
                bars = ax.bar(categories.keys(), categories.values(), color=C['accent'], width=0.55)
                ax.set_title("Inventory by Category", fontsize=11, fontweight='bold')
                ax.set_ylabel("Quantity"); ax.tick_params(axis='x', rotation=30)
                for bar in bars:
                    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.1,
                            str(int(bar.get_height())), ha='center', va='bottom',
                            color=C['text_primary'], fontsize=8)
            else:
                ax.text(0.5, 0.5, "No data", ha='center', va='center',
                        color=C['text_secondary'], transform=ax.transAxes)
        elif gt == "Pie Chart":
            if categories:
                pie_colors = [C['accent'], C['warning'], C['danger'],
                              '#7C83FD', '#A8EDEA', '#FED9B7', '#B8F7D4']
                wedges, texts, auto = ax.pie(
                    categories.values(), labels=categories.keys(),
                    autopct='%1.1f%%', startangle=140,
                    colors=pie_colors[:len(categories)],
                    wedgeprops={'linewidth':1,'edgecolor':C['bg_dark']}
                )
                for t in texts: t.set_color(C['text_primary'])
                for t in auto:  t.set_color(C['bg_dark'])
                ax.set_title("Distribution by Category", fontsize=11, fontweight='bold')
            else:
                ax.text(0.5, 0.5, "No data", ha='center', va='center',
                        color=C['text_secondary'], transform=ax.transAxes)
        elif gt == "Line Chart":
            sc = sorted(categories.items())
            if sc:
                cats, qtys = zip(*sc)
                ax.plot(cats, qtys, marker='o', linestyle='-', color=C['accent'],
                        linewidth=2, markersize=7, markerfacecolor=C['bg_card'],
                        markeredgecolor=C['accent'], markeredgewidth=2)
                ax.fill_between(range(len(cats)), qtys, alpha=0.1, color=C['accent'])
                ax.set_xticks(range(len(cats))); ax.set_xticklabels(cats, rotation=30, ha='right')
                ax.set_title("Quantity by Category", fontsize=11, fontweight='bold')
                ax.set_ylabel("Quantity")
                ax.grid(axis='y', color=C['border'], linestyle='--', alpha=0.4)
            else:
                ax.text(0.5, 0.5, "No data", ha='center', va='center',
                        color=C['text_secondary'], transform=ax.transAxes)

        self.graph_canvas.figure.tight_layout()
        self.graph_canvas.draw()


    # ── Step 2: Auto-save on close ───────────────────────────────────────────────
    def closeEvent(self, event):
        """Persist in-memory data to SQLite and save prefs before the window closes."""
        self._save_to_db()
        try:
            from core.prefs import save_prefs
            save_prefs()
        except Exception:
            pass
        event.accept()

    def _save_to_db(self):
        """Push the current in-memory inventory and asset data back to SQLite."""
        try:
            from core.inventory     import save_inventory_from_memory
            from core.asset_manager import save_assets_from_memory
            n_inv   = save_inventory_from_memory(inventory_data)
            n_asset = save_assets_from_memory(asset_data)
            import logging
            logging.getLogger(__name__).info(
                "Saved %d inventory items and %d assets to DB", n_inv, n_asset
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("DB save failed: %s", exc)

    # ── Step 9: Keyboard shortcuts ────────────────────────────────────────────
    def _setup_shortcuts(self):
        """Wire all keyboard shortcuts after init_ui() has run."""
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui     import QKeySequence

        shortcuts = [
            ("Ctrl+S",      self._shortcut_save),
            ("Ctrl+N",      self._shortcut_new_item),
            ("Ctrl+F",      self._shortcut_focus_search),
            ("Ctrl+P",      self._shortcut_generate_report),
            ("Ctrl+E",      self._shortcut_export),
            ("Ctrl+D",      self._shortcut_go_dashboard),
            ("Ctrl+1",      lambda: self.tabs.setCurrentIndex(0)),
            ("Ctrl+2",      lambda: self.tabs.setCurrentIndex(1)),
            ("Ctrl+3",      lambda: self.tabs.setCurrentIndex(2)),
            ("Ctrl+4",      lambda: self.tabs.setCurrentIndex(3)),
            ("Ctrl+,",      self.open_settings),
            ("F5",          self._shortcut_refresh),
        ]
        for seq, slot in shortcuts:
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(slot)

    def _shortcut_save(self):
        idx = self.tabs.currentIndex()
        if idx == 1:
            self.add_or_update_inventory()
        elif idx == 2:
            self.save_asset()
        else:
            self._save_to_db()
            self._status_flash("💾  Data saved to database.")

    def _shortcut_new_item(self):
        if self.tabs.currentIndex() == 1:
            self._clear_inv_form()
            self.item_name_input.setFocus()
        elif self.tabs.currentIndex() == 2:
            self._clear_asset_form()
            self.asset_name_input.setFocus()

    def _shortcut_focus_search(self):
        idx = self.tabs.currentIndex()
        if idx == 1 and hasattr(self, "inv_search"):
            self.inv_search.setFocus()
            self.inv_search.selectAll()
        elif idx == 2 and hasattr(self, "asset_search"):
            self.asset_search.setFocus()
            self.asset_search.selectAll()

    def _shortcut_generate_report(self):
        self.tabs.setCurrentIndex(3)
        if hasattr(self, "generate_report"):
            self.generate_report()

    def _shortcut_export(self):
        self.download_inventory_file()

    def _shortcut_go_dashboard(self):
        self.tabs.setCurrentIndex(0)

    def _shortcut_refresh(self):
        self.refresh_inventory_table()
        self.refresh_asset_table()
        self.update_dashboard_summary()
        self._status_flash("🔄  Refreshed.")

    def _status_flash(self, message: str):
        """Show a brief message in the window title, then restore it."""
        from PyQt5.QtCore import QTimer
        self.setWindowTitle(f"{APP_TITLE}  —  {message}")
        QTimer.singleShot(2500, lambda: self.setWindowTitle(APP_TITLE))


# ── Entry Point ───────────────────────────────────────────────────────────────
def run_app():
    import sys
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

    # Alejandro X. Solis - TechFusion Repairs LLC  03/10/2026
    