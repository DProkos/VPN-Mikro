"""Connection tab for MikroTik router configuration."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox, QPushButton,
    QGroupBox, QMessageBox, QLabel
)
from PyQt6.QtCore import pyqtSignal


class ConnectionTab(QWidget):
    """MikroTik connection configuration tab.
    
    Provides input fields for host, port, username, password,
    with options to remember credentials and verify TLS.
    
    Signals:
        connection_tested: Emitted when connection test completes (success, message)
        profile_saved: Emitted when profile is saved (profile_name)
    """
    
    connection_tested = pyqtSignal(bool, str)
    profile_saved = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the connection tab UI."""
        layout = QVBoxLayout(self)
        
        # Connection settings group
        conn_group = QGroupBox("MikroTik Connection")
        conn_layout = QFormLayout()
        
        # Host input
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("IP address or domain")
        conn_layout.addRow("Host:", self.host_input)
        
        # Port input (default 8729 for API-SSL)
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(8729)
        conn_layout.addRow("Port:", self.port_input)
        
        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("admin")
        conn_layout.addRow("Username:", self.username_input)
        
        # Password input
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Password")
        conn_layout.addRow("Password:", self.password_input)
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        # Options group
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        
        # Remember credentials checkbox
        self.remember_checkbox = QCheckBox("Remember credentials")
        self.remember_checkbox.setChecked(True)
        options_layout.addWidget(self.remember_checkbox)
        
        # Verify TLS checkbox (default OFF for self-signed MikroTik certs)
        self.verify_tls_checkbox = QCheckBox("Verify TLS certificate")
        self.verify_tls_checkbox.setChecked(False)
        self.verify_tls_checkbox.setToolTip(
            "Enable to verify TLS certificate chain.\n"
            "Default OFF for self-signed MikroTik certificates."
        )
        options_layout.addWidget(self.verify_tls_checkbox)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self._on_test_connection)
        button_layout.addWidget(self.test_button)
        
        self.save_button = QPushButton("Save Profile")
        self.save_button.clicked.connect(self._on_save_profile)
        button_layout.addWidget(self.save_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Add stretch to push everything to top
        layout.addStretch()
    
    def _on_test_connection(self):
        """Handle Test Connection button click."""
        host = self.host_input.text().strip()
        port = self.port_input.value()
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        # Validate inputs
        if not host:
            self._show_error("Please enter a host address.")
            return
        if not username:
            self._show_error("Please enter a username.")
            return
        if not password:
            self._show_error("Please enter a password.")
            return
        
        self.status_label.setText("Testing connection...")
        self.test_button.setEnabled(False)
        
        try:
            from vpnmikro.mikrotik.ros_client import ROSClient
            
            client = ROSClient(host, port, verify_tls=self.verify_tls_checkbox.isChecked())
            client.connect()
            success = client.login(username, password)
            client.disconnect()
            
            if success:
                self.status_label.setText("Connection successful!")
                self.status_label.setStyleSheet("color: green;")
                self.connection_tested.emit(True, "Connection successful")
                QMessageBox.information(self, "Success", "Connection to MikroTik successful!")
            else:
                self.status_label.setText("Authentication failed.")
                self.status_label.setStyleSheet("color: red;")
                self.connection_tested.emit(False, "Authentication failed")
                QMessageBox.warning(self, "Failed", "Invalid username or password.")
                
        except Exception as e:
            error_msg = str(e)
            self.status_label.setText(f"Connection failed: {error_msg}")
            self.status_label.setStyleSheet("color: red;")
            self.connection_tested.emit(False, error_msg)
            QMessageBox.critical(
                self, "Connection Error",
                f"Cannot connect to MikroTik at {host}:{port}\n\n{error_msg}"
            )
        finally:
            self.test_button.setEnabled(True)
    
    def _on_save_profile(self):
        """Handle Save Profile button click."""
        host = self.host_input.text().strip()
        port = self.port_input.value()
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        # Validate inputs
        if not host:
            self._show_error("Please enter a host address.")
            return
        if not username:
            self._show_error("Please enter a username.")
            return
        
        try:
            from vpnmikro.core.profiles import ProfileManager
            from vpnmikro.core.models import Profile
            
            manager = ProfileManager()
            
            # Create profile with host as name
            profile_name = host.replace(".", "-").replace(":", "-")
            
            profile = Profile(
                name=profile_name,
                host=host,
                port=port,
                verify_tls=self.verify_tls_checkbox.isChecked()
            )
            
            # Store credentials if remember is checked
            if self.remember_checkbox.isChecked() and password:
                manager.save_profile(profile, username=username, password=password)
            else:
                manager.save_profile(profile)
            
            self.status_label.setText(f"Profile '{profile_name}' saved.")
            self.status_label.setStyleSheet("color: green;")
            self.profile_saved.emit(profile_name)
            QMessageBox.information(self, "Saved", f"Profile '{profile_name}' saved successfully.")
            
        except Exception as e:
            self._show_error(f"Failed to save profile: {e}")
    
    def _show_error(self, message: str):
        """Show error message."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: red;")
        QMessageBox.warning(self, "Error", message)
    
    def load_profile(self, profile):
        """Load profile data into the form.
        
        Args:
            profile: Profile object to load
        """
        self.host_input.setText(profile.host)
        self.port_input.setValue(profile.port)
        self.verify_tls_checkbox.setChecked(profile.verify_tls)
    
    def get_connection_params(self) -> dict:
        """Get current connection parameters.
        
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
