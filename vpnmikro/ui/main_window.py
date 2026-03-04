"""Main application window with tab-based interface."""

import sys
import os
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QStatusBar,
    QSystemTrayIcon, QMenu, QWidget, QVBoxLayout, QMessageBox
)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt, QTimer

from vpnmikro.core.profiles import ProfileManager
from vpnmikro.core.device_manager import DeviceManager, AdminRightsError
from vpnmikro.core.models import Profile
from vpnmikro.core.logger import get_logger
from vpnmikro.mikrotik.ros_client import ROSClient
from vpnmikro.mikrotik.wg_manager import WGPeerManager

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Main application window with tabbed interface.
    
    Provides 4 tabs: Connection, VPN Servers, Devices, Advanced.
    Includes system tray icon and status bar for connection state.
    Wires UI components to backend services.
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VPN Mikro")
        self.setMinimumSize(800, 600)
        
        # Backend services
        self._profile_manager = ProfileManager()
        self._current_profile: Optional[Profile] = None
        self._ros_client: Optional[ROSClient] = None
        self._peer_manager: Optional[WGPeerManager] = None
        self._device_manager: Optional[DeviceManager] = None
        
        self._setup_ui()
        self._setup_tray_icon()
        self._setup_status_bar()
        self._wire_signals()
        self._load_current_profile()
    
    def _setup_ui(self):
        """Set up the main UI with tab widget."""
        # Central widget with tab structure
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        # Import tabs
        from vpnmikro.ui.connection_tab import ConnectionTab
        from vpnmikro.ui.vpn_servers_tab import VPNServersTab
        from vpnmikro.ui.devices_tab import DevicesTab
        from vpnmikro.ui.advanced_tab import AdvancedTab
        
        # Create tab instances
        self.connection_tab = ConnectionTab()
        self.vpn_servers_tab = VPNServersTab()
        self.devices_tab = DevicesTab()
        self.advanced_tab = AdvancedTab()
        
        # Add tabs to widget
        self.tab_widget.addTab(self.connection_tab, "Connection")
        self.tab_widget.addTab(self.vpn_servers_tab, "VPN Servers")
        self.tab_widget.addTab(self.devices_tab, "Devices")
        self.tab_widget.addTab(self.advanced_tab, "Advanced")
        
        # Set up menu bar with Help menu
        self._setup_menu_bar()
    
    def _setup_menu_bar(self):
        """Set up the menu bar with Help menu."""
        menu_bar = self.menuBar()
        
        # Help menu
        help_menu = menu_bar.addMenu("Help")
        
        about_action = QAction("About VPN Mikro", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)
    
    def _show_about_dialog(self):
        """Show the About dialog."""
        from vpnmikro.ui.about_dialog import AboutDialog
        dialog = AboutDialog(self)
        dialog.exec()
    
    def _setup_tray_icon(self):
        """Set up system tray icon with context menu."""
        self.tray_icon = QSystemTrayIcon(self)
        
        # Try to load logo from logo folder
        logo_path = Path(__file__).parent.parent.parent / "logo" / "logo.svg"
        if logo_path.exists():
            self.tray_icon.setIcon(QIcon(str(logo_path)))
        else:
            # Fallback to application icon
            self.tray_icon.setIcon(self.style().standardIcon(
                self.style().StandardPixmap.SP_ComputerIcon
            ))
        
        # Create tray menu
        tray_menu = QMenu()
        
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        hide_action = QAction("Hide", self)
        hide_action.triggered.connect(self.hide)
        tray_menu.addAction(hide_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
    
    def _setup_status_bar(self):
        """Set up status bar for connection state display."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_connection_status("Disconnected")
    
    def _wire_signals(self):
        """Wire UI signals to backend handlers."""
        # ConnectionTab signals
        self.connection_tab.connection_tested.connect(self._on_connection_tested)
        self.connection_tab.profile_saved.connect(self._on_profile_saved)
        
        # VPNServersTab signals
        self.vpn_servers_tab.settings_saved.connect(self._on_vpn_settings_saved)
        
        # DevicesTab signals
        self.devices_tab.device_added.connect(self._on_device_add_requested)
        self.devices_tab.device_connected.connect(self._on_device_connect_requested)
        self.devices_tab.device_disconnected.connect(self._on_device_disconnect_requested)
        self.devices_tab.device_deleted.connect(self._on_device_delete_requested)
        
        # AdvancedTab signals
        self.advanced_tab.settings_changed.connect(self._on_advanced_settings_changed)
    
    def _load_current_profile(self):
        """Load the current profile and populate UI."""
        try:
            self._current_profile = self._profile_manager.get_current_profile()
            if self._current_profile:
                logger.info(f"Loaded current profile: {self._current_profile.name}")
                self._populate_ui_from_profile()
        except Exception as e:
            logger.warning(f"Could not load current profile: {e}")
    
    def _populate_ui_from_profile(self):
        """Populate all UI tabs from the current profile."""
        if not self._current_profile:
            return
        
        # Load connection tab
        self.connection_tab.load_profile(self._current_profile)
        
        # Load credentials into connection tab if available
        try:
            username, password = self._profile_manager.decrypt_credentials(self._current_profile)
            if username:
                self.connection_tab.username_input.setText(username)
            if password:
                self.connection_tab.password_input.setText(password)
        except Exception as e:
            logger.warning(f"Could not decrypt credentials: {e}")
        
        # Load advanced settings
        self.advanced_tab.load_settings(self._current_profile)
        
        # Load VPN server settings (need to connect first to get interfaces)
        self.vpn_servers_tab.load_settings(self._current_profile)
        
        # Load devices
        self.devices_tab.set_devices(self._current_profile.devices)
    
    def _ensure_connection(self) -> bool:
        """Ensure we have an active connection to MikroTik.
        
        Returns:
            True if connected, False otherwise.
        """
        if self._ros_client and self._ros_client.is_connected:
            return True
        
        if not self._current_profile:
            QMessageBox.warning(
                self, "Not Connected",
                "Please configure and test MikroTik connection first."
            )
            self.tab_widget.setCurrentWidget(self.connection_tab)
            return False
        
        # Try to connect using stored credentials
        try:
            username, password = self._profile_manager.decrypt_credentials(self._current_profile)
            if not username or not password:
                QMessageBox.warning(
                    self, "Credentials Required",
                    "Please enter credentials and test connection."
                )
                self.tab_widget.setCurrentWidget(self.connection_tab)
                return False
            
            self._ros_client = ROSClient(
                self._current_profile.host,
                self._current_profile.port,
                verify_tls=self._current_profile.verify_tls
            )
            self._ros_client.connect()
            self._ros_client.login(username, password)
            
            self._peer_manager = WGPeerManager(self._ros_client)
            self._device_manager = DeviceManager(self._profile_manager, self._peer_manager)
            
            self.update_connection_status(f"Connected to {self._current_profile.host}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            QMessageBox.critical(
                self, "Connection Failed",
                f"Could not connect to MikroTik:\n{e}"
            )
            return False
    
    def _on_connection_tested(self, success: bool, message: str):
        """Handle connection test result."""
        if success:
            self.update_connection_status(f"Connected to {self.connection_tab.host_input.text()}")
            # Establish persistent connection
            params = self.connection_tab.get_connection_params()
            try:
                self._ros_client = ROSClient(
                    params["host"],
                    params["port"],
                    verify_tls=params["verify_tls"]
                )
                self._ros_client.connect()
                self._ros_client.login(params["username"], params["password"])
                
                self._peer_manager = WGPeerManager(self._ros_client)
                self._device_manager = DeviceManager(self._profile_manager, self._peer_manager)
                
                # Fetch and populate interfaces
                self._refresh_interfaces()
                
            except Exception as e:
                logger.error(f"Failed to establish persistent connection: {e}")
        else:
            self.update_connection_status("Disconnected")
    
    def _on_profile_saved(self, profile_name: str):
        """Handle profile saved event."""
        logger.info(f"Profile saved: {profile_name}")
        try:
            self._current_profile = self._profile_manager.load_profile(profile_name)
            self._profile_manager.set_current_profile(profile_name)
            self._populate_ui_from_profile()
        except Exception as e:
            logger.error(f"Failed to load saved profile: {e}")
    
    def _on_vpn_settings_saved(self):
        """Handle VPN server settings saved."""
        if not self._current_profile:
            return
        
        settings = self.vpn_servers_tab.get_settings()
        self._current_profile.selected_interface = settings["selected_interface"]
        self._current_profile.endpoint = settings["endpoint"]
        self._current_profile.server_public_key = settings["server_public_key"]
        
        try:
            self._profile_manager.save_profile(self._current_profile)
            logger.info("VPN server settings saved")
        except Exception as e:
            logger.error(f"Failed to save VPN settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")
    
    def _on_device_add_requested(self, device_name: str):
        """Handle device add request."""
        if not self._ensure_connection():
            self.devices_tab.status_label.setText("Connection required")
            self.devices_tab.status_label.setStyleSheet("color: red;")
            return
        
        if not self._current_profile:
            QMessageBox.warning(self, "Error", "No profile loaded.")
            return
        
        if not self._current_profile.selected_interface:
            QMessageBox.warning(
                self, "Configuration Required",
                "Please select a WireGuard interface in the VPN Servers tab first."
            )
            self.tab_widget.setCurrentWidget(self.vpn_servers_tab)
            return
        
        if not self._current_profile.endpoint or not self._current_profile.server_public_key:
            QMessageBox.warning(
                self, "Configuration Required",
                "Please configure endpoint and server public key in the VPN Servers tab."
            )
            self.tab_widget.setCurrentWidget(self.vpn_servers_tab)
            return
        
        try:
            # Apply advanced settings to profile before creating device
            advanced = self.advanced_tab.get_settings()
            self._current_profile.ip_pool = advanced["ip_pool"]
            self._current_profile.dns = advanced["dns"]
            self._current_profile.mtu = advanced["mtu"]
            self._current_profile.keepalive = advanced["keepalive"]
            self._current_profile.tunnel_mode = advanced["tunnel_mode"]
            self._current_profile.split_subnets = advanced["split_subnets"]
            
            device = self._device_manager.create_device(self._current_profile, device_name)
            self.devices_tab.add_device_to_table(device)
            
            QMessageBox.information(
                self, "Device Created",
                f"Device '{device.name}' created successfully.\n"
                f"Assigned IP: {device.assigned_ip}"
            )
            
        except Exception as e:
            logger.error(f"Failed to create device: {e}")
            self.devices_tab.status_label.setText(f"Failed: {str(e)[:40]}...")
            self.devices_tab.status_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Device Creation Failed", str(e))
    
    def _on_device_connect_requested(self, device_uuid: str):
        """Handle device connect request."""
        if not self._current_profile:
            return
        
        # Device manager doesn't need MikroTik connection for connect/disconnect
        if not self._device_manager:
            self._device_manager = DeviceManager(self._profile_manager)
        
        try:
            self._device_manager.connect_device(self._current_profile, device_uuid)
            self.devices_tab.update_device_status(device_uuid, connected=True)
            self.devices_tab.status_label.setText("Connected")
            self.devices_tab.status_label.setStyleSheet("color: green;")
            self.update_connection_status("VPN Connected")
            
        except AdminRightsError:
            QMessageBox.warning(
                self, "Administrator Required",
                "Please run VPN Mikro as Administrator to install VPN tunnel."
            )
            self.devices_tab.status_label.setText("Admin rights required")
            self.devices_tab.status_label.setStyleSheet("color: red;")
        except Exception as e:
            logger.error(f"Failed to connect device: {e}")
            self.devices_tab.status_label.setText(f"Failed: {str(e)[:40]}...")
            self.devices_tab.status_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Connection Failed", str(e))
    
    def _on_device_disconnect_requested(self, device_uuid: str):
        """Handle device disconnect request."""
        if not self._current_profile:
            return
        
        if not self._device_manager:
            self._device_manager = DeviceManager(self._profile_manager)
        
        try:
            self._device_manager.disconnect_device(self._current_profile, device_uuid)
            self.devices_tab.update_device_status(device_uuid, connected=False)
            self.devices_tab.status_label.setText("Disconnected")
            self.devices_tab.status_label.setStyleSheet("color: gray;")
            self.update_connection_status("VPN Disconnected")
            
        except AdminRightsError:
            QMessageBox.warning(
                self, "Administrator Required",
                "Please run VPN Mikro as Administrator to uninstall VPN tunnel."
            )
        except Exception as e:
            logger.error(f"Failed to disconnect device: {e}")
            self.devices_tab.status_label.setText(f"Failed: {str(e)[:40]}...")
            self.devices_tab.status_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Disconnection Failed", str(e))
    
    def _on_device_delete_requested(self, device_uuid: str):
        """Handle device delete request."""
        if not self._ensure_connection():
            self.devices_tab.status_label.setText("Connection required")
            self.devices_tab.status_label.setStyleSheet("color: red;")
            return
        
        if not self._current_profile:
            return
        
        try:
            self._device_manager.delete_device(self._current_profile, device_uuid)
            self.devices_tab.remove_device_from_table(device_uuid)
            
        except Exception as e:
            logger.error(f"Failed to delete device: {e}")
            self.devices_tab.status_label.setText(f"Failed: {str(e)[:40]}...")
            self.devices_tab.status_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Deletion Failed", str(e))
    
    def _on_advanced_settings_changed(self):
        """Handle advanced settings change."""
        if not self._current_profile:
            return
        
        settings = self.advanced_tab.get_settings()
        self._current_profile.ip_pool = settings["ip_pool"]
        self._current_profile.dns = settings["dns"]
        self._current_profile.mtu = settings["mtu"]
        self._current_profile.keepalive = settings["keepalive"]
        self._current_profile.tunnel_mode = settings["tunnel_mode"]
        self._current_profile.split_subnets = settings["split_subnets"]
        
        try:
            self._profile_manager.save_profile(self._current_profile)
            logger.info("Advanced settings saved to profile")
        except Exception as e:
            logger.error(f"Failed to save advanced settings: {e}")
    
    def _refresh_interfaces(self):
        """Refresh WireGuard interfaces from MikroTik."""
        if not self._peer_manager:
            return
        
        try:
            interfaces = self._peer_manager.list_interfaces()
            self.vpn_servers_tab.set_interfaces(interfaces)
            
            # Select current interface if set
            if self._current_profile and self._current_profile.selected_interface:
                for i, iface in enumerate(interfaces):
                    if iface.name == self._current_profile.selected_interface:
                        self.vpn_servers_tab.interface_dropdown.setCurrentIndex(i)
                        break
                        
        except Exception as e:
            logger.error(f"Failed to fetch interfaces: {e}")
    
    def _on_tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()
    
    def update_connection_status(self, status: str):
        """Update the status bar with connection state.
        
        Args:
            status: Connection status text to display
        """
        self.status_bar.showMessage(f"Status: {status}")
    
    def load_profile(self, profile_name: str):
        """Load a specific profile by name.
        
        Args:
            profile_name: Name of the profile to load
        """
        try:
            self._current_profile = self._profile_manager.load_profile(profile_name)
            self._profile_manager.set_current_profile(profile_name)
            self._populate_ui_from_profile()
            logger.info(f"Loaded profile: {profile_name}")
        except Exception as e:
            logger.error(f"Failed to load profile {profile_name}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load profile: {e}")
    
    def closeEvent(self, event):
        """Handle window close - minimize to tray instead of quitting."""
        # Disconnect from MikroTik when closing
        if self._ros_client and self._ros_client.is_connected:
            try:
                self._ros_client.disconnect()
            except Exception:
                pass
        
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()


def run_app():
    """Run the VPN Mikro application."""
    app = QApplication(sys.argv)
    app.setApplicationName("VPN Mikro")
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    
    # Check for first run and launch wizard if needed
    from vpnmikro.ui.wizard import check_first_run, SetupWizard
    
    if check_first_run():
        logger.info("First run detected, launching setup wizard")
        wizard = SetupWizard()
        result = wizard.exec()
        
        if result != wizard.DialogCode.Accepted:
            # User cancelled wizard, exit app
            logger.info("Setup wizard cancelled, exiting")
            sys.exit(0)
        
        # Wizard completed, get the created profile name
        profile_name = wizard.created_profile_name
        logger.info(f"Setup wizard completed with profile: {profile_name}")
        
        # Create main window and load the profile
        window = MainWindow()
        if profile_name:
            window.load_profile(profile_name)
        window.show()
    else:
        # Normal startup
        window = MainWindow()
        window.show()
    
    sys.exit(app.exec())
