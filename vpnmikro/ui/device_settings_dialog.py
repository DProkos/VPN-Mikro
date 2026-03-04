"""Device settings dialog for editing VPN client configuration.

Allows users to view and modify device-specific settings like:
- Device name
- Allowed IPs (split tunneling)
- DNS servers
- Persistent keepalive
- MTU
"""

from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox, QTextEdit,
    QPushButton, QLabel, QGroupBox, QMessageBox,
    QTabWidget, QWidget
)
from PyQt6.QtCore import Qt

from vpnmikro.core.models import Device
from vpnmikro.core.logger import get_logger
from vpnmikro.ui.assets import get_window_icon, load_theme

logger = get_logger(__name__)


class DeviceSettingsDialog(QDialog):
    """Dialog for editing device/VPN client settings.
    
    Provides tabs for:
    - General: Name, description
    - Network: Allowed IPs, DNS, MTU
    - Advanced: Keepalive, pre-shared key
    """
    
    def __init__(self, device: Device, config_content: str = "", parent=None):
        super().__init__(parent)
        self.device = device
        self.config_content = config_content
        self._modified = False
        
        self.setWindowTitle(f"Device Settings - {device.name}")
        self.setMinimumSize(500, 450)
        self.setModal(True)
        self.setWindowIcon(get_window_icon())
        self.setStyleSheet(load_theme())
        
        self._setup_ui()
        self._load_device_data()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # General tab
        self.tabs.addTab(self._create_general_tab(), "General")
        
        # Network tab
        self.tabs.addTab(self._create_network_tab(), "Network")
        
        # Advanced tab
        self.tabs.addTab(self._create_advanced_tab(), "Advanced")
        
        # Config tab (read-only view)
        self.tabs.addTab(self._create_config_tab(), "Config File")
        
        layout.addWidget(self.tabs)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
    
    def _create_general_tab(self) -> QWidget:
        """Create the General settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Device info group
        info_group = QGroupBox("Device Information")
        info_layout = QFormLayout()
        
        # Device name (read-only for now)
        self.name_input = QLineEdit()
        self.name_input.setReadOnly(True)
        self.name_input.setStyleSheet("background: #2a2d35;")
        info_layout.addRow("Name:", self.name_input)
        
        # UUID (read-only)
        self.uuid_label = QLabel()
        self.uuid_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.uuid_label.setStyleSheet("color: #888;")
        info_layout.addRow("UUID:", self.uuid_label)
        
        # Assigned IP (read-only)
        self.ip_label = QLabel()
        self.ip_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addRow("Assigned IP:", self.ip_label)
        
        # Created date
        self.created_label = QLabel()
        self.created_label.setStyleSheet("color: #888;")
        info_layout.addRow("Created:", self.created_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Status group
        status_group = QGroupBox("Status")
        status_layout = QFormLayout()
        
        self.enabled_checkbox = QCheckBox("Device Enabled")
        self.enabled_checkbox.setToolTip("Disable to prevent this device from connecting")
        status_layout.addRow("", self.enabled_checkbox)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        layout.addStretch()
        return widget
    
    def _create_network_tab(self) -> QWidget:
        """Create the Network settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Routing group
        routing_group = QGroupBox("Routing")
        routing_layout = QFormLayout()
        
        # Allowed IPs
        self.allowed_ips_input = QLineEdit()
        self.allowed_ips_input.setPlaceholderText("0.0.0.0/0, ::/0 (route all traffic)")
        self.allowed_ips_input.setToolTip(
            "Comma-separated list of IP ranges to route through VPN.\n"
            "0.0.0.0/0 = all IPv4 traffic\n"
            "::/0 = all IPv6 traffic\n"
            "10.0.0.0/8 = only 10.x.x.x traffic"
        )
        routing_layout.addRow("Allowed IPs:", self.allowed_ips_input)
        
        routing_group.setLayout(routing_layout)
        layout.addWidget(routing_group)
        
        # DNS group
        dns_group = QGroupBox("DNS")
        dns_layout = QFormLayout()
        
        self.dns_input = QLineEdit()
        self.dns_input.setPlaceholderText("1.1.1.1, 8.8.8.8")
        self.dns_input.setToolTip("Comma-separated DNS servers to use when VPN is active")
        dns_layout.addRow("DNS Servers:", self.dns_input)
        
        dns_group.setLayout(dns_layout)
        layout.addWidget(dns_group)
        
        # MTU group
        mtu_group = QGroupBox("MTU")
        mtu_layout = QFormLayout()
        
        self.mtu_input = QSpinBox()
        self.mtu_input.setRange(0, 9000)
        self.mtu_input.setValue(0)
        self.mtu_input.setSpecialValueText("Auto")
        self.mtu_input.setToolTip("Maximum Transmission Unit. 0 = auto-detect")
        mtu_layout.addRow("MTU:", self.mtu_input)
        
        mtu_group.setLayout(mtu_layout)
        layout.addWidget(mtu_group)
        
        layout.addStretch()
        return widget
    
    def _create_advanced_tab(self) -> QWidget:
        """Create the Advanced settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Keepalive group
        keepalive_group = QGroupBox("Connection")
        keepalive_layout = QFormLayout()
        
        self.keepalive_input = QSpinBox()
        self.keepalive_input.setRange(0, 3600)
        self.keepalive_input.setValue(20)
        self.keepalive_input.setSuffix(" seconds")
        self.keepalive_input.setSpecialValueText("Disabled")
        self.keepalive_input.setToolTip(
            "Send keepalive packets to maintain NAT mappings.\n"
            "Recommended: 20 seconds for mobile/NAT networks"
        )
        keepalive_layout.addRow("Persistent Keepalive:", self.keepalive_input)
        
        keepalive_group.setLayout(keepalive_layout)
        layout.addWidget(keepalive_group)
        
        # Keys group (read-only)
        keys_group = QGroupBox("Keys")
        keys_layout = QFormLayout()
        
        self.pubkey_label = QLabel()
        self.pubkey_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.pubkey_label.setWordWrap(True)
        self.pubkey_label.setStyleSheet("font-family: monospace; font-size: 11px;")
        keys_layout.addRow("Public Key:", self.pubkey_label)
        
        keys_group.setLayout(keys_layout)
        layout.addWidget(keys_group)
        
        # Warning
        warning = QLabel(
            "⚠️ Changing advanced settings may require reconnecting the VPN."
        )
        warning.setStyleSheet("color: #f59e0b; font-style: italic;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        layout.addStretch()
        return widget
    
    def _create_config_tab(self) -> QWidget:
        """Create the Config File tab (read-only view)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Config path
        path_layout = QHBoxLayout()
        path_label = QLabel("Config File:")
        self.config_path_label = QLabel()
        self.config_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.config_path_label.setStyleSheet("color: #888;")
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.config_path_label, 1)
        layout.addLayout(path_layout)
        
        # Config content (read-only)
        self.config_text = QTextEdit()
        self.config_text.setReadOnly(True)
        self.config_text.setStyleSheet(
            "font-family: 'Consolas', 'Monaco', monospace; "
            "font-size: 12px; "
            "background: #1a1d23; "
            "border: 1px solid #333;"
        )
        layout.addWidget(self.config_text)
        
        # Reload button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_reload = QPushButton("Reload")
        self.btn_reload.clicked.connect(self._reload_config)
        btn_layout.addWidget(self.btn_reload)
        
        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_open_folder.clicked.connect(self._open_config_folder)
        btn_layout.addWidget(self.btn_open_folder)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def _load_device_data(self):
        """Load device data into the form."""
        # General tab
        self.name_input.setText(self.device.name)
        self.uuid_label.setText(self.device.uuid)
        self.ip_label.setText(self.device.assigned_ip)
        self.created_label.setText(
            self.device.created_at.strftime("%Y-%m-%d %H:%M") if self.device.created_at else "-"
        )
        self.enabled_checkbox.setChecked(self.device.enabled)
        
        # Network tab - parse from config if available
        self._parse_config_values()
        
        # Advanced tab
        self.pubkey_label.setText(self.device.public_key or "-")
        
        # Config tab
        self.config_path_label.setText(self.device.config_path or "-")
        self._reload_config()
    
    def _parse_config_values(self):
        """Parse network values from config content."""
        if not self.config_content:
            self._reload_config()
        
        # Parse AllowedIPs
        for line in self.config_content.split('\n'):
            line = line.strip()
            if line.lower().startswith('allowedips'):
                _, _, value = line.partition('=')
                self.allowed_ips_input.setText(value.strip())
            elif line.lower().startswith('dns'):
                _, _, value = line.partition('=')
                self.dns_input.setText(value.strip())
            elif line.lower().startswith('mtu'):
                _, _, value = line.partition('=')
                try:
                    self.mtu_input.setValue(int(value.strip()))
                except ValueError:
                    pass
            elif line.lower().startswith('persistentkeepalive'):
                _, _, value = line.partition('=')
                try:
                    self.keepalive_input.setValue(int(value.strip()))
                except ValueError:
                    pass
    
    def _reload_config(self):
        """Reload config file content."""
        if self.device.config_path:
            config_path = Path(self.device.config_path)
            if config_path.exists():
                try:
                    self.config_content = config_path.read_text(encoding='utf-8')
                    self.config_text.setPlainText(self.config_content)
                except Exception as e:
                    self.config_text.setPlainText(f"Error reading config: {e}")
            else:
                self.config_text.setPlainText("Config file not found")
        else:
            self.config_text.setPlainText("No config file path")
    
    def _open_config_folder(self):
        """Open the config folder in file explorer."""
        if self.device.config_path:
            config_path = Path(self.device.config_path)
            folder = config_path.parent
            if folder.exists():
                import subprocess
                subprocess.run(['explorer', str(folder)])
    
    def _on_save(self):
        """Handle Save button click."""
        # For now, just save enabled status
        # Full config editing would require regenerating the config file
        
        self.device.enabled = self.enabled_checkbox.isChecked()
        
        # TODO: Update config file with new values
        # This would require:
        # 1. Parse existing config
        # 2. Update values
        # 3. Write back
        # 4. If connected, reconnect
        
        QMessageBox.information(
            self, "Saved",
            "Device settings saved.\n\n"
            "Note: Network settings changes require regenerating the config file."
        )
        
        self.accept()
    
    def get_device(self) -> Device:
        """Get the modified device."""
        return self.device
