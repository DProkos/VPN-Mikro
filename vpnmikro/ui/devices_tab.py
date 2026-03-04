"""Devices tab for VPN device management."""

from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox,
    QInputDialog, QAbstractItemView, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QColor


class DevicesTab(QWidget):
    """Device management tab with table view.
    
    Displays devices in a table with columns:
    Name, IP, Status, Enabled, Last Handshake, Created
    
    Provides buttons for device operations:
    Add, Connect, Disconnect, Export, QR, Copy PubKey, Delete
    
    Signals:
        device_added: Emitted when device is added (device_name)
        device_connected: Emitted when device connects (device_uuid)
        device_disconnected: Emitted when device disconnects (device_uuid)
        device_deleted: Emitted when device is deleted (device_uuid)
    """
    
    device_added = pyqtSignal(str)
    device_connected = pyqtSignal(str)
    device_disconnected = pyqtSignal(str)
    device_deleted = pyqtSignal(str)
    
    # Column indices
    COL_NAME = 0
    COL_IP = 1
    COL_STATUS = 2
    COL_ENABLED = 3
    COL_HANDSHAKE = 4
    COL_CREATED = 5
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices = []  # Cache of Device objects
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the devices tab UI."""
        layout = QVBoxLayout(self)
        
        # Devices table
        self.devices_table = QTableWidget()
        self.devices_table.setColumnCount(6)
        self.devices_table.setHorizontalHeaderLabels([
            "Name", "IP", "Status", "Enabled", "Last Handshake", "Created"
        ])
        
        # Table settings
        self.devices_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.devices_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.devices_table.setAlternatingRowColors(True)
        self.devices_table.setSortingEnabled(True)
        
        # Column sizing
        header = self.devices_table.horizontalHeader()
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_IP, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_ENABLED, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_HANDSHAKE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_CREATED, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.devices_table)
        
        # Button row
        button_layout = QHBoxLayout()
        
        self.add_button = QPushButton("Add Device")
        self.add_button.clicked.connect(self._on_add_device)
        button_layout.addWidget(self.add_button)
        
        button_layout.addSpacing(20)
        
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self._on_connect)
        button_layout.addWidget(self.connect_button)
        
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self._on_disconnect)
        button_layout.addWidget(self.disconnect_button)
        
        button_layout.addSpacing(20)
        
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._on_export)
        button_layout.addWidget(self.export_button)
        
        self.qr_button = QPushButton("QR")
        self.qr_button.clicked.connect(self._on_show_qr)
        button_layout.addWidget(self.qr_button)
        
        self.copy_pubkey_button = QPushButton("Copy PubKey")
        self.copy_pubkey_button.clicked.connect(self._on_copy_pubkey)
        button_layout.addWidget(self.copy_pubkey_button)
        
        button_layout.addSpacing(20)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.setStyleSheet("color: red;")
        self.delete_button.clicked.connect(self._on_delete)
        button_layout.addWidget(self.delete_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
    
    def _get_selected_device(self):
        """Get the currently selected device.
        
        Returns:
            Device object or None if no selection
        """
        row = self.devices_table.currentRow()
        if row < 0 or row >= len(self._devices):
            return None
        return self._devices[row]
    
    def _on_add_device(self):
        """Handle Add Device button click."""
        name, ok = QInputDialog.getText(
            self, "Add Device",
            "Enter device name:",
            text="my-device"
        )
        
        if ok and name:
            name = name.strip()
            if not name:
                QMessageBox.warning(self, "Error", "Device name cannot be empty.")
                return
            
            # Validate name (alphanumeric, hyphens, underscores)
            if not all(c.isalnum() or c in "-_" for c in name):
                QMessageBox.warning(
                    self, "Error",
                    "Device name can only contain letters, numbers, hyphens, and underscores."
                )
                return
            
            self.status_label.setText(f"Creating device '{name}'...")
            self.device_added.emit(name)
    
    def _on_connect(self):
        """Handle Connect button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "Warning", "Please select a device to connect.")
            return
        
        self.status_label.setText(f"Connecting '{device.name}'...")
        self.device_connected.emit(device.uuid)
    
    def _on_disconnect(self):
        """Handle Disconnect button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "Warning", "Please select a device to disconnect.")
            return
        
        self.status_label.setText(f"Disconnecting '{device.name}'...")
        self.device_disconnected.emit(device.uuid)
    
    def _on_export(self):
        """Handle Export button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "Warning", "Please select a device to export.")
            return
        
        from vpnmikro.ui.export_dialog import ExportDialog
        dialog = ExportDialog(device.name, device.config_path, self)
        dialog.exec()
    
    def _on_show_qr(self):
        """Handle QR button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "Warning", "Please select a device to show QR code.")
            return
        
        from pathlib import Path
        
        try:
            config_path = Path(device.config_path)
            if not config_path.exists():
                QMessageBox.warning(
                    self, "Error",
                    f"Configuration file not found:\n{device.config_path}"
                )
                return
            
            config_content = config_path.read_text(encoding="utf-8")
            
            from vpnmikro.ui.qr_dialog import QRCodeDialog
            dialog = QRCodeDialog(device.name, config_content, self)
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate QR code:\n{e}")
    
    def _on_copy_pubkey(self):
        """Handle Copy PubKey button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "Warning", "Please select a device.")
            return
        
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(device.public_key)
        
        self.status_label.setText(f"Public key copied to clipboard.")
        self.status_label.setStyleSheet("color: green;")
    
    def _on_delete(self):
        """Handle Delete button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "Warning", "Please select a device to delete.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete device '{device.name}'?\n\n"
            "This will remove the peer from MikroTik and delete the local configuration.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.status_label.setText(f"Deleting '{device.name}'...")
            self.device_deleted.emit(device.uuid)
    
    def set_devices(self, devices: list):
        """Set the devices to display in the table.
        
        Args:
            devices: List of Device objects
        """
        self._devices = devices
        self.devices_table.setRowCount(len(devices))
        
        for row, device in enumerate(devices):
            # Name
            name_item = QTableWidgetItem(device.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.devices_table.setItem(row, self.COL_NAME, name_item)
            
            # IP
            ip_item = QTableWidgetItem(device.assigned_ip)
            ip_item.setFlags(ip_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.devices_table.setItem(row, self.COL_IP, ip_item)
            
            # Status (will be updated by update_device_status)
            status_item = QTableWidgetItem("Disconnected")
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.devices_table.setItem(row, self.COL_STATUS, status_item)
            
            # Enabled
            enabled_text = "Yes" if device.enabled else "No"
            enabled_item = QTableWidgetItem(enabled_text)
            enabled_item.setFlags(enabled_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if not device.enabled:
                enabled_item.setForeground(QColor("gray"))
            self.devices_table.setItem(row, self.COL_ENABLED, enabled_item)
            
            # Last Handshake (placeholder - updated from tunnel status)
            handshake_item = QTableWidgetItem("-")
            handshake_item.setFlags(handshake_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.devices_table.setItem(row, self.COL_HANDSHAKE, handshake_item)
            
            # Created
            created_str = device.created_at.strftime("%Y-%m-%d %H:%M") if device.created_at else "-"
            created_item = QTableWidgetItem(created_str)
            created_item.setFlags(created_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.devices_table.setItem(row, self.COL_CREATED, created_item)
    
    def update_device_status(self, device_uuid: str, connected: bool, last_handshake: datetime = None):
        """Update the status display for a device.
        
        Args:
            device_uuid: UUID of the device to update
            connected: Whether the device is connected
            last_handshake: Last handshake time (optional)
        """
        for row, device in enumerate(self._devices):
            if device.uuid == device_uuid:
                # Update status column
                status_text = "Active" if connected else "Disconnected"
                status_item = self.devices_table.item(row, self.COL_STATUS)
                if status_item:
                    status_item.setText(status_text)
                    if connected:
                        status_item.setForeground(QColor("green"))
                    else:
                        status_item.setForeground(QColor("gray"))
                
                # Update handshake column
                if last_handshake:
                    handshake_str = last_handshake.strftime("%H:%M:%S")
                    handshake_item = self.devices_table.item(row, self.COL_HANDSHAKE)
                    if handshake_item:
                        handshake_item.setText(handshake_str)
                break
    
    def add_device_to_table(self, device):
        """Add a single device to the table.
        
        Args:
            device: Device object to add
        """
        self._devices.append(device)
        self.set_devices(self._devices)
        
        # Select the new device
        self.devices_table.selectRow(len(self._devices) - 1)
        
        self.status_label.setText(f"Device '{device.name}' created.")
        self.status_label.setStyleSheet("color: green;")
    
    def remove_device_from_table(self, device_uuid: str):
        """Remove a device from the table.
        
        Args:
            device_uuid: UUID of device to remove
        """
        self._devices = [d for d in self._devices if d.uuid != device_uuid]
        self.set_devices(self._devices)
        
        self.status_label.setText("Device deleted.")
        self.status_label.setStyleSheet("color: green;")
