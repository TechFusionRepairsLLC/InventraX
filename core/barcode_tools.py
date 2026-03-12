"""
barcode_tools.py  —  InventraX Barcode & QR Utilities
======================================================
Supports three scanning methods:

  1. USB / Bluetooth Keyboard-Wedge Scanner (works out of the box — no
     extra libraries needed).  Most handheld barcode scanners present as
     a USB HID keyboard and type the barcode string followed by Enter.
     The ScannerInputDialog listens for that Enter-terminated burst.

  2. Camera-based live scanner (requires opencv-python + pyzbar).
     Opens the default webcam, decodes barcodes/QR codes in real time,
     and returns the decoded string.  Gracefully unavailable if the
     libraries are not installed.

  3. Manual entry fallback — a plain text field the user can type into,
     so the workflow is never blocked.

Install optional dependencies for camera scanning:
    pip install opencv-python pyzbar
"""

import os
import time
import threading

# ── QR generation ────────────────────────────────────────────────────────────
try:
    import qrcode as _qrcode
    _QRCODE_AVAILABLE = True
except ImportError:
    _QRCODE_AVAILABLE = False

# ── Camera scanning (optional) ────────────────────────────────────────────────
try:
    import cv2 as _cv2
    from pyzbar import pyzbar as _pyzbar
    _CAMERA_AVAILABLE = True
except ImportError:
    _CAMERA_AVAILABLE = False

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QTabWidget, QWidget, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
from PyQt5.QtGui import QImage, QPixmap, QFont


# ─────────────────────────────────────────────────────────────────────────────
# QR / Barcode Generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_qr(data: str, output_path: str) -> bool:
    """
    Generate a QR code image and save it to output_path.
    Returns True on success, False if qrcode library is missing.
    """
    if not _QRCODE_AVAILABLE:
        return False
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    qr = _qrcode.QRCode(
        version=1,
        error_correction=_qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_path)
    return True


def generate_qr_pixmap(data: str, size: int = 200) -> "QPixmap | None":
    """
    Generate a QR code and return it as a QPixmap for inline display.
    Returns None if qrcode is not installed.
    """
    if not _QRCODE_AVAILABLE:
        return None
    import io
    from PIL import Image as _PilImage
    qr = _qrcode.QRCode(version=1,
                        error_correction=_qrcode.constants.ERROR_CORRECT_H,
                        box_size=8, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    pil_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    qt_img = QImage.fromData(buf.read())
    return QPixmap.fromImage(qt_img).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


# ─────────────────────────────────────────────────────────────────────────────
# Camera Worker Thread
# ─────────────────────────────────────────────────────────────────────────────

class _CameraWorker(QObject):
    """
    Runs in a background QThread.  Emits:
      frame_ready(QPixmap)   — live preview frame
      code_found(str)        — first decoded barcode/QR value
      error(str)             — camera open failure
    """
    frame_ready = pyqtSignal(QPixmap)
    code_found  = pyqtSignal(str)
    error       = pyqtSignal(str)

    def __init__(self, camera_index: int = 0):
        super().__init__()
        self._camera_index = camera_index
        self._running = False

    def start_capture(self):
        self._running = True
        cap = _cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            self.error.emit("Could not open camera. Check that it is connected and not in use.")
            return

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    break

                # Decode
                decoded = _pyzbar.decode(frame)
                for obj in decoded:
                    value = obj.data.decode("utf-8", errors="replace").strip()
                    if value:
                        # Draw bounding box on frame
                        pts = obj.polygon
                        if len(pts) == 4:
                            import numpy as np
                            pts_arr = np.array([(p.x, p.y) for p in pts], dtype=int)
                            _cv2.polylines(frame, [pts_arr], True, (0, 212, 170), 3)
                        _cv2.putText(frame, value, (obj.rect.left, obj.rect.top - 10),
                                     _cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 212, 170), 2)
                        self.stop()
                        # Convert and emit frame with overlay before stopping
                        self.frame_ready.emit(self._to_pixmap(frame))
                        self.code_found.emit(value)
                        cap.release()
                        return

                # Emit preview frame
                self.frame_ready.emit(self._to_pixmap(frame))

                time.sleep(0.03)   # ~30 fps cap
        finally:
            cap.release()

    def stop(self):
        self._running = False

    @staticmethod
    def _to_pixmap(frame) -> QPixmap:
        rgb = _cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qt_img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        return QPixmap.fromImage(qt_img).scaled(480, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation)


