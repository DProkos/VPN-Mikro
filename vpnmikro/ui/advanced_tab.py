"""Advanced tab for network settings with gated access."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QComboBox, QTextEdit, QCheckBox,
    QPushButton, QGroupBox, QMessageBox, QLabel, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt


class AdvancedTab(QWidget):
    """Advanced network settings tab with gated access.
    
    Provides configuration for:
    - IP pool CIDR range
    - DNS override
    - Tunnel mode (Full/Split)
    - Split subnets
    - MTU value
    - PersistentKeepalive interval
    
    All inputs are disabled until user acknowledges the warning gate.
    
    Signals:
        settings_changed: Emitted when settings are modified
    """
    
    settings_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._update_inputs_enabled()
    
    def _setup_ui(self):
        """Set up the advanced tab UI."""
        layout = QVBoxLayout(self)
        
        # Warning gate section
        gate_frame = QFrame()
        gate_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        gate_frame.setStyleSheet("QFrame { background-color: #fff3cd; border: 1px solid #ffc107; }")
        gate_layout = QVBoxLayout(gate_frame)
        
        warning_label = QLabel(
            "⚠️ Advanced Settings\n\n"
            "These settings can affect VPN connectivity and network behavior.\n"
            "Only modify if you understand the implications."
        )
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("color: #856404; font-weight: bold;")
        gate_layout.addWidget(warning_label)
        
        self.enable_toggle = QCheckBox("I know what I'm doing - enable advanced settings")
        self.enable_toggle.setStyleSheet("color: #856404;")
        self.enable_toggle.toggled.connect(self._on_gate_toggled)
        gate_layout.addWidget(self.enable_toggle)
        
        layout.addWidget(gate_frame)
        
        # IP Pool settings group
        pool_group = QGroupBox("IP Pool Configuration")
        pool_layout = QFormLayout()
        
        self.ip_pool_input = QLineEdit()
        self.ip_pool_input.setPlaceholderText("10.66.0.0/24")
        self.ip_pool_input.setText("10.66.0.0/24")
        self.ip_pool_input.setToolTip("CIDR range for client IP allocation")
        pool_layout.addRow("IP Pool (CIDR):", self.ip_pool_input)
        
        pool_group.setLayout(pool_layout)
        layout.addWidget(pool_group)
        self._pool_group = pool_group
        
        # Network settings group
        network_group = QGroupBox("Network Settings")
        network_layout = QFormLayout()
        
        # DNS input
        self.dns_input = QLineEdit()
        self.dns_input.setPlaceholderText("1.1.1.1, 8.8.8.8")
        self.dns_input.setToolTip("DNS servers (comma-separated)")
        network_layout.addRow("DNS Servers:", self.dns_input)
        
        # MTU input
        self.mtu_input = QSpinBox()
        self.mtu_input.setRange(1280, 1500)
        self.mtu_input.setValue(1420)
        self.mtu_input.setSpecialValueText("Auto")
        self.mtu_input.setToolTip("MTU value (1280-1500, default 1420)")
        network_layout.addRow("MTU:", self.mtu_input)
        
        # Keepalive input
        self.keepalive_input = QSpinBox()
        self.keepalive_input.setRange(0, 300)
        self.keepalive_input.setValue(20)
        self.keepalive_input.setSpecialValueText("Disabled")
        self.keepalive_input.setToolTip("PersistentKeepalive interval in seconds (0 to disable)")
        network_layout.addRow("Keepalive (sec):", self.keepalive_input)
        
        network_group.setLayout(network_layout)
        layout.addWidget(network_group)
        self._network_group = network_group
        
        # Tunnel mode group
        tunnel_group = QGroupBox("Tunnel Mode")
        tunnel_layout = QVBoxLayout()
        
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Mode:")
        mode_layout.addWidget(mode_label)
        
        self.tunnel_mode = QComboBox()
        self.tunnel_mode.addItem("Full Tunnel (0.0.0.0/0, ::/0)", "full")
        self.tunnel_mode.addItem("Split Tunnel (custom subnets)", "split")
        self.tunnel_mode.currentIndexChanged.connect(self._on_tunnel_mode_changed)
        mode_layout.addWidget(self.tunnel_mode)
        mode_layout.addStretch()
        
        tunnel_layout.addLayout(mode_layout)
        
        # Split subnets input (only visible in split mode)
        self.split_label = QLabel("Allowed Subnets (one per line):")
        tunnel_layout.addWidget(self.split_label)
        
        self.split_subnets = QTextEdit()
        self.split_subnets.setPlaceholderText("192.168.1.0/24\n10.0.0.0/8")
        self.split_subnets.setMaximumHeight(100)
        self.split_subnets.setToolTip("Subnets to route through VPN (CIDR format, one per line)")
        tunnel_layout.addWidget(self.split_subnets)
        
        tunnel_group.setLayout(tunnel_layout)
        layout.addWidget(tunnel_group)
        self._tunnel_group = tunnel_group
        
        # Initially hide split subnets
        self._update_split_visibility()
        
        # Save button
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save Advanced Settings")
        self.save_button.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_button)
        
        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.clicked.connect(self._on_reset)
        button_layout.addWidget(self.reset_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Add stretch to push everything to top
        layout.addStretch()
    
    def _on_gate_toggled(self, checked: bool):
        """Handle gate toggle - enable/disable inputs."""
        self._update_inputs_enabled()
        
        if checked:
            self.status_label.setText("Advanced settings enabled.")
            self.status_label.setStyleSheet("color: orange;")
        else:
            self.status_label.setText("")
    
    def _update_inputs_enabled(self):
        """Update enabled state of all inputs based on gate."""
        enabled = self.enable_toggle.isChecked()
        
        # Enable/disable all input widgets
        self.ip_pool_input.setEnabled(enabled)
        self.dns_input.setEnabled(enabled)
        self.mtu_input.setEnabled(enabled)
        self.keepalive_input.setEnabled(enabled)
        self.tunnel_mode.setEnabled(enabled)
        self.split_subnets.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.reset_button.setEnabled(enabled)
        
        # Visual feedback for groups
        opacity = "1.0" if enabled else "0.5"
        for group in [self._pool_group, self._network_group, self._tunnel_group]:
            group.setStyleSheet(f"QGroupBox {{ opacity: {opacity}; }}")
    
    def _on_tunnel_mode_changed(self, index: int):
        """Handle tunnel mode change."""
        self._update_split_visibility()
    
    def _update_split_visibility(self):
        """Show/hide split subnets based on tunnel mode."""
        is_split = self.tunnel_mode.currentData() == "split"
        self.split_label.setVisible(is_split)
        self.split_subnets.setVisible(is_split)
    
    def _on_save(self):
        """Handle Save button click."""
        # Validate IP pool
        ip_pool = self.ip_pool_input.text().strip()
        if ip_pool:
            if "/" not in ip_pool:
                self._show_error("IP pool must be in CIDR format (e.g., 10.66.0.0/24)")
                return
            try:
                from vpnmikro.core.ip_allocator import IPAllocator
                IPAllocator(ip_pool)  # Validate by creating allocator
            except Exception as e:
                self._show_error(f"Invalid IP pool: {e}")
                return
        
        # Validate split subnets if in split mode
        if self.tunnel_mode.currentData() == "split":
            subnets = self._get_split_subnets()
            if not subnets:
                self._show_error("Please enter at least one subnet for split tunnel mode.")
                return
        
        self.status_label.setText("Advanced settings saved.")
        self.status_label.setStyleSheet("color: green;")
        self.settings_changed.emit()
        QMessageBox.information(self, "Saved", "Advanced settings saved.\nNew devices will use these settings.")
    
    def _on_reset(self):
        """Handle Reset to Defaults button click."""
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Reset all advanced settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.ip_pool_input.setText("10.66.0.0/24")
            self.dns_input.clear()
            self.mtu_input.setValue(1420)
            self.keepalive_input.setValue(20)
            self.tunnel_mode.setCurrentIndex(0)  # Full tunnel
            self.split_subnets.clear()
            
            self.status_label.setText("Settings reset to defaults.")
            self.status_label.setStyleSheet("color: green;")
    
    def _show_error(self, message: str):
        """Show error message."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: red;")
        QMessageBox.warning(self, "Error", message)
    
    def _get_split_subnets(self) -> list:
        """Parse split subnets from text input.
        
        Returns:
            List of subnet strings
        """
        text = self.split_subnets.toPlainText().strip()
        if not text:
            return []
        
        subnets = []
        for line in text.split("\n"):
            line = line.strip()
            if line and "/" in line:
                subnets.append(line)
        return subnets
    
    def load_settings(self, profile):
        """Load settings from profile.
        
        Args:
            profile: Profile object with advanced settings
        """
        if profile.ip_pool:
            self.ip_pool_input.setText(profile.ip_pool)
        if profile.dns:
            self.dns_input.setText(profile.dns)
        if profile.mtu:
            self.mtu_input.setValue(profile.mtu)
        if profile.keepalive is not None:
            self.keepalive_input.setValue(profile.keepalive)
        
        # Set tunnel mode
        mode_index = 0 if profile.tunnel_mode == "full" else 1
        self.tunnel_mode.setCurrentIndex(mode_index)
        
        # Set split subnets
        if profile.split_subnets:
            self.split_subnets.setPlainText("\n".join(profile.split_subnets))
    
    def get_settings(self) -> dict:
        """Get current advanced settings.
        
        Returns:
            Dictionary with all advanced settings
        """
        return {
            "ip_pool": self.ip_pool_input.text().strip() or "10.66.0.0/24",
            "dns": self.dns_input.text().strip() or None,
            "mtu": self.mtu_input.value() if self.mtu_input.value() > 0 else None,
            "keepalive": self.keepalive_input.value(),
            "tunnel_mode": self.tunnel_mode.currentData(),
            "split_subnets": self._get_split_subnets()
        }
