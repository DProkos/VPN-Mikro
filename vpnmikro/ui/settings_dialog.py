"""Settings dialog with tabbed interface.

Provides configuration for:
- Connection: MikroTik credentials
- VPN Server: WireGuard interface, endpoint, public key
- Advanced: IP pool, DNS, tunnel mode, MTU, keepalive
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLineEdit, QSpinBox, QCheckBox, QComboBox,
    QPushButton, QLabel, QTextEdit, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt

from vpnmikro.ui.assets import icon, Icons, ICON_SIZE_MD, load_theme, get_window_icon
from vpnmikro.core.models import Profile
from vpnmikro.core.profiles import ProfileManager
from vpnmikro.core.logger import get_logger

logger = get_logger(__name__)


class SettingsDialog(QDialog):
    """Settings dialog with Connection, VPN Server, and Advanced tabs."""
    
    def __init__(
        self,
        profile: Optional[Profile],
        profile_manager: ProfileManager,
        parent=None,
        new_profile: bool = False
    ):
        super().__init__(parent)
        self._profile = profile
        self._profile_manager = profile_manager
        self._new_profile = new_profile
        self._interfaces = []
        
        self.setWindowTitle("New Profile" if new_profile else "Settings")
        self.setMinimumSize(550, 500)
        self.setStyleSheet(load_theme())
        self.setWindowIcon(get_window_icon())
        
        self._setup_ui()
        self._load_profile_data()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Profile name (for new profiles)
        if self._new_profile:
            name_layout = QFormLayout()
            self.name_input = QLineEdit()
            self.name_input.setPlaceholderText("my-router")
            name_layout.addRow("Profile Name:", self.name_input)
            layout.addLayout(name_layout)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_connection_tab(), "Connection")
        self.tabs.addTab(self._create_vpn_server_tab(), "VPN Server")
        self.tabs.addTab(self._create_advanced_tab(), "Advanced")
        layout.addWidget(self.tabs)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_save = QPushButton(" Save")
        self.btn_save.setIcon(icon(Icons.CHECK))
        self.btn_save.setIconSize(ICON_SIZE_MD)
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.clicked.connect(self._on_save)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
    
    def _create_connection_tab(self) -> QWidget:
        """Create the Connection settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        form = QFormLayout()
        
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("192.168.88.1 or router.example.com")
        form.addRow("Host:", self.host_input)
        
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(8729)
        form.addRow("Port:", self.port_input)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("admin")
        form.addRow("Username:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Password")
        form.addRow("Password:", self.password_input)
        
        layout.addLayout(form)
        
        self.verify_tls_checkbox = QCheckBox("Verify TLS certificate")
        self.verify_tls_checkbox.setToolTip("Enable for trusted certificates. Default OFF for self-signed.")
        layout.addWidget(self.verify_tls_checkbox)
        
        # Test button
        test_layout = QHBoxLayout()
        self.btn_test_conn = QPushButton(" Test Connection")
        self.btn_test_conn.setIcon(icon(Icons.REFRESH))
        self.btn_test_conn.setIconSize(ICON_SIZE_MD)
        self.btn_test_conn.clicked.connect(self._on_test_connection)
        test_layout.addWidget(self.btn_test_conn)
        
        self.conn_status_label = QLabel("")
        test_layout.addWidget(self.conn_status_label)
        test_layout.addStretch()
        
        layout.addLayout(test_layout)
        layout.addStretch()
        
        return widget
    
    def _create_vpn_server_tab(self) -> QWidget:
        """Create the VPN Server settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        form = QFormLayout()
        
        # Interface dropdown
        iface_layout = QHBoxLayout()
        self.interface_combo = QComboBox()
        self.interface_combo.setPlaceholderText("Select interface...")
        iface_layout.addWidget(self.interface_combo, 1)
        
        self.btn_refresh_iface = QPushButton()
        self.btn_refresh_iface.setIcon(icon(Icons.REFRESH))
        self.btn_refresh_iface.setIconSize(ICON_SIZE_MD)
        self.btn_refresh_iface.setToolTip("Refresh interfaces")
        self.btn_refresh_iface.clicked.connect(self._on_refresh_interfaces)
        iface_layout.addWidget(self.btn_refresh_iface)
        
        form.addRow("WireGuard Interface:", iface_layout)
        
        # Endpoint
        endpoint_layout = QHBoxLayout()
        self.endpoint_input = QLineEdit()
        self.endpoint_input.setPlaceholderText("vpn.example.com:51820")
        endpoint_layout.addWidget(self.endpoint_input, 1)
        
        self.btn_autofill_port = QPushButton("Auto Port")
        self.btn_autofill_port.clicked.connect(self._on_autofill_port)
        endpoint_layout.addWidget(self.btn_autofill_port)
        
        form.addRow("Public Endpoint:", endpoint_layout)
        
        # Server public key
        pubkey_layout = QHBoxLayout()
        self.server_pubkey_input = QLineEdit()
        self.server_pubkey_input.setPlaceholderText("Base64 encoded public key")
        pubkey_layout.addWidget(self.server_pubkey_input, 1)
        
        self.btn_autofill_key = QPushButton("Auto Key")
        self.btn_autofill_key.clicked.connect(self._on_autofill_key)
        pubkey_layout.addWidget(self.btn_autofill_key)
        
        form.addRow("Server Public Key:", pubkey_layout)
        
        layout.addLayout(form)
        layout.addStretch()
        
        return widget
    
    def _create_advanced_tab(self) -> QWidget:
        """Create the Advanced settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Warning
        warning = QLabel("⚠️ Only modify if you understand the implications.")
        warning.setStyleSheet("color: #EAB308; font-style: italic; font-size: 12px;")
        layout.addWidget(warning)
        
        form = QFormLayout()
        
        self.ip_pool_input = QLineEdit()
        self.ip_pool_input.setText("10.66.0.0/24")
        self.ip_pool_input.setPlaceholderText("10.66.0.0/24")
        form.addRow("IP Pool (CIDR):", self.ip_pool_input)
        
        self.dns_input = QLineEdit()
        self.dns_input.setPlaceholderText("1.1.1.1, 8.8.8.8")
        form.addRow("DNS Servers:", self.dns_input)
        
        self.mtu_input = QSpinBox()
        self.mtu_input.setRange(1280, 1500)
        self.mtu_input.setValue(1420)
        form.addRow("MTU:", self.mtu_input)
        
        self.keepalive_input = QSpinBox()
        self.keepalive_input.setRange(0, 300)
        self.keepalive_input.setValue(20)
        self.keepalive_input.setSpecialValueText("Disabled")
        form.addRow("Keepalive (sec):", self.keepalive_input)
        
        layout.addLayout(form)
        
        # Tunnel mode
        mode_group = QGroupBox("Tunnel Mode")
        mode_layout = QVBoxLayout(mode_group)
        
        self.tunnel_mode_combo = QComboBox()
        self.tunnel_mode_combo.addItem("Full Tunnel (0.0.0.0/0, ::/0)", "full")
        self.tunnel_mode_combo.addItem("Split Tunnel (custom subnets)", "split")
        self.tunnel_mode_combo.currentIndexChanged.connect(self._on_tunnel_mode_changed)
        mode_layout.addWidget(self.tunnel_mode_combo)
        
        self.split_label = QLabel("Allowed Subnets (one per line):")
        mode_layout.addWidget(self.split_label)
        
        self.split_subnets_input = QTextEdit()
        self.split_subnets_input.setPlaceholderText("192.168.1.0/24\n10.0.0.0/8")
        self.split_subnets_input.setMaximumHeight(80)
        mode_layout.addWidget(self.split_subnets_input)
        
        layout.addWidget(mode_group)
        layout.addStretch()
        
        self._on_tunnel_mode_changed(0)
        
        return widget
    
    def _load_profile_data(self):
        """Load existing profile data into the form."""
        if not self._profile:
            return
        
        p = self._profile
        
        # Connection
        self.host_input.setText(p.host)
        self.port_input.setValue(p.port)
        self.verify_tls_checkbox.setChecked(p.verify_tls)
        
        # Load credentials
        try:
            username, password = self._profile_manager.decrypt_credentials(p)
            self.username_input.setText(username)
            self.password_input.setText(password)
        except Exception:
            pass
        
        # VPN Server
        if p.endpoint:
            self.endpoint_input.setText(p.endpoint)
        if p.server_public_key:
            self.server_pubkey_input.setText(p.server_public_key)
        
        # Advanced
        self.ip_pool_input.setText(p.ip_pool)
        if p.dns:
            self.dns_input.setText(p.dns)
        if p.mtu:
            self.mtu_input.setValue(p.mtu)
        if p.keepalive is not None:
            self.keepalive_input.setValue(p.keepalive)
        
        mode_index = 0 if p.tunnel_mode == "full" else 1
        self.tunnel_mode_combo.setCurrentIndex(mode_index)
        
        if p.split_subnets:
            self.split_subnets_input.setPlainText("\n".join(p.split_subnets))
    
    def _on_tunnel_mode_changed(self, index: int):
        """Show/hide split subnets based on mode."""
        is_split = self.tunnel_mode_combo.currentData() == "split"
        self.split_label.setVisible(is_split)
        self.split_subnets_input.setVisible(is_split)
    
    def _on_test_connection(self):
        """Test the connection with current settings."""
        host = self.host_input.text().strip()
        port = self.port_input.value()
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not host or not username or not password:
            QMessageBox.warning(self, "Missing Fields", "Please fill in all connection fields.")
            return
        
        self.conn_status_label.setText("Testing...")
        self.conn_status_label.setStyleSheet("color: #EAB308;")
        
        try:
            from vpnmikro.mikrotik.ros_client import ROSClient
            
            client = ROSClient(host, port, verify_tls=self.verify_tls_checkbox.isChecked())
            client.connect()
            success = client.login(username, password)
            client.disconnect()
            
            if success:
                self.conn_status_label.setText("✓ Success")
                self.conn_status_label.setStyleSheet("color: #22C55E;")
            else:
                self.conn_status_label.setText("✗ Auth failed")
                self.conn_status_label.setStyleSheet("color: #EF4444;")
        except Exception as e:
            self.conn_status_label.setText(f"✗ Failed")
            self.conn_status_label.setStyleSheet("color: #EF4444;")
            QMessageBox.critical(self, "Error", str(e))
    
    def _on_refresh_interfaces(self):
        """Refresh WireGuard interfaces from router."""
        host = self.host_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not host or not username or not password:
            QMessageBox.warning(self, "Missing Fields", "Please fill in connection fields first.")
            return
        
        try:
            from vpnmikro.mikrotik.ros_client import ROSClient
            from vpnmikro.mikrotik.wg_manager import WGPeerManager
            
            client = ROSClient(host, self.port_input.value(), verify_tls=self.verify_tls_checkbox.isChecked())
            client.connect()
            client.login(username, password)
            
            peer_manager = WGPeerManager(client)
            self._interfaces = peer_manager.list_interfaces()
            
            client.disconnect()
            
            self.interface_combo.clear()
            for iface in self._interfaces:
                self.interface_combo.addItem(f"{iface.name} (:{iface.listen_port})", iface.name)
            
            # Select current interface if set
            if self._profile and self._profile.selected_interface:
                for i, iface in enumerate(self._interfaces):
                    if iface.name == self._profile.selected_interface:
                        self.interface_combo.setCurrentIndex(i)
                        break
                        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch interfaces: {e}")
    
    def _on_autofill_port(self):
        """Auto-fill endpoint port from selected interface."""
        index = self.interface_combo.currentIndex()
        if index < 0 or index >= len(self._interfaces):
            QMessageBox.warning(self, "No Interface", "Please select an interface first.")
            return
        
        iface = self._interfaces[index]
        current = self.endpoint_input.text().strip()
        
        if ":" in current:
            host = current.rsplit(":", 1)[0]
            self.endpoint_input.setText(f"{host}:{iface.listen_port}")
        elif current:
            self.endpoint_input.setText(f"{current}:{iface.listen_port}")
    
    def _on_autofill_key(self):
        """Auto-fill server public key from selected interface."""
        index = self.interface_combo.currentIndex()
        if index < 0 or index >= len(self._interfaces):
            QMessageBox.warning(self, "No Interface", "Please select an interface first.")
            return
        
        iface = self._interfaces[index]
        self.server_pubkey_input.setText(iface.public_key)
    
    def _on_save(self):
        """Save the settings."""
        # Validate
        host = self.host_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not host:
            QMessageBox.warning(self, "Missing Field", "Host is required.")
            return
        
        if self._new_profile:
            name = self.name_input.text().strip()
            if not name:
                QMessageBox.warning(self, "Missing Field", "Profile name is required.")
                return
            if self._profile_manager.profile_exists(name):
                QMessageBox.warning(self, "Exists", f"Profile '{name}' already exists.")
                return
        else:
            name = self._profile.name if self._profile else host.replace(".", "-")
        
        try:
            # Create or update profile
            if self._new_profile or not self._profile:
                profile = Profile(name=name, host=host)
            else:
                profile = self._profile
                profile.host = host
            
            profile.port = self.port_input.value()
            profile.verify_tls = self.verify_tls_checkbox.isChecked()
            
            # Encrypt credentials
            if username and password:
                enc_user, enc_pass = self._profile_manager.encrypt_credentials(username, password)
                profile.username_encrypted = enc_user
                profile.password_encrypted = enc_pass
            
            # VPN Server
            iface_index = self.interface_combo.currentIndex()
            if iface_index >= 0 and iface_index < len(self._interfaces):
                profile.selected_interface = self._interfaces[iface_index].name
            
            profile.endpoint = self.endpoint_input.text().strip() or None
            profile.server_public_key = self.server_pubkey_input.text().strip() or None
            
            # Advanced
            profile.ip_pool = self.ip_pool_input.text().strip() or "10.66.0.0/24"
            profile.dns = self.dns_input.text().strip() or None
            profile.mtu = self.mtu_input.value() if self.mtu_input.value() > 0 else None
            profile.keepalive = self.keepalive_input.value()
            profile.tunnel_mode = self.tunnel_mode_combo.currentData()
            
            subnets_text = self.split_subnets_input.toPlainText().strip()
            profile.split_subnets = [s.strip() for s in subnets_text.split("\n") if s.strip()]
            
            # Save
            self._profile_manager.save_profile(profile)
            
            if self._new_profile:
                self._profile_manager.set_current_profile(name)
            
            logger.info(f"Profile saved: {name}")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
