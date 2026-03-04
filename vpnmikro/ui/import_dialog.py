"""Import WireGuard configuration dialog.

Allows importing existing WireGuard .conf files to create standalone devices
without requiring a MikroTik connection.
"""

from pathlib import Path
from typing import Optional
import uuid
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QFileDialog, QMessageBox, QGroupBox,
    QFormLayout
)
from PyQt6.QtCore import Qt

from vpnmikro.core.models import Device, Profile
from vpnmikro.core.profiles import ProfileManager
from vpnmikro.core.secure_store import SecureStore
from vpnmikro.core.wg_controller_win import WGController
from vpnmikro.core.logger import get_logger
from vpnmikro.ui.assets import get_window_icon, load_theme

logger = get_logger(__name__)


class ImportConfigDialog(QDialog):
    """Dialog for importing WireGuard configuration files."""
    
    def __init__(self, profile: Profile, profile_manager: ProfileManager, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.profile_manager = profile_manager
        self.secure_store = SecureStore()
        self.imported_device: Optional[Device] = None
        
        self.setWindowTitle("Import WireGuard Config")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setWindowIcon(get_window_icon())
        self.setStyleSheet(load_theme())
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Instructions
        info = QLabel(
            "Import an existing WireGuard configuration file (.conf).\n"
            "This creates a standalone device that can connect without MikroTik."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
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
        
        # Device name
        name_group = QGroupBox("Device Name")
        name_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("my-imported-vpn")
        name_layout.addRow("Name:", self.name_input)
        
        name_group.setLayout(name_layout)
        layout.addWidget(name_group)
        
        # Preview
        preview_group = QGroupBox("Config Preview")
        preview_layout = QVBoxLayout()
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Config content will appear here...")
        
        preview_layout.addWidget(self.preview_text)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Parsed info
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_import = QPushButton("Import")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self._on_import)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_import)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
    
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
                if not self.name_input.text():
                    self.name_input.setText(path.stem)
                
                # Show parsed info
                info_parts = []
                if parsed.get("address"):
                    info_parts.append(f"Address: {parsed['address']}")
                if parsed.get("endpoint"):
                    info_parts.append(f"Endpoint: {parsed['endpoint']}")
                if parsed.get("dns"):
                    info_parts.append(f"DNS: {parsed['dns']}")
                
                self.info_label.setText("\n".join(info_parts))
                self.btn_import.setEnabled(True)
                self._parsed_config = parsed
                self._config_content = content
            else:
                self.info_label.setText("⚠️ Could not parse config file")
                self.btn_import.setEnabled(False)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load config: {e}")
            self.btn_import.setEnabled(False)
    
    def _parse_config(self, content: str) -> Optional[dict]:
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
                    # Remove /32 or /24 suffix for display
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
        
        # Validate required fields
        if not result["private_key"]:
            return None
        
        return result
    
    def _on_import(self):
        """Import the config and create a device."""
        name = self.name_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Name Required", "Please enter a device name.")
            return
        
        # Validate name
        if not all(c.isalnum() or c in "-_" for c in name):
            QMessageBox.warning(
                self, "Invalid Name",
                "Use only letters, numbers, hyphens, and underscores."
            )
            return
        
        # Check for duplicate name in current profile
        for device in self.profile.devices:
            if device.name.lower() == name.lower():
                QMessageBox.warning(
                    self, "Duplicate Name",
                    f"A device named '{name}' already exists in this profile."
                )
                return
        
        # Check for duplicate name across ALL profiles
        all_profiles = self.profile_manager.list_profiles()
        for profile_name in all_profiles:
            if profile_name == self.profile.name:
                continue  # Already checked above
            try:
                other_profile = self.profile_manager.load_profile(profile_name)
                for device in other_profile.devices:
                    if device.name.lower() == name.lower():
                        QMessageBox.warning(
                            self, "Duplicate Name",
                            f"A device named '{name}' already exists in profile '{profile_name}'.\n\n"
                            "Device names must be unique across all profiles."
                        )
                        return
            except Exception:
                pass  # Skip profiles that fail to load
        
        try:
            # Copy config to our config directory
            config_dir = Path("C:/ProgramData/VPNMikro/configs")
            config_dir.mkdir(parents=True, exist_ok=True)
            
            tunnel_name = WGController.make_tunnel_name(name)
            config_path = config_dir / f"{tunnel_name}.conf"
            
            # Write config
            config_path.write_text(self._config_content, encoding="utf-8")
            
            # Create device
            device = Device(
                uuid=str(uuid.uuid4()),
                name=name,
                assigned_ip=self._parsed_config.get("address") or "unknown",
                peer_id="imported",  # No MikroTik peer ID
                private_key_encrypted=self.secure_store.encrypt_string(
                    self._parsed_config["private_key"]
                ),
                public_key=self._parsed_config.get("public_key") or "",  # Server's public key
                config_path=str(config_path),
                created_at=datetime.now(),
                enabled=True,
                pending_delete=False,
            )
            
            # Add to profile and save
            self.profile.devices.append(device)
            self.profile_manager.save_profile(self.profile)
            
            self.imported_device = device
            
            logger.info(f"Imported device: {name} from config")
            
            QMessageBox.information(
                self, "Success",
                f"Device '{name}' imported successfully!\n"
                f"IP: {device.assigned_ip}"
            )
            
            self.accept()
            
        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            QMessageBox.critical(self, "Error", f"Failed to import: {e}")
