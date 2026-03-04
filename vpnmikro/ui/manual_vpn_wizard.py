"""Manual VPN Profile Wizard for creating VPN configs without MikroTik.

Provides a step-by-step wizard for users to manually create WireGuard
VPN configurations by entering server details.
"""

from pathlib import Path
from typing import Optional
import uuid
from datetime import datetime

from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QMessageBox, QFormLayout,
    QSpinBox, QCheckBox, QGroupBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from vpnmikro.core.models import Profile, Device
from vpnmikro.core.profiles import ProfileManager
from vpnmikro.core.wg_config import WGConfigBuilder
from vpnmikro.core.logger import get_logger

logger = get_logger(__name__)


class WelcomePage(QWizardPage):
    """Welcome page explaining the wizard."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Create VPN Profile")
        self.setSubTitle("This wizard will help you create a WireGuard VPN configuration.")
        
        layout = QVBoxLayout(self)
        
        info = QLabel(
            "You will need the following information from your VPN provider:\n\n"
            "• Server public key\n"
            "• Server endpoint (IP or hostname)\n"
            "• Server port\n"
            "• Your assigned IP address\n"
            "• Allowed IPs (usually 0.0.0.0/0 for full tunnel)\n\n"
            "Click Next to continue."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()


class ProfileNamePage(QWizardPage):
    """Page for entering profile/device name."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Profile Name")
        self.setSubTitle("Enter a name for this VPN profile.")
        
        layout = QFormLayout(self)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Work VPN, Home Server")
        self.registerField("profile_name*", self.name_edit)
        layout.addRow("Profile Name:", self.name_edit)
        
        hint = QLabel("Use a descriptive name to identify this VPN connection.")
        hint.setObjectName("MutedLabel")
        hint.setWordWrap(True)
        layout.addRow("", hint)


class ServerDetailsPage(QWizardPage):
    """Page for entering server details."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Server Details")
        self.setSubTitle("Enter the VPN server connection details.")
        
        layout = QFormLayout(self)
        
        # Server endpoint
        self.endpoint_edit = QLineEdit()
        self.endpoint_edit.setPlaceholderText("e.g., vpn.example.com or 203.0.113.1")
        self.registerField("server_endpoint*", self.endpoint_edit)
        layout.addRow("Server Address:", self.endpoint_edit)
        
        # Server port
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(51820)
        self.registerField("server_port", self.port_spin)
        layout.addRow("Server Port:", self.port_spin)
        
        # Server public key
        self.pubkey_edit = QLineEdit()
        self.pubkey_edit.setPlaceholderText("Base64 encoded public key")
        self.registerField("server_pubkey*", self.pubkey_edit)
        layout.addRow("Server Public Key:", self.pubkey_edit)


class ClientDetailsPage(QWizardPage):
    """Page for entering client details."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Client Details")
        self.setSubTitle("Enter your client configuration details.")
        
        layout = QFormLayout(self)
        
        # Client IP
        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("e.g., 10.0.0.2/32")
        self.registerField("client_ip*", self.ip_edit)
        layout.addRow("Your IP Address:", self.ip_edit)
        
        # Private key (optional - can generate)
        key_group = QGroupBox("Private Key")
        key_layout = QVBoxLayout(key_group)
        
        self.generate_key_check = QCheckBox("Generate new key pair automatically")
        self.generate_key_check.setChecked(True)
        self.generate_key_check.stateChanged.connect(self._on_generate_changed)
        key_layout.addWidget(self.generate_key_check)
        
        self.privkey_edit = QLineEdit()
        self.privkey_edit.setPlaceholderText("Base64 encoded private key (leave empty to generate)")
        self.privkey_edit.setEnabled(False)
        self.registerField("client_privkey", self.privkey_edit)
        key_layout.addWidget(self.privkey_edit)
        
        layout.addRow(key_group)
        
        # DNS
        self.dns_edit = QLineEdit()
        self.dns_edit.setPlaceholderText("e.g., 1.1.1.1, 8.8.8.8")
        self.dns_edit.setText("1.1.1.1, 8.8.8.8")
        self.registerField("dns_servers", self.dns_edit)
        layout.addRow("DNS Servers:", self.dns_edit)
    
    def _on_generate_changed(self, state):
        self.privkey_edit.setEnabled(state != Qt.CheckState.Checked.value)


