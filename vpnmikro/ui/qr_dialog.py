"""QR code display dialog for WireGuard configurations.

This module provides a dialog for displaying QR codes that can be scanned
by the WireGuard mobile app to import configurations.

Requirements: 5.2, 5.3
"""

from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from vpnmikro.core.qr_generator import QRGenerator
from vpnmikro.ui.assets import get_window_icon, load_theme


class QRCodeDialog(QDialog):
    """Dialog for displaying WireGuard configuration QR codes.
    
    Shows a QR code that can be scanned by the WireGuard mobile app
    to import the configuration. Provides option to save the QR image.
    """
    
    def __init__(self, device_name: str, config_content: str, parent=None):
        """Initialize the QR code dialog.
        
        Args:
            device_name: Name of the device for the title.
            config_content: WireGuard configuration content.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._device_name = device_name
        self._config_content = config_content
        self._setup_ui()
        self._generate_qr()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle(f"QR Code - {self._device_name}")
        self.setMinimumSize(400, 450)
        self.setWindowIcon(get_window_icon())
        self.setStyleSheet(load_theme())
        
        layout = QVBoxLayout(self)
        
        # Instructions label
        instructions = QLabel(
            "Scan this QR code with the WireGuard mobile app to import the configuration."
        )
        instructions.setWordWrap(True)
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instructions)
        
        # QR code image label
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumSize(300, 300)
        layout.addWidget(self.qr_label)
        
        # Device name label
        name_label = QLabel(f"Device: {self._device_name}")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)
        
        # Button row
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save QR Image")
        self.save_button.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def _generate_qr(self):
        """Generate and display the QR code."""
        try:
            qr_bytes = QRGenerator.generate_qr_bytes(self._config_content)
            
            pixmap = QPixmap()
            pixmap.loadFromData(qr_bytes)
            
            # Scale to fit the label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                300, 300,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.qr_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            self.qr_label.setText(f"Error generating QR code:\n{e}")
            self.save_button.setEnabled(False)
    
    def _on_save(self):
        """Handle Save QR Image button click."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save QR Code",
            f"{self._device_name}-qr.png",
            "PNG Image (*.png);;JPEG Image (*.jpg)"
        )
        
        if file_path:
            try:
                output_path = Path(file_path)
                QRGenerator.save_qr_image(self._config_content, output_path)
                QMessageBox.information(
                    self, "Saved",
                    f"QR code saved to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Error",
                    f"Failed to save QR code:\n{e}"
                )
