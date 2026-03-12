"""
ui/item_editor.py  —  InventraX Item Detail / Edit Dialog
===========================================================
A full-screen popup dialog that opens when the user double-clicks any
row in the Inventory table.  Shows ALL fields — including serial number,
warranty date, and notes that don't fit in the side panel — and lets
the user edit and save directly.

Also used as an "Add New Item" dialog when launched from the menu or
keyboard shortcut Ctrl+Shift+N.

Usage (from main_window.py)
---------------------------
    from ui.item_editor import ItemEditorDialog

    # Open for editing an existing item:
    dlg = ItemEditorDialog(parent=self, item_name="USB-C Hub",
                           item_data=inventory_data["USB-C Hub"])
    if dlg.exec_() == QDialog.Accepted:
        inventory_data[dlg.result_name()] = dlg.result_data()
        self.refresh_inventory_table()
        self.update_dashboard_summary()

    # Open as a blank "Add New" form:
    dlg = ItemEditorDialog(parent=self)
    if dlg.exec_() == QDialog.Accepted:
        ...
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QPushButton, QTextEdit, QGroupBox, QFrame,
    QDialogButtonBox, QMessageBox, QDateEdit, QSizePolicy
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui  import QFont


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _label(text: str, secondary: bool = False) -> QLabel:
    lbl = QLabel(text)
    if secondary:
        lbl.setStyleSheet("color:#8892B0; font-size:8pt; background:transparent;")
    return lbl


def _section(title: str) -> QGroupBox:
    gb = QGroupBox(title)
    gb.setStyleSheet("""
        QGroupBox {
            font-weight: 700;
            font-size: 10pt;
            color: #E8EAF6;
            border: 1px solid #2D3454;
            border-radius: 8px;
            margin-top: 10px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
            color: #00D4AA;
        }
    """)
    return gb


# ─────────────────────────────────────────────────────────────────────────────
# Dialog
# ─────────────────────────────────────────────────────────────────────────────

class ItemEditorDialog(QDialog):
    """
    Full-field editor for a single inventory item.

    Parameters
    ----------
    parent      : parent QWidget
    item_name   : existing item name to edit, or "" / None for a new item
    item_data   : dict of item fields (from inventory_data[name])
    read_only   : if True, all fields are disabled (view-only mode)
    """

    def __init__(self, parent=None,
                 item_name: str = "",
                 item_data: dict = None,
                 read_only: bool = False):
        super().__init__(parent)

        self._original_name = item_name or ""
        self._data          = dict(item_data) if item_data else {}
        self._read_only     = read_only
        self._is_new        = not bool(item_name)

        title = "View Item" if read_only else (
            f"✏️  Edit Item — {item_name}" if item_name else "➕  Add New Item"
        )
        self.setWindowTitle(title)
        self.setMinimumWidth(580)
        self.setMinimumHeight(620)
        self.setSizeGripEnabled(True)

        self._build_ui()
        self._populate(item_name, self._data)

        if read_only:
            self._set_all_readonly()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout()
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # ── Mode label ─────────────────────────────────────────────────────
        self._mode_label = QLabel(
            "Add all item details below." if self._is_new else
            "Edit the fields you want to change, then click Save."
        )
        self._mode_label.setStyleSheet("color:#8892B0; font-size:9pt;")
        self._mode_label.setWordWrap(True)
        outer.addWidget(self._mode_label)

        # ── Section 1: Core fields ──────────────────────────────────────────
        core_box  = _section("Core Details")
        core_form = QFormLayout()
        core_form.setSpacing(10)
        core_form.setLabelAlignment(Qt.AlignRight)

        self.f_name     = QLineEdit(); self.f_name.setPlaceholderText("e.g. USB-C Hub 3-Port")
        self.f_category = QLineEdit(); self.f_category.setPlaceholderText("e.g. Electronics")
        self.f_sku      = QLineEdit(); self.f_sku.setPlaceholderText("e.g. SKU-00042")
        self.f_serial   = QLineEdit(); self.f_serial.setPlaceholderText("e.g. SN-2024-00198")
        self.f_location = QLineEdit(); self.f_location.setPlaceholderText("e.g. Shelf A-3 / Bin 7")

        core_form.addRow("Item Name *", self.f_name)
        core_form.addRow("Category",    self.f_category)
        core_form.addRow("SKU",         self.f_sku)
        core_form.addRow("Serial No.",  self.f_serial)
        core_form.addRow("Location",    self.f_location)
        core_box.setLayout(core_form)
        outer.addWidget(core_box)

        # ── Section 2: Stock & Pricing ──────────────────────────────────────
        stock_box  = _section("Stock & Pricing")
        stock_form = QFormLayout()
        stock_form.setSpacing(10)
        stock_form.setLabelAlignment(Qt.AlignRight)

        self.f_quantity = QSpinBox()
        self.f_quantity.setRange(0, 99_999)
        self.f_quantity.setMinimumWidth(100)

        self.f_price = QDoubleSpinBox()
        self.f_price.setRange(0.0, 9_999_999.99)
        self.f_price.setDecimals(2)
        self.f_price.setPrefix("$  ")
        self.f_price.setMinimumWidth(140)

        self.f_sold_count = QSpinBox()
        self.f_sold_count.setRange(0, 99_999)
        self.f_sold_count.setMinimumWidth(100)

        self.f_sold_revenue = QDoubleSpinBox()
        self.f_sold_revenue.setRange(0.0, 9_999_999.99)
        self.f_sold_revenue.setDecimals(2)
        self.f_sold_revenue.setPrefix("$  ")
        self.f_sold_revenue.setMinimumWidth(140)

        self.f_usage_count = QSpinBox()
        self.f_usage_count.setRange(0, 99_999)
        self.f_usage_count.setMinimumWidth(100)

        # Inline quantity + price row
        qty_row = QHBoxLayout()
        qty_row.addWidget(self.f_quantity)
        qty_row.addSpacing(20)
        qty_row.addWidget(_label("Unit Price:"))
        qty_row.addWidget(self.f_price)
        qty_row.addStretch()

        sold_row = QHBoxLayout()
        sold_row.addWidget(self.f_sold_count)
        sold_row.addSpacing(20)
        sold_row.addWidget(_label("Revenue:"))
        sold_row.addWidget(self.f_sold_revenue)
        sold_row.addStretch()

        stock_form.addRow("Quantity on Hand", qty_row)
        stock_form.addRow("Units Sold",       sold_row)
        stock_form.addRow("Usage Count",      self.f_usage_count)
        stock_box.setLayout(stock_form)
        outer.addWidget(stock_box)

        # ── Section 3: Dates & Notes ────────────────────────────────────────
        extra_box  = _section("Dates & Notes")
        extra_form = QFormLayout()
        extra_form.setSpacing(10)
        extra_form.setLabelAlignment(Qt.AlignRight)

        self.f_warranty = QDateEdit()
        self.f_warranty.setCalendarPopup(True)
        self.f_warranty.setDate(QDate.currentDate())
        self.f_warranty.setDisplayFormat("yyyy-MM-dd")
        self.f_warranty.setMinimumWidth(140)

        self.f_notes = QTextEdit()
        self.f_notes.setPlaceholderText("Any additional notes about this item…")
        self.f_notes.setFixedHeight(70)

        extra_form.addRow("Warranty Expiry", self.f_warranty)
        extra_form.addRow("Notes",           self.f_notes)
        extra_box.setLayout(extra_form)
        outer.addWidget(extra_box)

        # ── Validation message ──────────────────────────────────────────────
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(
            "color:#FF4757; font-size:9pt; padding:4px 0;"
        )
        self._error_label.setWordWrap(True)
        outer.addWidget(self._error_label)

        # ── Buttons ─────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        if not self._read_only:
            self._save_btn = QPushButton("💾  Save Item")
            self._save_btn.setMinimumWidth(130)
            self._save_btn.setMinimumHeight(36)
            self._save_btn.clicked.connect(self._on_save)
            btn_row.addWidget(self._save_btn)

        cancel_btn = QPushButton("Cancel" if not self._read_only else "Close")
        cancel_btn.setObjectName("neutral_btn")
        cancel_btn.setMinimumWidth(90)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        outer.addLayout(btn_row)
        self.setLayout(outer)

    # ── Populate ──────────────────────────────────────────────────────────────

    def _populate(self, name: str, d: dict):
        self.f_name.setText(name or "")
        self.f_category.setText(d.get("category",     ""))
        self.f_sku.setText(d.get("sku",               ""))
        self.f_serial.setText(d.get("serial",         ""))
        self.f_location.setText(d.get("location",     ""))
        self.f_quantity.setValue(int(d.get("quantity", 0)))
        self.f_usage_count.setValue(int(d.get("usage_count", 0)))
        self.f_sold_count.setValue(int(d.get("sold_count",   0)))

        try:   self.f_price.setValue(float(d.get("price", 0.0)))
        except (TypeError, ValueError): self.f_price.setValue(0.0)

        try:   self.f_sold_revenue.setValue(float(d.get("sold_revenue", 0.0)))
        except (TypeError, ValueError): self.f_sold_revenue.setValue(0.0)

        # Warranty date
        w_str = d.get("warranty_date", "")
        if w_str:
            qd = QDate.fromString(w_str, "yyyy-MM-dd")
            if qd.isValid():
                self.f_warranty.setDate(qd)

        self.f_notes.setPlainText(d.get("notes", ""))

    def _set_all_readonly(self):
        for widget in [self.f_name, self.f_category, self.f_sku,
                       self.f_serial, self.f_location, self.f_notes]:
            widget.setReadOnly(True)
        for widget in [self.f_quantity, self.f_price, self.f_sold_count,
                       self.f_sold_revenue, self.f_usage_count]:
            widget.setReadOnly(True)
        self.f_warranty.setReadOnly(True)

    # ── Save / Validate ───────────────────────────────────────────────────────

    def _on_save(self):
        name = self.f_name.text().strip()
        if not name:
            self._error_label.setText("⚠  Item Name is required.")
            self.f_name.setFocus()
            return
        self._error_label.setText("")
        self.accept()

    # ── Result accessors (read after exec_() == Accepted) ────────────────────

    def result_name(self) -> str:
        """The (potentially renamed) item name."""
        return self.f_name.text().strip()

    def result_data(self) -> dict:
        """Return the edited fields as a dict matching inventory_data structure."""
        return {
            "category":     self.f_category.text().strip(),
            "quantity":     self.f_quantity.value(),
            "location":     self.f_location.text().strip(),
            "price":        round(self.f_price.value(), 2),
            "sku":          self.f_sku.text().strip(),
            "serial":       self.f_serial.text().strip(),
            "warranty_date":self.f_warranty.date().toString("yyyy-MM-dd"),
            "usage_count":  self.f_usage_count.value(),
            "sold_count":   self.f_sold_count.value(),
            "sold_revenue": round(self.f_sold_revenue.value(), 2),
            "notes":        self.f_notes.toPlainText().strip(),
        }

    def was_renamed(self) -> bool:
        """True if the user changed the item name."""
        return self.result_name() != self._original_name
