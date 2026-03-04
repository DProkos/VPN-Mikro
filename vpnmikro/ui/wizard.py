"""Setup wizard for first-run configuration.

This module provides a QWizard-based setup wizard that guides users through
initial configuration: MikroTik credentials, WireGuard interface selection,
endpoint configuration, and first device creation.

Also supports Client-only mode for importing existing WireGuard configs.
"""

from pathlib import Path
from datetime import datetime
import uuid

from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox, QComboBox, QPushButton,
    QLabel, QGroupBox, QMessageBox, QProgressBar, QRadioButton,
    QButtonGroup, QFileDialog, QTextEdit
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from vpnmikro.core.models import Profile, WGInterface, Device
from vpnmikro.core.profiles import ProfileManager
from vpnmikro.core.secure_store import SecureStore
from vpnmikro.core.logger import get_logger

logger = get_logger(__name__)


# Page IDs
PAGE_MODE_SELECT = 0
PAGE_CREDENTIALS = 1
PAGE_INTERFACE = 2
PAGE_ENDPOINT = 3
PAGE_FIRST_DEVICE = 4
PAGE_CLIENT_IMPORT = 5


class ModeSelectPage(QWizardPage):
    """Page 0: Mode selection - MikroTik or Client-only.
    
    Allows user to choose between:
    - MikroTik Mode: Full integration with MikroTik router
    - Client Mode: Import existing WireGuard config
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Welcome to VPN Mikro")
        self.setSubTitle("Choose how you want to set up your VPN connection.")
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # MikroTik Mode
        mikrotik_group = QGroupBox()
        mikrotik_layout = QVBoxLayout()
        
        self.radio_mikrotik = QRadioButton("MikroTik Mode (Recommended)")
        self.radio_mikrotik.setChecked(True)
        mikrotik_layout.addWidget(self.radio_mikrotik)
        
        mikrotik_desc = QLabel(
            "Connect to your MikroTik router to automatically manage\n"
            "WireGuard peers and generate client configurations."
        )
        mikrotik_desc.setStyleSheet("color: #9AA4B2; margin-left: 25px;")
        mikrotik_layout.addWidget(mikrotik_desc)
        
        mikrotik_group.setLayout(mikrotik_layout)
        layout.addWidget(mikrotik_group)
        
        # Client Mode
        client_group = QGroupBox()
        client_layout = QVBoxLayout()
        
        self.radio_client = QRadioButton("Client Mode (Import Config)")
        client_layout.addWidget(self.radio_client)
        
        client_desc = QLabel(
            "Import an existing WireGuard configuration file (.conf).\n"
            "Use this if you already have a config from another provider."
        )
        client_desc.setStyleSheet("color: #9AA4B2; margin-left: 25px;")
        client_layout.addWidget(client_desc)
        
        client_group.setLayout(client_layout)
        layout.addWidget(client_group)
        
        # Button group
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_mikrotik, 0)
        self.mode_group.addButton(self.radio_client, 1)
        
        layout.addStretch()
    
    def nextId(self) -> int:
        """Determine next page based on mode selection."""
        if self.radio_client.isChecked():
            return PAGE_CLIENT_IMPORT
        return PAGE_CREDENTIALS
    
    def is_client_mode(self) -> bool:
        """Check if client mode is selected."""
        return self.radio_client.isChecked()


class ClientImportPage(QWizardPage):
    """Page for importing WireGuard config in Client mode."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Import WireGuard Config")
        self.setSubTitle("Select your WireGuard configuration file to import.")
        self._config_valid = False
        self._parsed_config = None
        self._config_content = ""
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # File selection
        file_group = QGroupBox("Configuration File")
        file_layout = QHBoxLayout()
        
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Select a .conf file...")
        self.file_path.setReadOnly(True)
        
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._on_browse)
        
        file_layout.addWidget(self.file_path)
        file_layout.addWidget(self.btn_browse)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Profile name
        name_group = QGroupBox("Profile Name")
        name_layout = QFormLayout()
        
        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText("my-vpn")
        self.profile_name_input.textChanged.connect(self._on_input_changed)
        name_layout.addRow("Name:", self.profile_name_input)
        
        name_group.setLayout(name_layout)
        layout.addWidget(name_group)
        
        # Preview
        preview_group = QGroupBox("Config Preview")
        preview_layout = QVBoxLayout()
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        
        preview_layout.addWidget(self.preview_text)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Parsed info
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        layout.addStretch()
    
    def _on_browse(self):
        """Browse for a .conf file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select WireGuard Config",
            "",
            "WireGuard Config (*.conf);;All Files (*)"
        )
        
        if file_path:
            self.file_path.setText(file_path)
            self._load_config(file_path)
    
    def _on_input_changed(self):
        """Handle input changes."""
        self.completeChanged.emit()
    
    def _load_config(self, file_path: str):
        """Load and parse the config file."""
        try:
            path = Path(file_path)
            content = path.read_text(encoding="utf-8")
            
            self.preview_text.setPlainText(content)
            
            # Parse config
            parsed = self._parse_config(content)
            
            if parsed:
                # Auto-fill name from filename
                if not self.profile_name_input.text():
                    self.profile_name_input.setText(path.stem)
                
                # Show parsed info
                info_parts = []
                if parsed.get("address"):
                    info_parts.append(f"✓ Address: {parsed['address']}")
                if parsed.get("endpoint"):
                    info_parts.append(f"✓ Endpoint: {parsed['endpoint']}")
                if parsed.get("dns"):
                    info_parts.append(f"✓ DNS: {parsed['dns']}")
                
                self.info_label.setText("\n".join(info_parts))
                self.info_label.setStyleSheet("color: #22C55E;")
                self._config_valid = True
                self._parsed_config = parsed
                self._config_content = content
            else:
                self.info_label.setText("⚠️ Could not parse config file - missing PrivateKey")
                self.info_label.setStyleSheet("color: #EAB308;")
                self._config_valid = False
            
            self.completeChanged.emit()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load config: {e}")
            self._config_valid = False
            self.completeChanged.emit()
    
    def _parse_config(self, content: str) -> dict | None:
        """Parse WireGuard config content."""
        result = {
            "private_key": None,
            "address": None,
            "dns": None,
            "mtu": None,
            "public_key": None,
            "endpoint": None,
            "allowed_ips": None,
            "keepalive": None,
        }
        
        current_section = None
        
        for line in content.splitlines():
            line = line.strip()
            
            if not line or line.startswith("#"):
                continue
            
            if line.lower() == "[interface]":
                current_section = "interface"
                continue
            elif line.lower() == "[peer]":
                current_section = "peer"
                continue
            
            if "=" not in line:
                continue
            
            key, _, value = line.partition("=")
            key = key.strip().lower()
            value = value.strip()
            
            if current_section == "interface":
                if key == "privatekey":
                    result["private_key"] = value
                elif key == "address":
                    result["address"] = value.split("/")[0]
                elif key == "dns":
                    result["dns"] = value
                elif key == "mtu":
                    result["mtu"] = int(value)
            
            elif current_section == "peer":
                if key == "publickey":
                    result["public_key"] = value
                elif key == "endpoint":
                    result["endpoint"] = value
                elif key == "allowedips":
                    result["allowed_ips"] = value
                elif key == "persistentkeepalive":
                    result["keepalive"] = int(value)
        
        if not result["private_key"]:
            return None
        
        return result
    
    def isComplete(self) -> bool:
        """Check if page is complete."""
        return (
            self._config_valid and
            bool(self.profile_name_input.text().strip())
        )
    
    def nextId(self) -> int:
        """No next page - this is the final page for client mode."""
        return -1
    
    def get_config_data(self) -> dict:
        """Get the parsed config data."""
        return {
            "profile_name": self.profile_name_input.text().strip(),
            "parsed_config": self._parsed_config,
            "config_content": self._config_content,
        }


class CredentialsPage(QWizardPage):
    """Page 1: MikroTik credentials configuration.
    
    Collects host, port, username, password, and TLS verification settings.
    Validates connection before allowing progression.
    """
    
    connection_tested = pyqtSignal(bool, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("MikroTik Connection")
        self.setSubTitle("Enter your MikroTik router credentials to get started.")
        self._connection_valid = False
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the credentials page UI."""
        layout = QVBoxLayout(self)
        
        # Connection settings
        form_layout = QFormLayout()
        
        # Host input
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("192.168.88.1 or router.example.com")
        self.host_input.textChanged.connect(self._on_input_changed)
        form_layout.addRow("Host:", self.host_input)
        
        # Port input
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(8729)
        self.port_input.setToolTip("API-SSL port (default: 8729)")
        form_layout.addRow("Port:", self.port_input)
        
        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("admin")
        self.username_input.textChanged.connect(self._on_input_changed)
        form_layout.addRow("Username:", self.username_input)
        
        # Password input
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Password")
        self.password_input.textChanged.connect(self._on_input_changed)
        form_layout.addRow("Password:", self.password_input)
        
        layout.addLayout(form_layout)
        
        # TLS verification checkbox
        self.verify_tls_checkbox = QCheckBox("Verify TLS certificate")
        self.verify_tls_checkbox.setChecked(False)
        self.verify_tls_checkbox.setToolTip(
            "Enable to verify TLS certificate chain.\n"
            "Default OFF for self-signed MikroTik certificates."
        )
        layout.addWidget(self.verify_tls_checkbox)
        
        layout.addSpacing(10)
        
        # Test connection button and status
        test_layout = QHBoxLayout()
        
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self._on_test_connection)
        test_layout.addWidget(self.test_button)
        
        self.status_label = QLabel("")
        test_layout.addWidget(self.status_label, stretch=1)
        
        layout.addLayout(test_layout)
        
        # Info label
        info_label = QLabel(
            "💡 You must test the connection before proceeding."
        )
        info_label.setStyleSheet("color: gray; font-style: italic; font-size: 12px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        # Register fields for wizard
        self.registerField("host*", self.host_input)
        self.registerField("port", self.port_input, "value")
        self.registerField("username*", self.username_input)
        self.registerField("password*", self.password_input)
        self.registerField("verify_tls", self.verify_tls_checkbox)
    
    def _on_input_changed(self):
        """Reset connection validation when inputs change."""
        self._connection_valid = False
        self.status_label.setText("")
        self.status_label.setStyleSheet("")
        self.completeChanged.emit()
    
    def _on_test_connection(self):
        """Test connection to MikroTik router."""
        host = self.host_input.text().strip()
        port = self.port_input.value()
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not host or not username or not password:
            QMessageBox.warning(self, "Missing Fields", "Please fill in all fields.")
            return
        
        self.status_label.setText("Testing connection...")
        self.status_label.setStyleSheet("color: orange;")
        self.test_button.setEnabled(False)
        
        # Force UI update
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            from vpnmikro.mikrotik.ros_client import ROSClient
            
            client = ROSClient(host, port, verify_tls=self.verify_tls_checkbox.isChecked())
            client.connect()
            success = client.login(username, password)
            client.disconnect()
            
            if success:
                self._connection_valid = True
                self.status_label.setText("✓ Connection successful!")
                self.status_label.setStyleSheet("color: green;")
                self.connection_tested.emit(True, "Connection successful")
                self.completeChanged.emit()
            else:
                self._connection_valid = False
                self.status_label.setText("✗ Authentication failed")
                self.status_label.setStyleSheet("color: red;")
                self.connection_tested.emit(False, "Authentication failed")
                
        except Exception as e:
            self._connection_valid = False
            error_msg = str(e)
            self.status_label.setText(f"✗ {error_msg[:50]}...")
            self.status_label.setStyleSheet("color: red;")
            self.connection_tested.emit(False, error_msg)
            QMessageBox.critical(
                self, "Connection Error",
                f"Cannot connect to MikroTik at {host}:{port}\n\n{error_msg}"
            )
        finally:
            self.test_button.setEnabled(True)
    
    def isComplete(self) -> bool:
        """Check if page is complete (connection tested successfully)."""
        return (
            self._connection_valid and
            bool(self.host_input.text().strip()) and
            bool(self.username_input.text().strip()) and
            bool(self.password_input.text())
        )
    
    def get_credentials(self) -> dict:
        """Get the entered credentials.
        
        Returns:
            Dictionary with host, port, username, password, verify_tls
        """
        return {
            "host": self.host_input.text().strip(),
            "port": self.port_input.value(),
            "username": self.username_input.text().strip(),
            "password": self.password_input.text(),
            "verify_tls": self.verify_tls_checkbox.isChecked()
        }
    
    def nextId(self) -> int:
        """Go to interface selection page."""
        return PAGE_INTERFACE


class InterfaceSelectPage(QWizardPage):
    """Page 2: WireGuard interface selection.
    
    Fetches and displays available WireGuard interfaces from the router.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("WireGuard Interface")
        self.setSubTitle("Select the WireGuard interface to use for VPN connections.")
        self._interfaces: list[WGInterface] = []
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the interface selection page UI."""
        layout = QVBoxLayout(self)
        
        # Interface dropdown
        form_layout = QFormLayout()
        
        interface_layout = QHBoxLayout()
        self.interface_dropdown = QComboBox()
        self.interface_dropdown.setPlaceholderText("Loading interfaces...")
        self.interface_dropdown.currentIndexChanged.connect(self._on_interface_changed)
        interface_layout.addWidget(self.interface_dropdown, stretch=1)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._fetch_interfaces)
        interface_layout.addWidget(self.refresh_button)
        
        form_layout.addRow("Interface:", interface_layout)
        layout.addLayout(form_layout)
        
        # Interface details
        self.details_group = QGroupBox("Interface Details")
        details_layout = QFormLayout()
        
        self.listen_port_label = QLabel("-")
        details_layout.addRow("Listen Port:", self.listen_port_label)
        
        self.public_key_label = QLabel("-")
        self.public_key_label.setWordWrap(True)
        self.public_key_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addRow("Public Key:", self.public_key_label)
        
        self.details_group.setLayout(details_layout)
        layout.addWidget(self.details_group)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def initializePage(self):
        """Called when page is shown - fetch interfaces."""
        self._fetch_interfaces()
    
    def _fetch_interfaces(self):
        """Fetch WireGuard interfaces from the router."""
        self.status_label.setText("Fetching interfaces...")
        self.status_label.setStyleSheet("color: orange;")
        self.refresh_button.setEnabled(False)
        self.interface_dropdown.clear()
        self.interface_dropdown.setPlaceholderText("Loading...")
        
        # Force UI update
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            # Get credentials from credentials page
            wizard = self.wizard()
            creds_page = wizard.page(PAGE_CREDENTIALS)
            creds = creds_page.get_credentials()
            
            from vpnmikro.mikrotik.ros_client import ROSClient
            from vpnmikro.mikrotik.wg_manager import WGPeerManager
            
            client = ROSClient(
                creds["host"],
                creds["port"],
                verify_tls=creds["verify_tls"]
            )
            client.connect()
            client.login(creds["username"], creds["password"])
            
            peer_manager = WGPeerManager(client)
            self._interfaces = peer_manager.list_interfaces()
            
            client.disconnect()
            
            if not self._interfaces:
                self.status_label.setText("No WireGuard interfaces found on router.")
                self.status_label.setStyleSheet("color: red;")
                self.interface_dropdown.setPlaceholderText("No interfaces found")
                return
            
            # Populate dropdown
            self.interface_dropdown.setPlaceholderText("")
            for iface in self._interfaces:
                self.interface_dropdown.addItem(
                    f"{iface.name} (:{iface.listen_port})"
                )
            
            self.status_label.setText(f"Found {len(self._interfaces)} interface(s)")
            self.status_label.setStyleSheet("color: green;")
            
            # Select first interface
            if self._interfaces:
                self.interface_dropdown.setCurrentIndex(0)
                self._on_interface_changed(0)
            
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)[:50]}...")
            self.status_label.setStyleSheet("color: red;")
            self.interface_dropdown.setPlaceholderText("Error loading")
            logger.error(f"Failed to fetch interfaces: {e}")
        finally:
            self.refresh_button.setEnabled(True)
            self.completeChanged.emit()
    
    def _on_interface_changed(self, index: int):
        """Update details when interface selection changes."""
        if index < 0 or index >= len(self._interfaces):
            self.listen_port_label.setText("-")
            self.public_key_label.setText("-")
            return
        
        iface = self._interfaces[index]
        self.listen_port_label.setText(str(iface.listen_port))
        self.public_key_label.setText(iface.public_key)
        self.completeChanged.emit()
    
    def isComplete(self) -> bool:
        """Check if an interface is selected."""
        return (
            len(self._interfaces) > 0 and
            self.interface_dropdown.currentIndex() >= 0
        )
    
    def get_selected_interface(self) -> WGInterface | None:
        """Get the selected WireGuard interface.
        
        Returns:
            Selected WGInterface or None
        """
        index = self.interface_dropdown.currentIndex()
        if 0 <= index < len(self._interfaces):
            return self._interfaces[index]
        return None
    
    def nextId(self) -> int:
        """Go to endpoint configuration page."""
        return PAGE_ENDPOINT


