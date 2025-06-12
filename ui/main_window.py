from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QAction, QMessageBox, QLabel, QVBoxLayout,
    QWidget, QTabWidget, QLineEdit, QFormLayout, QSpinBox, QPushButton,
    QHBoxLayout, QTextEdit, QFileDialog
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from config.settings import APP_TITLE
import webbrowser
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import pandas as pd

# In-memory data stores
inventory_data = {}
asset_data = []

def open_url(url):
    webbrowser.open(url)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1000, 700)
        self.init_ui()

    def init_ui(self):
        menubar = self.menuBar()
        support_menu = menubar.addMenu("Support")

        contact_action = QAction("Contact Us", self)
        contact_action.triggered.connect(self.show_contact_dialog)

        website_action = QAction("Visit Website", self)
        website_action.triggered.connect(lambda: open_url("https://alejandroxsolis93.wixsite.com/techfusionrepairsllc"))

        donate_action = QAction("Donate", self)
        donate_action.triggered.connect(lambda: open_url("https://www.paypal.com/donate/?hosted_button_id=CESA5GQALY386"))

        github_action = QAction("GitHub", self)
        github_action.triggered.connect(lambda: open_url("https://github.com/TechFusionRepairsLLC"))

        support_menu.addAction(contact_action)
        support_menu.addAction(website_action)
        support_menu.addAction(donate_action)
        support_menu.addAction(github_action)

        file_menu = menubar.addMenu("File")
        upload_action = QAction("Upload Inventory File", self)
        upload_action.triggered.connect(self.upload_inventory_file)
        download_action = QAction("Download Inventory File", self)
        download_action.triggered.connect(self.download_inventory_file)
        file_menu.addAction(upload_action)
        file_menu.addAction(download_action)

        # Create the tabs
        tabs = QTabWidget()
        tabs.addTab(self.create_dashboard_tab(), "Dashboard")
        tabs.addTab(self.create_inventory_tab(), "Inventory")
        tabs.addTab(self.create_assets_tab(), "Asset Management")
        tabs.addTab(self.create_reports_tab(), "Reports")

        # Create main widget container with vertical layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addWidget(tabs)

        # Add the footer widget below tabs
        footer = self.create_footer_widget()
        main_layout.addWidget(footer)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def create_footer_widget(self):
        footer_widget = QWidget()
        footer_layout = QHBoxLayout()

        # Load the TechFusion.png logo
        logo_label = QLabel()
        pixmap = QPixmap("assets/icons/TechFusion.png")
        if not pixmap.isNull():
            logo_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_label.setText("[Logo Missing]")

        footer_layout.addWidget(logo_label)

        # Footer text label
        footer_text = QLabel("Created by Alejandro X. Solis Founder of TechFusion Repairs LLC")
        footer_text.setStyleSheet("color: gray; font-size: 10pt;")
        footer_layout.addWidget(footer_text)

        # Push footer text and logo to left, and stretch to fill the rest
        footer_layout.addStretch()

        footer_widget.setLayout(footer_layout)

        # Optional: set a subtle top border line for the footer
        footer_widget.setStyleSheet("border-top: 1px solid #cccccc; padding: 5px;")

        return footer_widget

    def show_contact_dialog(self):
        msg = QMessageBox()
        msg.setWindowTitle("Contact Support")
        msg.setText(
            "📧 Email: TechFusionRepairs@gmail.com\n\n"
            "🌐 Website: https://alejandroxsolis93.wixsite.com/techfusionrepairsllc\n\n"
            "💸 Donate: https://www.paypal.com/donate/?hosted_button_id=CESA5GQALY386\n\n"
            "🔗 GitHub: https://github.com/TechFusionRepairsLLC"
        )
        msg.setIconPixmap(QPixmap("assets/icons/TechFusion.png").scaled(100, 100, Qt.KeepAspectRatio))
        msg.exec_()

    def upload_inventory_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Inventory File", "", "Excel Files (*.xlsx *.xls)")
        if file_name:
            df = pd.read_excel(file_name)
            for _, row in df.iterrows():
                name = str(row['Item Name']).strip()
                inventory_data[name] = {
                    'category': str(row['Category']),
                    'quantity': int(row['Quantity']),
                    'location': str(row['Location'])
                }
            QMessageBox.information(self, "Upload Successful", f"Loaded {len(df)} items into inventory.")

    def download_inventory_file(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Inventory File", "inventory.xlsx", "Excel Files (*.xlsx)")
        if file_name:
            df = pd.DataFrame([
                {
                    'Item Name': name,
                    'Category': details['category'],
                    'Quantity': details['quantity'],
                    'Location': details['location']
                } for name, details in inventory_data.items()
            ])
            df.to_excel(file_name, index=False)
            QMessageBox.information(self, "Download Successful", "Inventory exported successfully.")

    def create_dashboard_tab(self):
        layout = QVBoxLayout()

        logo = QLabel()
        pixmap = QPixmap("assets/icons/inventrax_logo.png")
        logo.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        how_to_use = QLabel("""
<h2>Welcome to InventraX</h2>
<p><b>InventraX</b> is your all-in-one solution for inventory and asset management.</p>
<ul>
<li>Add and manage inventory with item names, categories, and quantities.</li>
<li>Assign assets to users or departments for tracking.</li>
<li>Generate useful reports for audits and planning.</li>
<li>Scan barcodes or enter item names to auto-update quantities.</li>
</ul>
<p>Use the tabs above to navigate between Dashboard, Inventory, Asset Management, and Reports.</p>
""")
        how_to_use.setWordWrap(True)
        how_to_use.setAlignment(Qt.AlignTop)
        layout.addWidget(how_to_use)

        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def create_inventory_tab(self):
        layout = QVBoxLayout()

        form_layout = QFormLayout()
        self.item_name_input = QLineEdit()
        self.category_input = QLineEdit()
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(1, 10000)
        self.location_input = QLineEdit()

        form_layout.addRow("Item Name:", self.item_name_input)
        form_layout.addRow("Category:", self.category_input)
        form_layout.addRow("Quantity:", self.quantity_input)
        form_layout.addRow("Location:", self.location_input)

        add_button = QPushButton("Add / Update Item")
        add_button.clicked.connect(self.add_or_update_inventory)
        remove_button = QPushButton("Remove Item")
        remove_button.clicked.connect(self.remove_inventory_item)

        form_layout.addWidget(add_button)
        form_layout.addWidget(remove_button)

        self.inventory_status = QLabel()
        layout.addLayout(form_layout)
        layout.addWidget(self.inventory_status)

        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def add_or_update_inventory(self):
        name = self.item_name_input.text().strip()
        category = self.category_input.text().strip()
        quantity = self.quantity_input.value()
        location = self.location_input.text().strip()

        if name:
            if name in inventory_data:
                inventory_data[name]['quantity'] += quantity
                self.inventory_status.setText(f"Updated '{name}': New Quantity = {inventory_data[name]['quantity']}")
            else:
                inventory_data[name] = {
                    'category': category,
                    'quantity': quantity,
                    'location': location
                }
                self.inventory_status.setText(f"Added new item: {name}")
        else:
            self.inventory_status.setText("Please enter an item name.")

        self.item_name_input.clear()
        self.category_input.clear()
        self.quantity_input.setValue(1)
        self.location_input.clear()

    def remove_inventory_item(self):
        name = self.item_name_input.text().strip()
        if name in inventory_data:
            del inventory_data[name]
            self.inventory_status.setText(f"Removed item: {name}")
        else:
            self.inventory_status.setText("Item not found.")

        self.item_name_input.clear()

    def create_assets_tab(self):
        layout = QVBoxLayout()

        form_layout = QFormLayout()
        self.asset_name_input = QLineEdit()
        self.assigned_to_input = QLineEdit()
        self.asset_location_input = QLineEdit()

        form_layout.addRow("Asset Name:", self.asset_name_input)
        form_layout.addRow("Assigned To:", self.assigned_to_input)
        form_layout.addRow("Location:", self.asset_location_input)

        assign_button = QPushButton("Assign Asset")
        assign_button.clicked.connect(self.assign_asset)
        form_layout.addWidget(assign_button)

        self.asset_status = QLabel()
        layout.addLayout(form_layout)
        layout.addWidget(self.asset_status)

        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def assign_asset(self):
        asset_name = self.asset_name_input.text().strip()
        assigned_to = self.assigned_to_input.text().strip()
        location = self.asset_location_input.text().strip()

        if asset_name:
            asset_data.append({
                'asset': asset_name,
                'assigned_to': assigned_to,
                'location': location
            })
            self.asset_status.setText(f"Asset '{asset_name}' assigned to {assigned_to} at {location}.")
            self.asset_name_input.clear()
            self.assigned_to_input.clear()
            self.asset_location_input.clear()
        else:
            self.asset_status.setText("Please enter an asset name.")

    def create_reports_tab(self):
        layout = QVBoxLayout()

        self.report_display = QTextEdit()
        self.report_display.setReadOnly(True)
        generate_button = QPushButton("Generate Inventory Report")
        generate_button.clicked.connect(self.generate_report)

        self.graph_canvas = FigureCanvas(plt.Figure(figsize=(5, 3)))

        layout.addWidget(generate_button)
        layout.addWidget(self.report_display)
        layout.addWidget(self.graph_canvas)

        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def generate_report(self):
        report_lines = ["Inventory Report:\n"]
        categories = {}
        for item, details in inventory_data.items():
            report_lines.append(f"Item: {item}, Category: {details['category']}, Quantity: {details['quantity']}, Location: {details['location']}")
            cat = details['category']
            categories[cat] = categories.get(cat, 0) + details['quantity']

        report_lines.append("\nAsset Assignments:\n")
        for asset in asset_data:
            report_lines.append(f"Asset: {asset['asset']}, Assigned To: {asset['assigned_to']}, Location: {asset['location']}")

        self.report_display.setText("\n".join(report_lines))

        self.graph_canvas.figure.clear()
        ax = self.graph_canvas.figure.add_subplot(111)
        ax.bar(categories.keys(), categories.values(), color='skyblue')
        ax.set_title("Inventory by Category")
        ax.set_ylabel("Quantity")
        ax.set_xlabel("Category")
        ax.tick_params(axis='x', rotation=45)
        self.graph_canvas.draw()

def run_app():
    import sys
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