class RoutingPage(QWizardPage):
    """Page for configuring routing options."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Routing")
        self.setSubTitle("Configure which traffic goes through the VPN.")
        
        layout = QVBoxLayout(self)
        
        # Full tunnel option
        self.full_tunnel_check = QCheckBox("Route all traffic through VPN (full tunnel)")
        self.full_tunnel_check.setChecked(True)
        self.full_tunnel_check.stateChanged.connect(self._on_full_tunnel_changed)
        layout.addWidget(self.full_tunnel_check)
        
        # Custom allowed IPs
        self.allowed_ips_label = QLabel("Allowed IPs:")
        self.allowed_ips_edit = QLineEdit()
        self.allowed_ips_edit.setPlaceholderText("e.g., 10.0.0.0/8, 192.168.0.0/16")
        self.allowed_ips_edit.setText("0.0.0.0/0, ::/0")
        self.allowed_ips_edit.setEnabled(False)
        self.registerField("allowed_ips", self.allowed_ips_edit)
        
        layout.addWidget(self.allowed_ips_label)
        layout.addWidget(self.allowed_ips_edit)
        
        # Persistent keepalive
        keepalive_layout = QHBoxLayout()
        self.keepalive_check = QCheckBox("Enable persistent keepalive")
        self.keepalive_check.setChecked(True)
        self.keepalive_spin = QSpinBox()
        self.keepalive_spin.setRange(0, 300)
        self.keepalive_spin.setValue(25)
        self.keepalive_spin.setSuffix(" seconds")
        self.registerField("keepalive", self.keepalive_spin)
        
        keepalive_layout.addWidget(self.keepalive_check)
        keepalive_layout.addWidget(self.keepalive_spin)
        keepalive_layout.addStretch()
        layout.addLayout(keepalive_layout)
        
        layout.addStretch()
    
    def _on_full_tunnel_changed(self, state):
        is_full = state == Qt.CheckState.Checked.value
        self.allowed_ips_edit.setEnabled(not is_full)
        if is_full:
            self.allowed_ips_edit.setText("0.0.0.0/0, ::/0")


class SummaryPage(QWizardPage):
    """Summary page showing the configuration."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Summary")
        self.setSubTitle("Review your VPN configuration before creating.")
        
        layout = QVBoxLayout(self)
        
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.summary_text)
    
    def initializePage(self):
        """Generate summary when page is shown."""
        wizard = self.wizard()
        
        name = wizard.field("profile_name")
        endpoint = wizard.field("server_endpoint")
        port = wizard.field("server_port")
        pubkey = wizard.field("server_pubkey")
        client_ip = wizard.field("client_ip")
        dns = wizard.field("dns_servers")
        allowed_ips = wizard.field("allowed_ips")
        keepalive = wizard.field("keepalive")
        
        summary = f"""Profile Name: {name}

[Interface]
Address = {client_ip}
DNS = {dns}
PrivateKey = (will be generated)

[Peer]
PublicKey = {pubkey}
Endpoint = {endpoint}:{port}
AllowedIPs = {allowed_ips}
PersistentKeepalive = {keepalive}
"""
        self.summary_text.setPlainText(summary)


class ManualVPNWizard(QWizard):
    """Wizard for creating VPN profiles manually."""
    
    def __init__(self, profile_manager: ProfileManager, parent=None):
        super().__init__(parent)
        self._profile_manager = profile_manager
        self._created_device: Optional[Device] = None
        
        self.setWindowTitle("Create VPN Profile")
        self.setMinimumSize(500, 400)
        
        # Add pages
        self.addPage(WelcomePage())
        self.addPage(ProfileNamePage())
        self.addPage(ServerDetailsPage())
        self.addPage(ClientDetailsPage())
        self.addPage(RoutingPage())
        self.addPage(SummaryPage())
        
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
    
    def accept(self):
        """Create the VPN profile when wizard is accepted."""
        try:
            self._create_profile()
            super().accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create profile:\n{e}")
    
    def _create_profile(self):
        """Create the profile and device from wizard data."""
        name = self.field("profile_name")
        endpoint = self.field("server_endpoint")
        port = self.field("server_port")
        server_pubkey = self.field("server_pubkey")
        client_ip = self.field("client_ip")
        dns = self.field("dns_servers")
        allowed_ips = self.field("allowed_ips")
        keepalive = self.field("keepalive")
        client_privkey = self.field("client_privkey")
        
        # Generate keys if needed
        if not client_privkey:
            privkey, pubkey = WGConfigBuilder.generate_keypair()
        else:
            privkey = client_privkey
            # Derive public key from private key
            import base64
            from nacl.bindings import crypto_scalarmult_base
            privkey_bytes = base64.b64decode(privkey)
            pubkey_bytes = crypto_scalarmult_base(privkey_bytes)
            pubkey = base64.b64encode(pubkey_bytes).decode("ascii")
        
        # Create or get profile
        profile_name = name.replace(" ", "-").lower()
        
        try:
            profile = self._profile_manager.load_profile(profile_name)
        except:
            # Create new profile (client-only, no MikroTik host)
            profile = Profile(
                name=profile_name,
                host="",  # No MikroTik host
                port=0,
                verify_tls=False,
                devices=[]
            )
        
        # Create device
        device_uuid = str(uuid.uuid4())
        
        # Encrypt private key with DPAPI
        from vpnmikro.core.secure_store import SecureStore
        secure_store = SecureStore()
        private_key_encrypted = secure_store.encrypt(privkey.encode('utf-8'))
        
        device = Device(
            uuid=device_uuid,
            name=name,
            public_key=pubkey,
            private_key_encrypted=private_key_encrypted,
            assigned_ip=client_ip.split("/")[0],
            peer_id="manual",  # Mark as manually created
            config_path="",  # Will be set after saving config
            created_at=datetime.now(),
            enabled=True
        )
        
        # Generate config file
        config_content = self._generate_config(
            privkey, client_ip, dns, server_pubkey, 
            endpoint, port, allowed_ips, keepalive
        )
        
        # Save config file
        from vpnmikro.core.wg_controller_win import WGController
        config_dir = WGController.CONFIG_DIR
        config_dir.mkdir(parents=True, exist_ok=True)
        
        tunnel_name = WGController.make_tunnel_name(name)
        config_path = config_dir / f"{tunnel_name}.conf"
        config_path.write_text(config_content, encoding="utf-8")
        
        device.config_path = str(config_path)
        
        # Add device to profile
        profile.devices.append(device)
        self._profile_manager.save_profile(profile)
        
        self._created_device = device
        logger.info(f"Created manual VPN profile: {name}")
    
    def _generate_config(self, privkey, address, dns, peer_pubkey, 
                         endpoint, port, allowed_ips, keepalive) -> str:
        """Generate WireGuard config content."""
        config = f"""[Interface]
PrivateKey = {privkey}
Address = {address}
DNS = {dns}

[Peer]
PublicKey = {peer_pubkey}
Endpoint = {endpoint}:{port}
AllowedIPs = {allowed_ips}
PersistentKeepalive = {keepalive}
"""
        return config
    
    @property
    def created_device(self) -> Optional[Device]:
        """Get the created device after wizard completes."""
        return self._created_device
