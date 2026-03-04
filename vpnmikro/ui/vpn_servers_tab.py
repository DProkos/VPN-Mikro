"""VPN Servers tab for WireGuard interface selection."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QPushButton, QGroupBox,
    QMessageBox, QLabel
)
from PyQt6.QtCore import pyqtSignal


class VPNServersTab(QWidget):
    """WireGuard interface selection tab.
    
    Allows selecting a WireGuard interface from the MikroTik router,
    configuring the public endpoint and server public key.
    
    Signals:
        interface_selected: Emitted when interface is selected (interface_name)
        settings_saved: Emitted when settings are saved
    """
    
    interface_selected = pyqtSignal(str)
    settings_saved = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._interfaces = []  # Cache of WGInterface objects
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the VPN servers tab UI."""
        layout = QVBoxLayout(self)
        
        # WireGuard Interface group
        interface_group = QGroupBox("WireGuard Interface")
        interface_layout = QVBoxLayout()
        
        # Interface dropdown with refresh button
        dropdown_layout = QHBoxLayout()
        
        self.interface_dropdown = QComboBox()
        self.interface_dropdown.setPlaceholderText("Select WireGuard interface...")
        self.interface_dropdown.currentIndexChanged.connect(self._on_interface_changed)
        dropdown_layout.addWidget(self.interface_dropdown, stretch=1)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._on_refresh)
        dropdown_layout.addWidget(self.refresh_button)
        
        interface_layout.addLayout(dropdown_layout)
        
        # Interface info label
        self.interface_info_label = QLabel("")
        self.interface_info_label.setStyleSheet("color: gray; font-style: italic;")
        interface_layout.addWidget(self.interface_info_label)
        
        interface_group.setLayout(interface_layout)
        layout.addWidget(interface_group)
        
        # Server Settings group
        server_group = QGroupBox("Server Settings")
        server_layout = QFormLayout()
        
        # Endpoint input with auto-fill button
        endpoint_layout = QHBoxLayout()
        self.endpoint_input = QLineEdit()
        self.endpoint_input.setPlaceholderText("domain.com:51820 or IP:port")
        endpoint_layout.addWidget(self.endpoint_input, stretch=1)
        
        self.autofill_port_button = QPushButton("Auto-fill Port")
        self.autofill_port_button.setToolTip("Fill port from selected WireGuard interface")
        self.autofill_port_button.clicked.connect(self._on_autofill_port)
        endpoint_layout.addWidget(self.autofill_port_button)
        
        server_layout.addRow("Public Endpoint:", endpoint_layout)
        
        # Server public key input
        self.server_pubkey_input = QLineEdit()
        self.server_pubkey_input.setPlaceholderText("Base64 encoded public key")
        server_layout.addRow("Server Public Key:", self.server_pubkey_input)
        
        server_group.setLayout(server_layout)
        layout.addWidget(server_group)
        
        # Save button
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Add stretch to push everything to top
        layout.addStretch()
    
    def _on_interface_changed(self, index: int):
        """Handle interface selection change."""
        if index < 0 or index >= len(self._interfaces):
            self.interface_info_label.setText("")
            return
        
        interface = self._interfaces[index]
        self.interface_info_label.setText(
            f"Listen Port: {interface.listen_port} | "
            f"Public Key: {interface.public_key[:20]}..."
        )
        self.interface_selected.emit(interface.name)
    
    def _on_refresh(self):
        """Handle Refresh button click - fetch interfaces from MikroTik."""
        self.status_label.setText("Fetching interfaces...")
        self.refresh_button.setEnabled(False)
        
        # Signal to parent to refresh interfaces
        # The MainWindow will handle the actual fetching
        try:
            # Get parent window and trigger refresh
            main_window = self.window()
            if hasattr(main_window, '_refresh_interfaces'):
                if main_window._ensure_connection():
                    main_window._refresh_interfaces()
                    self.status_label.setText("Interfaces refreshed")
                    self.status_label.setStyleSheet("color: green;")
                else:
                    self.status_label.setText("Connection required")
                    self.status_label.setStyleSheet("color: orange;")
            else:
                self.status_label.setText("Connect to MikroTik first (Connection tab)")
                self.status_label.setStyleSheet("color: orange;")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            self.status_label.setStyleSheet("color: red;")
        finally:
            self.refresh_button.setEnabled(True)
    
    def _on_autofill_port(self):
        """Auto-fill endpoint port from selected interface."""
        index = self.interface_dropdown.currentIndex()
        if index < 0 or index >= len(self._interfaces):
            QMessageBox.warning(self, "Warning", "Please select a WireGuard interface first.")
            return
        
        interface = self._interfaces[index]
        current_endpoint = self.endpoint_input.text().strip()
        
        if ":" in current_endpoint:
            # Replace existing port
            host = current_endpoint.rsplit(":", 1)[0]
            self.endpoint_input.setText(f"{host}:{interface.listen_port}")
        elif current_endpoint:
            # Add port to existing host
            self.endpoint_input.setText(f"{current_endpoint}:{interface.listen_port}")
        else:
            # Just set the port placeholder
            self.endpoint_input.setPlaceholderText(f"domain.com:{interface.listen_port}")
    
    def _on_save(self):
        """Handle Save Settings button click."""
        interface_index = self.interface_dropdown.currentIndex()
        endpoint = self.endpoint_input.text().strip()
        server_pubkey = self.server_pubkey_input.text().strip()
        
        # Validate
        if interface_index < 0:
            self._show_error("Please select a WireGuard interface.")
            return
        if not endpoint:
            self._show_error("Please enter the public endpoint.")
            return
        if not server_pubkey:
            self._show_error("Please enter the server public key.")
            return
        
        # Validate endpoint format
        if ":" not in endpoint:
            self._show_error("Endpoint must include port (e.g., domain.com:51820)")
            return
        
        try:
            # Save to current profile (will be wired in task 15)
            self.status_label.setText("Settings saved.")
            self.status_label.setStyleSheet("color: green;")
            self.settings_saved.emit()
            QMessageBox.information(self, "Saved", "VPN server settings saved.")
            
        except Exception as e:
            self._show_error(f"Failed to save: {e}")
    
    def _show_error(self, message: str):
        """Show error message."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: red;")
        QMessageBox.warning(self, "Error", message)
    
    def set_interfaces(self, interfaces: list):
        """Set available WireGuard interfaces.
        
        Args:
            interfaces: List of WGInterface objects
        """
        self._interfaces = interfaces
        self.interface_dropdown.clear()
        
        for iface in interfaces:
            self.interface_dropdown.addItem(
                f"{iface.name} (:{iface.listen_port})"
            )
    
    def load_settings(self, profile):
        """Load settings from profile.
        
        Args:
            profile: Profile object with VPN server settings
        """
        if profile.endpoint:
            self.endpoint_input.setText(profile.endpoint)
        if profile.server_public_key:
            self.server_pubkey_input.setText(profile.server_public_key)
        
        # Select interface if set
        if profile.selected_interface and self._interfaces:
            for i, iface in enumerate(self._interfaces):
                if iface.name == profile.selected_interface:
                    self.interface_dropdown.setCurrentIndex(i)
                    break
    
    def get_settings(self) -> dict:
        """Get current VPN server settings.
        
        Returns:
            Dictionary with interface, endpoint, server_public_key
        """
        interface_name = None
        index = self.interface_dropdown.currentIndex()
        if 0 <= index < len(self._interfaces):
            interface_name = self._interfaces[index].name
        
        return {
            "selected_interface": interface_name,
            "endpoint": self.endpoint_input.text().strip(),
            "server_public_key": self.server_pubkey_input.text().strip()
        }
