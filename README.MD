# InventraX

**InventraX** is a user-friendly, efficient, and scalable **Inventory & Asset Management** tool designed for IT teams, retailers, and office managers. It simplifies the tracking, assignment, and organization of stock, supplies, and equipment using a clean interface, barcode support, and insightful reporting features.

---

## 🚀 Features

- **Inventory Dashboard** with quick stats and low stock alerts
- **Item Management** (Add/Edit/Delete, Serial/Warranty tracking)
- **Asset Assignment** to people, departments, or locations
- **Barcode & QR Code Integration** (generate and scan)
- **Smart Stock Control** with reorder levels
- **Advanced Search & Filters**
- **Reports & Analytics** exportable to PDF, CSV, Excel
- **User Roles & Permissions** (Admin, Manager, Viewer)
- **Location Mapping** (building, room, shelf tracking)

---

## 🛠️ Technology Stack

- **Frontend:** Python + PyQt5 (desktop app UI)
- **Backend:** SQLite (PostgreSQL support in future)
- **Barcoding:** `python-barcode`, `pyzbar`, `qrcode`
- **Reporting:** `pandas`, `matplotlib`, `openpyxl`, `reportlab`
- **Packaging:** PyInstaller for Windows/macOS builds

---

## 📁 Project Structure

inventrax/
├── main.py # App entry point
├── config/
│ └── settings.py # Configuration variables
├── ui/
│ └── main_window.py # Main GUI window
│ └── item_editor.py # Item/Asset editor components
├── database/
│ └── db_init.py # Database setup and schema
│ └── models.py # Database interactions
├── core/
│ └── inventory.py # Inventory logic
│ └── asset_manager.py # Asset assignment logic
│ └── barcode_tools.py # QR/barcode generation
│ └── reporting.py # Export/report generation
├── assets/
│ └── icons/ # UI icons
│ └── templates/ # Report templates

yaml
Copy
Edit

---

## 📦 Setup Instructions

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/yourname/inventrax.git
   cd inventrax
Install Dependencies:

bash
Copy
Edit
pip install -r requirements.txt
Run the Application:

bash
Copy
Edit
python main.py
📌 Future Enhancements
Cloud sync and backup

Mobile app version

Maintenance tracking module

License & warranty manager

PostgreSQL upgrade

🎯 Target Users
IT departments managing hardware/software

Retailers with back-office inventory

Office supply and equipment tracking

Small warehouses and storerooms

📃 License
MIT License – free for personal and commercial use.

👨‍💻 Author
Alejandro X. Solis
Founder, TechFusion Repairs LLC