class EndpointPage(QWizardPage):
    """Page 3: Endpoint and server public key configuration.
    
    Configures the public endpoint and server public key for client configs.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Server Configuration")
        self.setSubTitle("Configure the public endpoint and server public key.")
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the endpoint page UI."""
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        # Endpoint input
        endpoint_layout = QHBoxLayout()
        self.endpoint_input = QLineEdit()
        self.endpoint_input.setPlaceholderText("vpn.example.com:51820 or IP:port")
        self.endpoint_input.textChanged.connect(self.completeChanged)
        endpoint_layout.addWidget(self.endpoint_input, stretch=1)
        
        self.autofill_button = QPushButton("Auto-fill Port")
        self.autofill_button.setToolTip("Fill port from selected WireGuard interface")
        self.autofill_button.clicked.connect(self._on_autofill_port)
        endpoint_layout.addWidget(self.autofill_button)
        
        form_layout.addRow("Public Endpoint:", endpoint_layout)
        
        # Server public key input
        self.server_pubkey_input = QLineEdit()
        self.server_pubkey_input.setPlaceholderText("Base64 encoded public key")
        self.server_pubkey_input.textChanged.connect(self.completeChanged)
        form_layout.addRow("Server Public Key:", self.server_pubkey_input)
        
        layout.addLayout(form_layout)
        
        # Auto-fill public key button
        autofill_key_layout = QHBoxLayout()
        self.autofill_key_button = QPushButton("Auto-fill from Interface")
        self.autofill_key_button.setToolTip("Use the public key from the selected WireGuard interface")
        self.autofill_key_button.clicked.connect(self._on_autofill_pubkey)
        autofill_key_layout.addWidget(self.autofill_key_button)
        autofill_key_layout.addStretch()
        layout.addLayout(autofill_key_layout)
        
        layout.addSpacing(20)
        
        # Help text
        help_group = QGroupBox("Help")
        help_layout = QVBoxLayout()
        
        help_text = QLabel(
            "<b>Public Endpoint:</b> The address clients will use to connect. "
            "This should be your router's public IP or domain name, followed by "
            "the WireGuard listen port.<br><br>"
            "<b>Server Public Key:</b> The WireGuard interface's public key. "
            "Click 'Auto-fill from Interface' to use the key from the selected interface."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: gray;")
        help_layout.addWidget(help_text)
        
        help_group.setLayout(help_layout)
        layout.addWidget(help_group)
        
        layout.addStretch()
        
        # Register fields
        self.registerField("endpoint*", self.endpoint_input)
        self.registerField("server_pubkey*", self.server_pubkey_input)
    
    def initializePage(self):
        """Called when page is shown - auto-fill public key if available."""
        wizard = self.wizard()
        interface_page = wizard.page(PAGE_INTERFACE)
        iface = interface_page.get_selected_interface()
        
        if iface:
            # Auto-fill public key
            if not self.server_pubkey_input.text():
                self.server_pubkey_input.setText(iface.public_key)
            
            # Set placeholder with port
            self.endpoint_input.setPlaceholderText(
                f"vpn.example.com:{iface.listen_port}"
            )
    
    def _on_autofill_port(self):
        """Auto-fill endpoint port from selected interface."""
        wizard = self.wizard()
        interface_page = wizard.page(PAGE_INTERFACE)
        iface = interface_page.get_selected_interface()
        
        if not iface:
            QMessageBox.warning(self, "Warning", "No interface selected.")
            return
        
        current = self.endpoint_input.text().strip()
        if ":" in current:
            # Replace existing port
            host = current.rsplit(":", 1)[0]
            self.endpoint_input.setText(f"{host}:{iface.listen_port}")
        elif current:
            # Add port
            self.endpoint_input.setText(f"{current}:{iface.listen_port}")
        else:
            # Just show in placeholder
            self.endpoint_input.setPlaceholderText(f"vpn.example.com:{iface.listen_port}")
    
    def _on_autofill_pubkey(self):
        """Auto-fill server public key from selected interface."""
        wizard = self.wizard()
        interface_page = wizard.page(PAGE_INTERFACE)
        iface = interface_page.get_selected_interface()
        
        if not iface:
            QMessageBox.warning(self, "Warning", "No interface selected.")
            return
        
        self.server_pubkey_input.setText(iface.public_key)
    
    def isComplete(self) -> bool:
        """Check if endpoint and public key are provided."""
        endpoint = self.endpoint_input.text().strip()
        pubkey = self.server_pubkey_input.text().strip()
        
        # Validate endpoint has port
        if endpoint and ":" not in endpoint:
            return False
        
        return bool(endpoint) and bool(pubkey)
    
    def get_server_settings(self) -> dict:
        """Get the server configuration.
        
        Returns:
            Dictionary with endpoint and server_public_key
        """
        return {
            "endpoint": self.endpoint_input.text().strip(),
            "server_public_key": self.server_pubkey_input.text().strip()
        }
    
    def nextId(self) -> int:
        """Go to first device creation page."""
        return PAGE_FIRST_DEVICE


class FirstDevicePage(QWizardPage):
    """Page 4: Create first device.
    
    Creates the first VPN device to complete the setup.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Create First Device")
        self.setSubTitle("Create your first VPN device to complete the setup.")
        self._device_created = False
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the first device page UI."""
        layout = QVBoxLayout(self)
        
        # Device name input
        form_layout = QFormLayout()
        
        self.device_name_input = QLineEdit()
        self.device_name_input.setPlaceholderText("my-laptop")
        self.device_name_input.setText("my-device")
        self.device_name_input.textChanged.connect(self._on_name_changed)
        form_layout.addRow("Device Name:", self.device_name_input)
        
        layout.addLayout(form_layout)
        
        # Name validation hint
        self.name_hint_label = QLabel(
            "Use letters, numbers, hyphens, and underscores only."
        )
        self.name_hint_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.name_hint_label)
        
        layout.addSpacing(20)
        
        # Create device button
        create_layout = QHBoxLayout()
        
        self.create_button = QPushButton("Create Device")
        self.create_button.clicked.connect(self._on_create_device)
        create_layout.addWidget(self.create_button)
        
        self.status_label = QLabel("")
        create_layout.addWidget(self.status_label, stretch=1)
        
        layout.addLayout(create_layout)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        layout.addSpacing(20)
        
        # Summary (shown after creation)
        self.summary_group = QGroupBox("Device Created")
        self.summary_group.hide()
        summary_layout = QFormLayout()
        
        self.summary_name_label = QLabel("-")
        summary_layout.addRow("Name:", self.summary_name_label)
        
        self.summary_ip_label = QLabel("-")
        summary_layout.addRow("Assigned IP:", self.summary_ip_label)
        
        self.summary_config_label = QLabel("-")
        self.summary_config_label.setWordWrap(True)
        summary_layout.addRow("Config File:", self.summary_config_label)
        
        self.summary_group.setLayout(summary_layout)
        layout.addWidget(self.summary_group)
        
        layout.addStretch()
    
    def _on_name_changed(self):
        """Validate device name as user types."""
        name = self.device_name_input.text().strip()
        
        if not name:
            self.name_hint_label.setText("Device name is required.")
            self.name_hint_label.setStyleSheet("color: red;")
            return
        
        # Check for valid characters
        if not all(c.isalnum() or c in "-_" for c in name):
            self.name_hint_label.setText("Invalid characters. Use letters, numbers, hyphens, underscores.")
            self.name_hint_label.setStyleSheet("color: red;")
            return
        
        self.name_hint_label.setText("✓ Valid name")
        self.name_hint_label.setStyleSheet("color: green;")
    
    def _on_create_device(self):
        """Create the first device."""
        name = self.device_name_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a device name.")
            return
        
        if not all(c.isalnum() or c in "-_" for c in name):
            QMessageBox.warning(
                self, "Error",
                "Device name can only contain letters, numbers, hyphens, and underscores."
            )
            return
        
        self.create_button.setEnabled(False)
        self.device_name_input.setEnabled(False)
        self.progress_bar.show()
        self.status_label.setText("Creating device...")
        self.status_label.setStyleSheet("color: orange;")
        
        # Force UI update
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            wizard = self.wizard()
            
            # Get all configuration from previous pages
            creds_page = wizard.page(PAGE_CREDENTIALS)
            interface_page = wizard.page(PAGE_INTERFACE)
            endpoint_page = wizard.page(PAGE_ENDPOINT)
            
            creds = creds_page.get_credentials()
            iface = interface_page.get_selected_interface()
            server_settings = endpoint_page.get_server_settings()
            
            if not iface:
                raise ValueError("No WireGuard interface selected")
            
            # Create profile
            profile_manager = ProfileManager()
            profile_name = creds["host"].replace(".", "-").replace(":", "-")
            
            profile = profile_manager.create_profile(
                name=profile_name,
                host=creds["host"],
                username=creds["username"],
                password=creds["password"],
                port=creds["port"],
                verify_tls=creds["verify_tls"],
                selected_interface=iface.name,
                endpoint=server_settings["endpoint"],
                server_public_key=server_settings["server_public_key"],
            )
            
            # Save profile first
            profile_manager.save_profile(profile)
            profile_manager.set_current_profile(profile_name)
            
            # Connect to router and create device
            from vpnmikro.mikrotik.ros_client import ROSClient
            from vpnmikro.mikrotik.wg_manager import WGPeerManager
            from vpnmikro.core.device_manager import DeviceManager
            
            client = ROSClient(
                creds["host"],
                creds["port"],
                verify_tls=creds["verify_tls"]
            )
            client.connect()
            client.login(creds["username"], creds["password"])
            
            peer_manager = WGPeerManager(client)
            device_manager = DeviceManager(profile_manager, peer_manager)
            
            # Reload profile to get the saved version
            profile = profile_manager.load_profile(profile_name)
            
            # Create device
            device = device_manager.create_device(profile, name)
            
            client.disconnect()
            
            # Show success
            self._device_created = True
            self.progress_bar.hide()
            self.status_label.setText("✓ Device created successfully!")
            self.status_label.setStyleSheet("color: green;")
            
            # Show summary
            self.summary_name_label.setText(device.name)
            self.summary_ip_label.setText(device.assigned_ip)
            self.summary_config_label.setText(device.config_path)
            self.summary_group.show()
            
            # Store profile name for wizard completion
            wizard.created_profile_name = profile_name
            wizard.created_device = device
            
            self.completeChanged.emit()
            
            logger.info(f"First device created: {device.name} ({device.assigned_ip})")
            
        except Exception as e:
            self.progress_bar.hide()
            self.create_button.setEnabled(True)
            self.device_name_input.setEnabled(True)
            self.status_label.setText(f"✗ Failed: {str(e)[:40]}...")
            self.status_label.setStyleSheet("color: red;")
            
            QMessageBox.critical(
                self, "Device Creation Failed",
                f"Failed to create device:\n\n{str(e)}"
            )
            logger.error(f"Failed to create first device: {e}")
    
    def isComplete(self) -> bool:
        """Check if device has been created."""
        return self._device_created
    
    def nextId(self) -> int:
        """No next page - this is the final page for MikroTik mode."""
        return -1