# ─────────────────────────────────────────────────────────────────────────────
# Main Scanner Dialog
# ─────────────────────────────────────────────────────────────────────────────

class ScannerDialog(QDialog):
    """
    A three-tab dialog for scanning/entering barcodes:
      Tab 1 — USB / Bluetooth wedge scanner input
      Tab 2 — Camera live scanner (if opencv + pyzbar are installed)
      Tab 3 — Manual text entry

    Usage:
        dlg = ScannerDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            barcode_value = dlg.result()
    """

    def __init__(self, parent=None, prompt: str = "Scan or enter a barcode / QR code"):
        super().__init__(parent)
        self.setWindowTitle("Barcode / QR Scanner")
        self.setMinimumWidth(540)
        self.setMinimumHeight(480)
        self._result = ""
        self._camera_thread = None
        self._camera_worker = None
        self._wedge_buffer  = ""
        self._wedge_timer   = QTimer(self)
        self._wedge_timer.setSingleShot(True)
        self._wedge_timer.timeout.connect(self._wedge_timeout)
        self._build_ui(prompt)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self, prompt: str):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel(prompt)
        title.setWordWrap(True)
        title.setStyleSheet("font-size:11pt; font-weight:700; padding-bottom:4px;")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_wedge_tab(),  "  📡  USB Scanner  ")
        self.tabs.addTab(self._build_camera_tab(), "  📷  Camera  ")
        self.tabs.addTab(self._build_manual_tab(), "  ⌨️  Manual Entry  ")
        self.tabs.currentChanged.connect(self._on_tab_change)
        layout.addWidget(self.tabs)

        # Result preview row
        result_row = QHBoxLayout()
        self._result_label = QLabel("No scan yet.")
        self._result_label.setStyleSheet(
            "font-size:10pt; font-weight:600; padding:6px 10px;"
            "border:1px solid #2D3454; border-radius:6px;"
        )
        self._result_label.setWordWrap(True)
        result_row.addWidget(QLabel("Scanned:"))
        result_row.addWidget(self._result_label, 1)
        layout.addLayout(result_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("neutral_btn")
        self._cancel_btn.setFixedWidth(100)
        self._cancel_btn.clicked.connect(self.reject)

        self._accept_btn = QPushButton("Use This Code")
        self._accept_btn.setFixedWidth(150)
        self._accept_btn.setEnabled(False)
        self._accept_btn.clicked.connect(self._on_accept)

        btn_row.addWidget(self._cancel_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(self._accept_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    # ── Tab 1: USB Wedge ──────────────────────────────────────────────────────
    def _build_wedge_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info = QLabel(
            "Point your USB or Bluetooth scanner at the barcode and pull the trigger.\n\n"
            "Most scanners act as a keyboard — they type the code and press Enter automatically. "
            "The field below will capture the input even if it's not focused."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size:9pt; color:#8892B0;")
        layout.addWidget(info)

        indicator_frame = QFrame()
        indicator_frame.setStyleSheet(
            "QFrame { background-color: #1E2333; border: 2px dashed #2D3454; border-radius: 10px; }"
        )
        ind_layout = QVBoxLayout()
        ind_layout.setContentsMargins(20, 20, 20, 20)

        self._wedge_icon = QLabel("📡")
        self._wedge_icon.setAlignment(Qt.AlignCenter)
        self._wedge_icon.setStyleSheet("font-size: 36pt; background: transparent; border: none;")

        self._wedge_status = QLabel("Waiting for scanner input…")
        self._wedge_status.setAlignment(Qt.AlignCenter)
        self._wedge_status.setStyleSheet(
            "font-size:10pt; font-weight:600; color:#8892B0; background:transparent; border:none;")

        self._wedge_input = QLineEdit()
        self._wedge_input.setPlaceholderText("Scanner input appears here…")
        self._wedge_input.setReadOnly(False)
        self._wedge_input.returnPressed.connect(self._on_wedge_return)
        self._wedge_input.textChanged.connect(self._on_wedge_text_changed)

        ind_layout.addWidget(self._wedge_icon)
        ind_layout.addWidget(self._wedge_status)
        ind_layout.addSpacing(10)
        ind_layout.addWidget(self._wedge_input)
        indicator_frame.setLayout(ind_layout)
        layout.addWidget(indicator_frame)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("neutral_btn")
        clear_btn.setFixedWidth(80)
        clear_btn.clicked.connect(lambda: (self._wedge_input.clear(), self._set_result("")))
        layout.addWidget(clear_btn, alignment=Qt.AlignRight)
        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def _on_wedge_text_changed(self):
        # Reset the inactivity timer — if no new chars for 200ms after typing, treat as complete
        self._wedge_timer.start(200)

    def _wedge_timeout(self):
        text = self._wedge_input.text().strip()
        if text:
            self._on_wedge_complete(text)

    def _on_wedge_return(self):
        self._wedge_timer.stop()
        text = self._wedge_input.text().strip()
        if text:
            self._on_wedge_complete(text)

    def _on_wedge_complete(self, value: str):
        self._wedge_icon.setText("✅")
        self._wedge_status.setText(f"Detected: {value}")
        self._wedge_status.setStyleSheet(
            "font-size:10pt; font-weight:600; color:#00D4AA; background:transparent; border:none;")
        self._set_result(value)

    # ── Tab 2: Camera ──────────────────────────────────────────────────────────
    def _build_camera_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        if not _CAMERA_AVAILABLE:
            unavail = QLabel(
                "📷  Camera scanning is not available.\n\n"
                "Install the required libraries to enable it:\n\n"
                "    pip install opencv-python pyzbar\n\n"
                "After installing, restart InventraX."
            )
            unavail.setWordWrap(True)
            unavail.setStyleSheet(
                "font-size:10pt; color:#8892B0; padding:20px;"
                "border:2px dashed #2D3454; border-radius:10px;")
            layout.addWidget(unavail)
            layout.addStretch()
            tab.setLayout(layout)
            return tab

        self._camera_preview = QLabel()
        self._camera_preview.setAlignment(Qt.AlignCenter)
        self._camera_preview.setMinimumHeight(300)
        self._camera_preview.setStyleSheet(
            "background:#0F1117; border:1px solid #2D3454; border-radius:8px;")
        self._camera_preview.setText("Camera preview will appear here.")
        layout.addWidget(self._camera_preview)

        self._cam_status = QLabel("Press 'Start Camera' to begin scanning.")
        self._cam_status.setAlignment(Qt.AlignCenter)
        self._cam_status.setStyleSheet("font-size:9pt; color:#8892B0;")
        layout.addWidget(self._cam_status)

        btn_row = QHBoxLayout()
        self._start_cam_btn = QPushButton("▶  Start Camera")
        self._start_cam_btn.clicked.connect(self._start_camera)
        self._stop_cam_btn  = QPushButton("■  Stop Camera")
        self._stop_cam_btn.setObjectName("danger_btn")
        self._stop_cam_btn.clicked.connect(self._stop_camera)
        self._stop_cam_btn.setEnabled(False)
        btn_row.addWidget(self._start_cam_btn)
        btn_row.addWidget(self._stop_cam_btn)
        layout.addLayout(btn_row)

        tab.setLayout(layout)
        return tab

    def _start_camera(self):
        if not _CAMERA_AVAILABLE:
            return
        self._start_cam_btn.setEnabled(False)
        self._stop_cam_btn.setEnabled(True)
        self._cam_status.setText("Scanning… point camera at barcode or QR code.")

        self._camera_worker = _CameraWorker(camera_index=0)
        self._camera_thread = QThread()
        self._camera_worker.moveToThread(self._camera_thread)

        self._camera_thread.started.connect(self._camera_worker.start_capture)
        self._camera_worker.frame_ready.connect(self._on_camera_frame)
        self._camera_worker.code_found.connect(self._on_camera_code)
        self._camera_worker.error.connect(self._on_camera_error)

        self._camera_thread.start()

    def _stop_camera(self):
        if self._camera_worker:
            self._camera_worker.stop()
        if self._camera_thread:
            self._camera_thread.quit()
            self._camera_thread.wait()
        self._start_cam_btn.setEnabled(True)
        self._stop_cam_btn.setEnabled(False)
        self._cam_status.setText("Camera stopped.")

    def _on_camera_frame(self, pixmap: QPixmap):
        if hasattr(self, '_camera_preview'):
            self._camera_preview.setPixmap(pixmap)

    def _on_camera_code(self, value: str):
        self._stop_camera()
        self._cam_status.setText(f"✅  Scanned: {value}")
        self._cam_status.setStyleSheet("font-size:9pt; color:#00D4AA; font-weight:700;")
        self._set_result(value)

    def _on_camera_error(self, msg: str):
        self._stop_camera()
        self._cam_status.setText(f"⚠️  {msg}")
        self._cam_status.setStyleSheet("font-size:9pt; color:#FF4757;")

    # ── Tab 3: Manual Entry ────────────────────────────────────────────────────
    def _build_manual_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info = QLabel("Type or paste a barcode value, SKU, or item name manually.")
        info.setWordWrap(True)
        info.setStyleSheet("font-size:9pt; color:#8892B0;")
        layout.addWidget(info)

        self._manual_input = QLineEdit()
        self._manual_input.setPlaceholderText("e.g.  SKU-00042  or  USB-C-HUB-3PORT")
        self._manual_input.setMinimumHeight(38)
        self._manual_input.returnPressed.connect(self._on_manual_confirm)
        layout.addWidget(self._manual_input)

        confirm_btn = QPushButton("Confirm")
        confirm_btn.setFixedWidth(120)
        confirm_btn.clicked.connect(self._on_manual_confirm)
        layout.addWidget(confirm_btn, alignment=Qt.AlignLeft)
        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def _on_manual_confirm(self):
        value = self._manual_input.text().strip()
        if value:
            self._set_result(value)
        else:
            self._result_label.setText("Please enter a value first.")

    # ── Shared helpers ────────────────────────────────────────────────────────
    def _set_result(self, value: str):
        self._result = value
        if value:
            self._result_label.setText(value)
            self._result_label.setStyleSheet(
                "font-size:10pt; font-weight:700; color:#00D4AA;"
                "padding:6px 10px; border:1px solid #00897B; border-radius:6px;")
            self._accept_btn.setEnabled(True)
        else:
            self._result_label.setText("No scan yet.")
            self._result_label.setStyleSheet(
                "font-size:10pt; padding:6px 10px;"
                "border:1px solid #2D3454; border-radius:6px;")
            self._accept_btn.setEnabled(False)

    def _on_tab_change(self, index: int):
        # Stop camera if switching away from camera tab
        if index != 1 and self._camera_worker and self._camera_worker._running:
            self._stop_camera()
        # Focus the appropriate input
        if index == 0:
            self._wedge_input.setFocus()
        elif index == 2:
            self._manual_input.setFocus()

    def _on_accept(self):
        if self._result:
            self.accept()

    def result(self) -> str:
        return self._result

    def closeEvent(self, event):
        if self._camera_worker:
            self._camera_worker.stop()
        if self._camera_thread:
            self._camera_thread.quit()
            self._camera_thread.wait()
        super().closeEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience helper used by MainWindow
# ─────────────────────────────────────────────────────────────────────────────

def open_scanner_dialog(parent=None, prompt: str = "Scan a barcode or QR code") -> str:
    """
    Open the ScannerDialog and return the scanned/entered value, or "" if cancelled.
    """
    dlg = ScannerDialog(parent=parent, prompt=prompt)
    if dlg.exec_() == QDialog.Accepted:
        return dlg.result()
    return ""