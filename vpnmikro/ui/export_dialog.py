"""Export dialog for WireGuard configurations.

This module provides a dialog for exporting WireGuard configurations
with options to save, copy to clipboard, or open the containing folder.

Requirements: 5.1
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QMessageBox, QTextEdit,
    QApplication, QGroupBox
)
from PyQt6.QtCore import Qt

from vpnmikro.ui.assets import get_window_icon, load_theme


class ExportDialog(QDialog):
    """Dialog for exporting WireGuard configuration files.
    
    Provides options to:
    - Save configuration to a user-selected location
    - Copy configuration content to clipboard
    - Open the folder containing the configuration file
    """
    
    def __init__(self, device_name: str, config_path: str, parent=None):
        """Initialize the export dialog.
        
        Args:
            device_name: Name of the device.
            config_path: Path to the configuration file.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._device_name = device_name
        self._config_path = Path(config_path)
        self._config_content: Optional[str] = None
        self._setup_ui()
        self._load_config()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle(f"Export Configuration - {self._device_name}")
        self.setMinimumSize(500, 400)
        self.setWindowIcon(get_window_icon())
        self.setStyleSheet(load_theme())
        
        layout = QVBoxLayout(self)
        
        # Info section
        info_group = QGroupBox("Configuration Info")
        info_layout = QVBoxLayout(info_group)
        
        self.path_label = QLabel(f"File: {self._config_path}")
        self.path_label.setWordWrap(True)
        info_layout.addWidget(self.path_label)
        
        layout.addWidget(info_group)
        
        # Preview section
        preview_group = QGroupBox("Configuration Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(self._get_monospace_font())
        preview_layout.addWidget(self.preview_text)
        
        layout.addWidget(preview_group)
        
        # Action buttons
        actions_layout = QHBoxLayout()
        
        self.save_as_button = QPushButton("Save As...")
        self.save_as_button.clicked.connect(self._on_save_as)
        actions_layout.addWidget(self.save_as_button)
        
        self.copy_button = QPushButton("Copy Config")
        self.copy_button.clicked.connect(self._on_copy_config)
        actions_layout.addWidget(self.copy_button)
        
        self.open_folder_button = QPushButton("Open Folder")
        self.open_folder_button.clicked.connect(self._on_open_folder)
        actions_layout.addWidget(self.open_folder_button)
        
        layout.addLayout(actions_layout)
        
        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        close_layout.addWidget(self.close_button)
        
        layout.addLayout(close_layout)
    
    def _get_monospace_font(self):
        """Get a monospace font for the preview."""
        from PyQt6.QtGui import QFont
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        return font
    
    def _load_config(self):
        """Load the configuration file content."""
        try:
            if self._config_path.exists():
                self._config_content = self._config_path.read_text(encoding="utf-8")
                self.preview_text.setPlainText(self._config_content)
            else:
                self.preview_text.setPlainText("Configuration file not found.")
                self._disable_actions()
        except Exception as e:
            self.preview_text.setPlainText(f"Error loading configuration:\n{e}")
            self._disable_actions()
    
    def _disable_actions(self):
        """Disable action buttons when config is unavailable."""
        self.save_as_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
    
    def _on_save_as(self):
        """Handle Save As button click."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration",
            f"{self._device_name}.conf",
            "WireGuard Config (*.conf);;All Files (*)"
        )
        
        if file_path and self._config_content:
            try:
                Path(file_path).write_text(self._config_content, encoding="utf-8")
                QMessageBox.information(
                    self, "Saved",
                    f"Configuration saved to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Error",
                    f"Failed to save configuration:\n{e}"
                )
    
    def _on_copy_config(self):
        """Handle Copy Config button click."""
        if self._config_content:
            clipboard = QApplication.clipboard()
            clipboard.setText(self._config_content)
            QMessageBox.information(
                self, "Copied",
                "Configuration copied to clipboard."
            )
    
    def _on_open_folder(self):
        """Handle Open Folder button click."""
        folder_path = self._config_path.parent
        
        if not folder_path.exists():
            QMessageBox.warning(
                self, "Warning",
                f"Folder does not exist:\n{folder_path}"
            )
            return
        
        try:
            # Windows-specific: open folder in Explorer
            if os.name == 'nt':
                # Use explorer to open folder and select the file if it exists
                if self._config_path.exists():
                    subprocess.run(['explorer', '/select,', str(self._config_path)], check=False)
                else:
                    subprocess.run(['explorer', str(folder_path)], check=False)
            else:
                # Fallback for other platforms
                subprocess.run(['xdg-open', str(folder_path)], check=False)
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to open folder:\n{e}"
            )