class SetupWizard(QWizard):
    """First-run setup wizard for VPN Mikro.
    
    Guides users through initial configuration:
    - Mode selection (MikroTik or Client)
    - MikroTik Mode: credentials, interface, endpoint, first device
    - Client Mode: import existing config
    
    Signals:
        setup_completed: Emitted when wizard completes successfully (profile_name)
    """
    
    setup_completed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VPN Mikro Setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(600, 500)
        
        # Set window icon
        from vpnmikro.ui.assets import get_window_icon
        self.setWindowIcon(get_window_icon())
        
        # Store created profile/device for later access
        self.created_profile_name: str | None = None
        self.created_device = None
        
        self._setup_pages()
        
        # Connect finish signal
        self.finished.connect(self._on_finished)
    
    def _setup_pages(self):
        """Add wizard pages."""
        # Page 0: Mode selection
        self.mode_page = ModeSelectPage(self)
        self.setPage(PAGE_MODE_SELECT, self.mode_page)
        
        # Page 1: Credentials (MikroTik mode)
        self.credentials_page = CredentialsPage(self)
        self.setPage(PAGE_CREDENTIALS, self.credentials_page)
        
        # Page 2: Interface selection (MikroTik mode)
        self.interface_page = InterfaceSelectPage(self)
        self.setPage(PAGE_INTERFACE, self.interface_page)
        
        # Page 3: Endpoint configuration (MikroTik mode)
        self.endpoint_page = EndpointPage(self)
        self.setPage(PAGE_ENDPOINT, self.endpoint_page)
        
        # Page 4: First device (MikroTik mode)
        self.first_device_page = FirstDevicePage(self)
        self.setPage(PAGE_FIRST_DEVICE, self.first_device_page)
        
        # Page 5: Client import (Client mode)
        self.client_import_page = ClientImportPage(self)
        self.setPage(PAGE_CLIENT_IMPORT, self.client_import_page)
    
    def _on_finished(self, result: int):
        """Handle wizard completion."""
        if result == QWizard.DialogCode.Accepted:
            # Check if client mode
            if self.mode_page.is_client_mode():
                self._finish_client_mode()
            elif self.created_profile_name:
                logger.info(f"Setup wizard completed. Profile: {self.created_profile_name}")
                self.setup_completed.emit(self.created_profile_name)
        else:
            logger.info("Setup wizard cancelled")
    
    def _finish_client_mode(self):
        """Complete setup for client mode - create profile from imported config."""
        try:
            config_data = self.client_import_page.get_config_data()
            profile_name = config_data["profile_name"]
            parsed = config_data["parsed_config"]
            content = config_data["config_content"]
            
            # Create profile
            profile_manager = ProfileManager()
            secure_store = SecureStore()
            
            profile = Profile(
                name=profile_name,
                host="",  # No MikroTik host
                port=0,
                username_encrypted=b"",
                password_encrypted=b"",
                verify_tls=False,
                selected_interface=None,
                endpoint=parsed.get("endpoint", ""),
                server_public_key=parsed.get("public_key", ""),
                ip_pool="",
                dns=parsed.get("dns"),
                mtu=parsed.get("mtu"),
                keepalive=parsed.get("keepalive", 20),
                tunnel_mode="full",
                split_subnets=[],
                devices=[],
            )
            
            # Copy config to our config directory
            from vpnmikro.core.wg_controller_win import WGController
            
            config_dir = Path("C:/ProgramData/VPNMikro/configs")
            config_dir.mkdir(parents=True, exist_ok=True)
            
            tunnel_name = WGController.make_tunnel_name(profile_name)
            config_path = config_dir / f"{tunnel_name}.conf"
            config_path.write_text(content, encoding="utf-8")
            
            # Create device
            device = Device(
                uuid=str(uuid.uuid4()),
                name=profile_name,
                assigned_ip=parsed.get("address", "unknown"),
                peer_id="imported",
                private_key_encrypted=secure_store.encrypt_string(parsed["private_key"]),
                public_key="",
                config_path=str(config_path),
                created_at=datetime.now(),
                enabled=True,
                pending_delete=False,
            )
            
            profile.devices.append(device)
            
            # Save profile
            profile_manager.save_profile(profile)
            profile_manager.set_current_profile(profile_name)
            
            self.created_profile_name = profile_name
            self.created_device = device
            
            logger.info(f"Client mode setup completed. Profile: {profile_name}")
            self.setup_completed.emit(profile_name)
            
        except Exception as e:
            logger.error(f"Failed to complete client mode setup: {e}")
            QMessageBox.critical(
                self, "Setup Failed",
                f"Failed to create profile:\n\n{str(e)}"
            )


def check_first_run() -> bool:
    """Check if this is the first run (no profiles exist).
    
    Returns:
        True if no profiles exist, False otherwise.
    """
    try:
        profile_manager = ProfileManager()
        profiles = profile_manager.list_profiles()
        return len(profiles) == 0
    except Exception as e:
        logger.warning(f"Error checking for profiles: {e}")
        return True
