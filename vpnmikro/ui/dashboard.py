"""Modern dashboard-style main window for VPN Mikro.

Provides a clean, modern UI with:
- Top bar: Logo, profile selector, status pill, connect/disconnect, settings
- Main area: Two columns with cards for profile info and devices
- Bottom status bar
- System tray icon with minimize-to-tray support
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFrame, QTableWidget, QTableWidgetItem,
    QToolButton, QStatusBar, QHeaderView, QAbstractItemView, QMessageBox,
    QInputDialog, QSizePolicy, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QColor, QIcon, QAction, QCloseEvent

from vpnmikro.ui.assets import icon, load_theme, Icons, ICON_SIZE_MD, get_window_icon
from vpnmikro.core.profiles import ProfileManager
from vpnmikro.core.device_manager import DeviceManager, AdminRightsError
from vpnmikro.core.models import Profile, Device
from vpnmikro.core.logger import get_logger
from vpnmikro.mikrotik.ros_client import ROSClient
from vpnmikro.mikrotik.wg_manager import WGPeerManager

logger = get_logger(__name__)


class VPNWorkerThread(QThread):
    """Background thread for VPN connect/disconnect operations."""
    
    finished = pyqtSignal(bool, str)  # success, message
    status_update = pyqtSignal(str)  # status message for UI
    
    def __init__(self, device_manager: DeviceManager, profile: Profile, device_uuid: str, action: str, tunnel_name: str = None, timeout: int = 5):
        super().__init__()
        self._device_manager = device_manager
        self._profile = profile
        self._device_uuid = device_uuid
        self._action = action  # "connect" or "disconnect"
        self._tunnel_name = tunnel_name
        self._timeout = timeout  # Connection verification timeout in seconds
    
    def run(self):
        """Run the VPN operation in background."""
        import time
        
        try:
            if self._action == "connect":
                self._device_manager.connect_device(self._profile, self._device_uuid)
                
                # Verify connection by checking for traffic
                if self._tunnel_name:
                    self.status_update.emit("Verifying connection...")
                    
                    # Wait up to timeout seconds for traffic
                    for attempt in range(self._timeout):
                        time.sleep(1)
                        self.status_update.emit(f"Verifying... ({attempt + 1}/{self._timeout})")
                        
                        # Check for received bytes
                        rx_bytes = self._get_traffic_rx()
                        if rx_bytes and rx_bytes > 0:
                            self.finished.emit(True, "Connected")
                            return
                    
                    # No traffic after timeout - connection failed
                    self.finished.emit(False, f"verify_failed:No data received from VPN server after {self._timeout} seconds")
                    return
                
                self.finished.emit(True, "Connected")
            else:
                self._device_manager.disconnect_device(self._profile, self._device_uuid)
                self.finished.emit(True, "Disconnected")
        except PermissionError:
            self.finished.emit(False, "permission_cancelled")
        except AdminRightsError as e:
            self.finished.emit(False, f"admin_required:{e}")
        except Exception as e:
            self.finished.emit(False, f"error:{e}")
    
    def _get_traffic_rx(self) -> int:
        """Get received bytes from tunnel adapter."""
        if not self._tunnel_name:
            return 0
        
        try:
            cmd = [
                "powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                f"Get-NetAdapterStatistics -Name '{self._tunnel_name}' -ErrorAction SilentlyContinue | "
                "Select-Object -Property ReceivedBytes | ConvertTo-Json"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                return data.get("ReceivedBytes", 0) or 0
        except Exception:
            pass
        
        return 0


class TrafficMonitorThread(QThread):
    """Background thread for monitoring VPN traffic stats."""
    
    traffic_updated = pyqtSignal(int, int)  # rx_bytes, tx_bytes
    
    def __init__(self, tunnel_name: str, interval_ms: int = 2000):
        super().__init__()
        self._tunnel_name = tunnel_name
        self._interval_ms = interval_ms
        self._running = True
    
    def stop(self):
        """Stop the monitoring thread."""
        self._running = False
        self.wait(2000)
    
    def run(self):
        """Run the traffic monitoring loop."""
        import time
        
        while self._running:
            try:
                # Use PowerShell to get network adapter stats (reliable method)
                cmd = [
                    "powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                    f"Get-NetAdapterStatistics -Name '{self._tunnel_name}' -ErrorAction SilentlyContinue | "
                    "Select-Object -Property ReceivedBytes,SentBytes | ConvertTo-Json"
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    data = json.loads(result.stdout)
                    rx = data.get("ReceivedBytes", 0) or 0
                    tx = data.get("SentBytes", 0) or 0
                    self.traffic_updated.emit(rx, tx)
                
            except Exception as e:
                logger.debug(f"Traffic monitor error: {e}")
            
            # Sleep in small intervals to allow quick stop
            for _ in range(self._interval_ms // 100):
                if not self._running:
                    break
                time.sleep(0.1)


class MikroTikMonitorThread(QThread):
    """Background thread for monitoring MikroTik connection."""
    
    connection_lost = pyqtSignal(str)  # Emits error message when connection lost
    connection_ok = pyqtSignal()  # Emits when connection is OK
    
    def __init__(self, ros_client: ROSClient, interval_ms: int = 5000):
        super().__init__()
        self._ros_client = ros_client
        self._interval_ms = interval_ms
        self._running = True
    
    def stop(self):
        """Stop the monitoring thread."""
        self._running = False
        self.wait(2000)  # Wait up to 2 seconds for thread to finish
    
    def run(self):
        """Run the monitoring loop."""
        import time
        while self._running:
            try:
                if not self._ros_client:
                    self.connection_lost.emit("Client is None")
                    break
                    
                if not self._ros_client.is_connected:
                    self.connection_lost.emit("Client disconnected")
                    break
                
                # Lightweight check - get system identity
                self._ros_client.execute("/system/identity/print")
                self.connection_ok.emit()
                
            except Exception as e:
                logger.warning(f"MikroTik connection check failed: {e}")
                self.connection_lost.emit(str(e))
                break
            
            # Sleep in small intervals to allow quick stop
            for _ in range(self._interval_ms // 100):
                if not self._running:
                    break
                time.sleep(0.1)


class ModernMainWindow(QMainWindow):
    """Modern dashboard-style main window.
    
    Features:
    - Profile selector with quick connect
    - Device management table
    - Settings dialog access
    - Dark theme with purple accents
    - System tray icon with minimize-to-tray
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VPN Mikro")
        self.setMinimumSize(1100, 700)
        
        # Set window icon
        self._set_window_icon()
        
        # Backend services
        self._profile_manager = ProfileManager()
        self._current_profile: Optional[Profile] = None
        self._ros_client: Optional[ROSClient] = None
        self._peer_manager: Optional[WGPeerManager] = None
        self._device_manager: Optional[DeviceManager] = None
        self._devices: list[Device] = []
        self._all_clients: list[tuple] = []  # List of (profile, device) tuples
        self._mikrotik_profiles: list[Profile] = []  # List of profiles with MikroTik host
        
        # Connection state
        self._is_connected = False
        self._force_quit = False
        self._connected_tunnel_name: Optional[str] = None
        
        # MikroTik connection monitor thread (real-time, every 5 seconds)
        self._mikrotik_monitor_thread: Optional[MikroTikMonitorThread] = None
        
        # VPN worker thread for connect/disconnect operations
        self._vpn_worker: Optional[VPNWorkerThread] = None
        self._pending_device: Optional[Device] = None
        
        # Traffic monitor thread
        self._traffic_monitor: Optional[TrafficMonitorThread] = None
        
        # Settings for persistence
        from PyQt6.QtCore import QSettings
        self._settings = QSettings("VPNMikro", "VPNMikro")
        
        # VPN ping target for connection monitoring
        self._vpn_ping_target: Optional[str] = None
        
        # Apply theme
        self.setStyleSheet(load_theme())
        
        self._setup_ui()
        self._setup_status_bar()
        self._setup_tray_icon()
        self._wire_signals()
        
        # Fix any duplicate device names before loading
        self._fix_duplicate_devices()
        
        self._load_profiles()
        self._load_settings()  # Load saved settings
        
        # Check for updates on startup (delayed)
        QTimer.singleShot(3000, self._check_for_updates_silent)
    
    def _fix_duplicate_devices(self):
        """Check and fix duplicate device names across profiles."""
        fixes = self._profile_manager.fix_duplicate_device_names()
        if fixes:
            logger.warning(f"Fixed {len(fixes)} duplicate device names:")
            for fix in fixes:
                logger.warning(f"  - {fix}")
            # Show notification to user
            QTimer.singleShot(1000, lambda: self._show_duplicate_fix_message(fixes))
    
    def _show_duplicate_fix_message(self, fixes: list[str]):
        """Show message about fixed duplicates."""
        QMessageBox.information(
            self,
            "Duplicate Devices Fixed",
            f"Found and fixed {len(fixes)} duplicate device name(s):\n\n" +
            "\n".join(f"• {fix}" for fix in fixes[:5]) +
            ("\n..." if len(fixes) > 5 else "")
        )
    
    def _set_window_icon(self):
        """Set the window icon from logo folder."""
        self.setWindowIcon(get_window_icon())
    
    def _setup_ui(self):
        """Set up the main UI."""
        root = QWidget()
        self.setCentralWidget(root)
        
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        
        # Top bar
        outer.addLayout(self._create_top_bar())
        
        # Main area (2 columns)
        main = QHBoxLayout()
        main.setSpacing(12)
        
        # Left column
        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(self._create_profile_card())
        left.addWidget(self._create_quick_actions_card())
        left.addStretch(1)
        
        # Right column
        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(self._create_devices_card())
        
        main.addLayout(left, 1)
        main.addLayout(right, 2)
        
        outer.addLayout(main)
    
    def _create_top_bar(self) -> QHBoxLayout:
        """Create the top bar with logo, profile selector, and buttons."""
        from PyQt6.QtGui import QPixmap
        
        top = QHBoxLayout()
        top.setSpacing(12)
        
        # Logo image instead of text title
        logo_label = QLabel()
        logo_paths = [
            Path(__file__).parent.parent.parent / "logo" / "logo_no_BG.png",
            Path(sys.executable).parent / "logo" / "logo_no_BG.png",
        ]
        
        for logo_path in logo_paths:
            if logo_path.exists():
                pixmap = QPixmap(str(logo_path))
                if not pixmap.isNull():
                    # Scale to ~32px height to match the top bar
                    scaled = pixmap.scaledToHeight(32, Qt.TransformationMode.SmoothTransformation)
                    logo_label.setPixmap(scaled)
                    break
        
        logo_label.setToolTip("VPN Mikro")
        top.addWidget(logo_label)
        
        top.addStretch(1)
        
        # VPN Client selector (shows all devices from all profiles)
        self.client_combo = QComboBox()
        self.client_combo.setMinimumWidth(260)
        self.client_combo.setPlaceholderText("Select VPN client...")
        top.addWidget(self.client_combo)
        
        # Status pill
        self.status_pill = QLabel("Disconnected")
        self.status_pill.setObjectName("StatusPill")
        self.status_pill.setProperty("status", "disconnected")
        self.status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_pill.setMinimumWidth(100)
        top.addWidget(self.status_pill)
        
        # Connect button
        self.btn_connect = QPushButton(" Connect")
        self.btn_connect.setObjectName("PrimaryButton")
        self.btn_connect.setIcon(icon(Icons.PLUG))
        self.btn_connect.setIconSize(ICON_SIZE_MD)
        top.addWidget(self.btn_connect)
        
        # Disconnect button (hidden by default)
        self.btn_disconnect = QPushButton(" Disconnect")
        self.btn_disconnect.setObjectName("DangerButton")
        self.btn_disconnect.setIcon(icon(Icons.UNPLUG))
        self.btn_disconnect.setIconSize(ICON_SIZE_MD)
        self.btn_disconnect.setVisible(False)
        top.addWidget(self.btn_disconnect)
        
        # Settings button
        self.btn_settings = QToolButton()
        self.btn_settings.setIcon(icon(Icons.SETTINGS))
        self.btn_settings.setIconSize(ICON_SIZE_MD)
        self.btn_settings.setToolTip("Settings")
        self.btn_settings.setObjectName("IconButton")
        top.addWidget(self.btn_settings)
        
        return top
    
    def _create_card(self, title_text: str) -> QFrame:
        """Create a styled card frame."""
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        
        title = QLabel(title_text)
        title.setObjectName("CardTitle")
        layout.addWidget(title)
        
        return frame
    
    def _create_profile_card(self) -> QWidget:
        """Create the selected profile info card with MikroTik management."""
        card = self._create_card("MikroTik Management")
        layout = card.layout()
        
        # Enable/Disable MikroTik management checkbox
        from PyQt6.QtWidgets import QCheckBox
        self.chk_mikrotik_enabled = QCheckBox("Enable MikroTik Management")
        self.chk_mikrotik_enabled.setToolTip("Enable to manage WireGuard peers on MikroTik router")
        self.chk_mikrotik_enabled.stateChanged.connect(self._on_mikrotik_enabled_changed)
        layout.addWidget(self.chk_mikrotik_enabled)
        
        # MikroTik management container (hidden by default)
        self.mikrotik_container = QWidget()
        mikrotik_layout = QVBoxLayout(self.mikrotik_container)
        mikrotik_layout.setContentsMargins(0, 8, 0, 0)
        mikrotik_layout.setSpacing(8)
        
        # MikroTik selector combo
        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)
        lbl_select = QLabel("Router:")
        lbl_select.setObjectName("MutedLabel")
        self.mikrotik_combo = QComboBox()
        self.mikrotik_combo.setMinimumWidth(180)
        self.mikrotik_combo.setPlaceholderText("Select MikroTik...")
        self.mikrotik_combo.currentIndexChanged.connect(self._on_mikrotik_selected)
        selector_row.addWidget(lbl_select)
        selector_row.addWidget(self.mikrotik_combo)
        selector_row.addStretch()
        mikrotik_layout.addLayout(selector_row)
        
        # Profile info labels
        self.lbl_host = QLabel("Host: —")
        self.lbl_port = QLabel("Port: —")
        self.lbl_tls = QLabel("TLS Verify: —")
        self.lbl_interface = QLabel("Interface: —")
        
        for lbl in [self.lbl_host, self.lbl_port, self.lbl_tls, self.lbl_interface]:
            lbl.setObjectName("MutedLabel")
            mikrotik_layout.addWidget(lbl)
        
        # MikroTik connection status
        self.lbl_mikrotik_status = QLabel("MikroTik: Disconnected")
        self.lbl_mikrotik_status.setObjectName("MutedLabel")
        mikrotik_layout.addWidget(self.lbl_mikrotik_status)
        
        # Button row for MikroTik connection
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        
        self.btn_mikrotik_connect = QPushButton(" Connect")
        self.btn_mikrotik_connect.setIcon(icon(Icons.PLUG))
        self.btn_mikrotik_connect.setIconSize(ICON_SIZE_MD)
        self.btn_mikrotik_connect.setToolTip("Connect to MikroTik router")
        
        self.btn_mikrotik_disconnect = QPushButton(" Disconnect")
        self.btn_mikrotik_disconnect.setIcon(icon(Icons.UNPLUG))
        self.btn_mikrotik_disconnect.setIconSize(ICON_SIZE_MD)
        self.btn_mikrotik_disconnect.setToolTip("Disconnect from MikroTik router")
        self.btn_mikrotik_disconnect.setVisible(False)
        
        self.btn_test = QPushButton(" Test")
        self.btn_test.setIcon(icon(Icons.REFRESH))
        self.btn_test.setIconSize(ICON_SIZE_MD)
        self.btn_test.setToolTip("Test connection without staying connected")
        
        self.btn_mikrotik_settings = QPushButton(" Settings")
        self.btn_mikrotik_settings.setIcon(icon(Icons.SETTINGS))
        self.btn_mikrotik_settings.setIconSize(ICON_SIZE_MD)
        self.btn_mikrotik_settings.setToolTip("Edit MikroTik profile settings")
        
        btn_row.addWidget(self.btn_mikrotik_connect)
        btn_row.addWidget(self.btn_mikrotik_disconnect)
        btn_row.addWidget(self.btn_test)
        btn_row.addWidget(self.btn_mikrotik_settings)
        btn_row.addStretch()
        
        mikrotik_layout.addLayout(btn_row)
        
        # Hide MikroTik container by default
        self.mikrotik_container.setVisible(False)
        layout.addWidget(self.mikrotik_container)
        
        return card
    
    def _create_quick_actions_card(self) -> QWidget:
        """Create the quick actions card."""
        card = self._create_card("Quick Actions")
        layout = card.layout()
        
        row = QHBoxLayout()
        row.setSpacing(8)
        
        self.btn_new_profile = QPushButton(" New")
        self.btn_new_profile.setIcon(icon(Icons.PLUS))
        self.btn_new_profile.setIconSize(ICON_SIZE_MD)
        
        self.btn_edit_profile = QPushButton(" Edit")
        self.btn_edit_profile.setIcon(icon(Icons.PROFILE))
        self.btn_edit_profile.setIconSize(ICON_SIZE_MD)
        
        self.btn_delete_profile = QPushButton(" Delete")
        self.btn_delete_profile.setIcon(icon(Icons.TRASH))
        self.btn_delete_profile.setIconSize(ICON_SIZE_MD)
        
        row.addWidget(self.btn_new_profile)
        row.addWidget(self.btn_edit_profile)
        row.addWidget(self.btn_delete_profile)
        
        layout.addLayout(row)
        
        return card
    
    def _create_devices_card(self) -> QWidget:
        """Create the devices table card."""
        card = self._create_card("Devices")
        layout = card.layout()
        
        # Devices table
        self.devices_table = QTableWidget(0, 6)
        self.devices_table.setHorizontalHeaderLabels([
            "Name", "IP", "Status", "Enabled", "Traffic", "Created"
        ])
        self.devices_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.devices_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.devices_table.setAlternatingRowColors(True)
        self.devices_table.setSortingEnabled(True)
        self.devices_table.verticalHeader().setVisible(False)
        self.devices_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)  # Read-only
        self.devices_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Remove focus rectangle
        self.devices_table.cellDoubleClicked.connect(self._on_device_double_click)
        self.devices_table.cellClicked.connect(self._on_device_row_clicked)
        
        # Column sizing - allow user to resize columns
        header = self.devices_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # User can resize all columns
        header.setStretchLastSection(True)  # Last column stretches to fill space
        
        # Set default column widths
        self.devices_table.setColumnWidth(0, 150)  # Name
        self.devices_table.setColumnWidth(1, 120)  # IP
        self.devices_table.setColumnWidth(2, 100)  # Status
        self.devices_table.setColumnWidth(3, 70)   # Enabled
        self.devices_table.setColumnWidth(4, 120)  # Traffic
        # Column 5 (Created) will stretch
        
        layout.addWidget(self.devices_table)
        
        # Button row
        btns = QHBoxLayout()
        btns.setSpacing(8)
        
        self.btn_add_device = QPushButton(" Add")
        self.btn_add_device.setIcon(icon(Icons.PLUS))
        self.btn_add_device.setIconSize(ICON_SIZE_MD)
        self.btn_add_device.setEnabled(True)  # Always enabled - can create manual VPN profiles
        self.btn_add_device.setToolTip("Add a new VPN profile")
        
        self.btn_device_settings = QPushButton(" Settings")
        self.btn_device_settings.setIcon(icon(Icons.SETTINGS))
        self.btn_device_settings.setIconSize(ICON_SIZE_MD)
        
        self.btn_import_device = QPushButton(" Import")
        self.btn_import_device.setIcon(icon(Icons.DOWNLOAD))
        self.btn_import_device.setIconSize(ICON_SIZE_MD)
        self.btn_import_device.setToolTip("Import WireGuard config file")
        
        self.btn_delete_device = QPushButton(" Delete")
        self.btn_delete_device.setIcon(icon(Icons.TRASH))
        self.btn_delete_device.setIconSize(ICON_SIZE_MD)
        self.btn_delete_device.setEnabled(True)  # Always enabled - imported devices don't need MikroTik
        self.btn_delete_device.setToolTip("Delete selected device")
        
        btns.addWidget(self.btn_add_device)
        btns.addWidget(self.btn_import_device)
        btns.addWidget(self.btn_device_settings)
        btns.addStretch(1)
        
        self.btn_export = QPushButton(" Export")
        self.btn_export.setIcon(icon(Icons.DOWNLOAD))
        self.btn_export.setIconSize(ICON_SIZE_MD)
        
        self.btn_qr = QPushButton(" QR")
        self.btn_qr.setIcon(icon(Icons.QRCODE))
        self.btn_qr.setIconSize(ICON_SIZE_MD)
        
        self.btn_copy_key = QPushButton(" Copy Key")
        self.btn_copy_key.setIcon(icon(Icons.COPY))
        self.btn_copy_key.setIconSize(ICON_SIZE_MD)
        
        btns.addWidget(self.btn_export)
        btns.addWidget(self.btn_qr)
        btns.addWidget(self.btn_copy_key)
        btns.addWidget(self.btn_delete_device)
        
        layout.addLayout(btns)
        
        return card
    
    def _setup_status_bar(self):
        """Set up the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar("Ready")
    
    def _setup_tray_icon(self):
        """Set up the system tray icon."""
        # Create tray icon with the app logo
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(get_window_icon())  # Use the app icon
        self.tray_icon.setToolTip("VPN Mikro - Disconnected")
        
        # Create tray menu
        tray_menu = QMenu()
        
        # Show/Hide action
        self.tray_action_show = QAction("Show", self)
        self.tray_action_show.triggered.connect(self._on_tray_show)
        tray_menu.addAction(self.tray_action_show)
        
        tray_menu.addSeparator()
        
        # Connect action
        self.tray_action_connect = QAction("Connect", self)
        self.tray_action_connect.triggered.connect(self._on_tray_connect)
        tray_menu.addAction(self.tray_action_connect)
        
        # Disconnect action
        self.tray_action_disconnect = QAction("Disconnect", self)
        self.tray_action_disconnect.triggered.connect(self._on_tray_disconnect)
        self.tray_action_disconnect.setEnabled(False)
        tray_menu.addAction(self.tray_action_disconnect)
        
        tray_menu.addSeparator()
        
        # Exit action
        self.tray_action_exit = QAction("Exit", self)
        self.tray_action_exit.triggered.connect(self._on_tray_exit)
        tray_menu.addAction(self.tray_action_exit)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # Double-click to show window
        self.tray_icon.activated.connect(self._on_tray_activated)
        
        # Show tray icon
        self.tray_icon.show()
    
    def _on_tray_show(self):
        """Show the main window from tray."""
        self.showNormal()
        self.activateWindow()
        self.raise_()
    
    def _on_tray_connect(self):
        """Connect from tray menu."""
        self._on_tray_show()
        # If there's a selected device, connect it
        device = self._get_selected_device()
        if device:
            self._on_connect_device()
    
    def _on_tray_disconnect(self):
        """Disconnect from tray menu."""
        device = self._get_selected_device()
        if device:
            self._on_disconnect_device()
    
    def _on_tray_exit(self):
        """Exit application from tray."""
        if self._is_connected:
            reply = QMessageBox.question(
                self,
                "VPN Active",
                "VPN is still connected. Disconnect and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            # Disconnect all active devices
            self._disconnect_all_devices()
        
        # Stop MikroTik monitor thread before quitting
        self._stop_mikrotik_monitor()
        
        # Stop VPN monitor
        self._stop_vpn_monitor()
        
        self._force_quit = True
        self.tray_icon.hide()
        QApplication.quit()
    
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """Handle tray icon activation."""
        try:
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
                self._on_tray_show()
        except Exception as e:
            logger.warning(f"Tray activation error: {e}")
    
    def _update_tray_state(self, connected: bool):
        """Update tray icon and menu based on connection state."""
        self._is_connected = connected
        
        if connected:
            self.tray_icon.setToolTip("VPN Mikro - Connected")
            self.tray_action_connect.setEnabled(False)
            self.tray_action_disconnect.setEnabled(True)
            # Show notification if enabled
            if self._settings.value("notify_vpn_connect", True, type=bool):
                self.tray_icon.showMessage(
                    "VPN Mikro",
                    "VPN Connected",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000
                )
        else:
            self.tray_icon.setToolTip("VPN Mikro - Disconnected")
            self.tray_action_connect.setEnabled(True)
            self.tray_action_disconnect.setEnabled(False)
            # Show notification if enabled
            if self._settings.value("notify_vpn_disconnect", False, type=bool):
                self.tray_icon.showMessage(
                    "VPN Mikro",
                    "VPN Disconnected",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000
                )
    
    def _disconnect_all_devices(self):
        """Disconnect all active devices."""
        if not self._device_manager:
            self._device_manager = DeviceManager(self._profile_manager)
        
        for device in self._devices:
            try:
                self._device_manager.disconnect_device(self._current_profile, device.uuid)
            except Exception as e:
                logger.warning(f"Failed to disconnect {device.name}: {e}")
        
        self._update_tray_state(False)
    
    def _wire_signals(self):
        """Connect signals to slots."""
        # VPN Client selection
        self.client_combo.currentIndexChanged.connect(self._on_client_selected)
        
        # Top bar buttons
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        self.btn_disconnect.clicked.connect(self._on_disconnect_clicked)
        self.btn_settings.clicked.connect(self._on_settings_clicked)
        
        # Profile card
        self.btn_mikrotik_connect.clicked.connect(self._on_mikrotik_connect)
        self.btn_mikrotik_disconnect.clicked.connect(self._on_mikrotik_disconnect)
        self.btn_test.clicked.connect(self._on_test_connection)
        self.btn_mikrotik_settings.clicked.connect(self._on_mikrotik_settings)
        
        # Quick actions
        self.btn_new_profile.clicked.connect(self._on_new_profile)
        self.btn_edit_profile.clicked.connect(self._on_edit_profile)
        self.btn_delete_profile.clicked.connect(self._on_delete_profile)
        
        # Device buttons
        self.btn_add_device.clicked.connect(self._on_add_device)
        self.btn_import_device.clicked.connect(self._on_import_device)
        self.btn_device_settings.clicked.connect(self._on_device_settings)
        self.btn_export.clicked.connect(self._on_export_device)
        self.btn_qr.clicked.connect(self._on_show_qr)
        self.btn_copy_key.clicked.connect(self._on_copy_key)
        self.btn_delete_device.clicked.connect(self._on_delete_device)
    
    def _load_profiles(self):
        """Load all profiles and populate the client combo with all VPN clients."""
        self.client_combo.clear()
        self.mikrotik_combo.clear()
        self._all_clients = []  # List of (profile, device) tuples - None for "All"
        self._mikrotik_profiles = []  # List of profiles with MikroTik host
        
        profiles = self._profile_manager.list_profiles()
        
        # Add "All" option first
        self.client_combo.addItem("All VPN Clients")
        self._all_clients.append(None)  # None means "All"
        
        for profile_name in profiles:
            try:
                profile = self._profile_manager.load_profile(profile_name)
                
                # Add to MikroTik combo if it has a host configured
                if profile.host:
                    self._mikrotik_profiles.append(profile)
                    self.mikrotik_combo.addItem(f"{profile.name} ({profile.host})")
                
                for device in profile.devices:
                    self._all_clients.append((profile, device))
                    # Show only device name (no profile name)
                    self.client_combo.addItem(device.name)
            except Exception as e:
                logger.warning(f"Failed to load profile {profile_name}: {e}")
        
        # Select "All" by default and show all devices
        self.client_combo.setCurrentIndex(0)
        self._show_all_devices()
        
        # Select first MikroTik if available
        if self._mikrotik_profiles:
            self.mikrotik_combo.setCurrentIndex(0)
    
    def _load_settings(self):
        """Load saved settings from previous session."""
        # Load MikroTik Management enabled state
        mikrotik_enabled = self._settings.value("mikrotik_enabled", False, type=bool)
        self.chk_mikrotik_enabled.setChecked(mikrotik_enabled)
        self.mikrotik_container.setVisible(mikrotik_enabled)
        
        # Load selected MikroTik profile index
        mikrotik_index = self._settings.value("mikrotik_index", 0, type=int)
        if mikrotik_index < self.mikrotik_combo.count():
            self.mikrotik_combo.setCurrentIndex(mikrotik_index)
        
        # Load selected VPN client index
        client_index = self._settings.value("client_index", 0, type=int)
        if client_index < self.client_combo.count():
            self.client_combo.setCurrentIndex(client_index)
        
        # Load table column widths
        for i in range(self.devices_table.columnCount() - 1):  # Skip last column (stretches)
            width = self._settings.value(f"column_width_{i}", 0, type=int)
            if width > 0:
                self.devices_table.setColumnWidth(i, width)
        
        # Load window geometry
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        # Load window state (maximized, etc.)
        state = self._settings.value("windowState")
        if state:
            self.restoreState(state)
        
        logger.debug("Settings loaded from previous session")
    
    def _save_settings(self):
        """Save current settings for next session."""
        # Save MikroTik Management enabled state
        self._settings.setValue("mikrotik_enabled", self.chk_mikrotik_enabled.isChecked())
        
        # Save selected MikroTik profile index
        self._settings.setValue("mikrotik_index", self.mikrotik_combo.currentIndex())
        
        # Save selected VPN client index
        self._settings.setValue("client_index", self.client_combo.currentIndex())
        
        # Save table column widths
        for i in range(self.devices_table.columnCount() - 1):  # Skip last column (stretches)
            self._settings.setValue(f"column_width_{i}", self.devices_table.columnWidth(i))
        
        # Save window geometry
        self._settings.setValue("geometry", self.saveGeometry())
        
        # Save window state
        self._settings.setValue("windowState", self.saveState())
        
        logger.debug("Settings saved")
    
    def closeEvent(self, event: QCloseEvent):
        """Handle window close event - save settings and minimize to tray."""
        # Save settings before closing
        self._save_settings()
        
        if self._force_quit:
            event.accept()
            return
        
        # Minimize to tray instead of closing
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "VPN Mikro",
            "Application minimized to tray. Right-click the tray icon to quit.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )
    
    def _on_client_selected(self, index: int):
        """Handle VPN client selection change."""
        if index < 0 or index >= len(self._all_clients):
            return
        
        client_entry = self._all_clients[index]
        
        # Handle "All" option - just show all devices, no selection
        if client_entry is None:
            self._show_all_devices()
            return
        
        profile, device = client_entry
        self._current_profile = profile
        self._profile_manager.set_current_profile(profile.name)
        
        # Update MikroTik combo to match the selected profile (if it has MikroTik)
        if profile.host:  # Only if profile has MikroTik host
            for i, mikrotik_profile in enumerate(self._mikrotik_profiles):
                if mikrotik_profile.name == profile.name:
                    # Block signals to avoid recursive calls
                    self.mikrotik_combo.blockSignals(True)
                    self.mikrotik_combo.setCurrentIndex(i)
                    self.mikrotik_combo.blockSignals(False)
                    self._update_profile_card()
                    break
        
        # Always show all devices in the table
        self._show_all_devices()
        
        # Find and select the device in the table
        for row, d in enumerate(self._devices):
            if d.uuid == device.uuid:
                self.devices_table.selectRow(row)
                break
    
    def _show_all_devices(self):
        """Show all devices from all profiles in the table."""
        self._devices = []
        profiles = self._profile_manager.list_profiles()
        
        for profile_name in profiles:
            try:
                profile = self._profile_manager.load_profile(profile_name)
                self._devices.extend(profile.devices)
            except Exception as e:
                logger.warning(f"Failed to load profile {profile_name}: {e}")
        
        # Update table with all devices
        self.devices_table.setRowCount(len(self._devices))
        
        for row, device in enumerate(self._devices):
            items = [
                QTableWidgetItem(device.name),
                QTableWidgetItem(device.assigned_ip),
                QTableWidgetItem("Disconnected"),
                QTableWidgetItem("Yes" if device.enabled else "No"),
                QTableWidgetItem("—"),
                QTableWidgetItem(device.created_at.strftime("%Y-%m-%d %H:%M") if device.created_at else "—"),
            ]
            
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.devices_table.setItem(row, col, item)
    
    def _on_profile_selected(self, index: int):
        """Handle profile selection change (legacy - kept for compatibility)."""
        pass  # Now handled by _on_client_selected
    
    def _on_mikrotik_enabled_changed(self, state: int):
        """Handle MikroTik management checkbox change."""
        from PyQt6.QtCore import Qt
        enabled = state == Qt.CheckState.Checked.value
        self.mikrotik_container.setVisible(enabled)
        
        if enabled and self._mikrotik_profiles:
            # Update profile card with selected MikroTik info
            self._on_mikrotik_selected(self.mikrotik_combo.currentIndex())
        else:
            # Disabled - disconnect from MikroTik and remove synced devices
            self._cleanup_mikrotik_connection()
        
        # Always show all devices - just highlight MikroTik ones when enabled
        self._show_all_devices()
    
    def _cleanup_mikrotik_connection(self):
        """Disconnect from MikroTik and remove devices that were synced from it."""
        # Stop connection monitor thread
        self._stop_mikrotik_monitor()
        
        # Disconnect from MikroTik if connected
        if self._ros_client:
            try:
                self._ros_client.disconnect()
            except Exception:
                pass
            self._ros_client = None
            self._peer_manager = None
        
        # Update UI to show disconnected state
        self.btn_mikrotik_connect.setVisible(True)
        self.btn_mikrotik_connect.setEnabled(True)
        self.btn_mikrotik_disconnect.setVisible(False)
        self.lbl_mikrotik_status.setText("MikroTik: Disconnected")
        self.lbl_mikrotik_status.setStyleSheet("")
        
        # Remove devices that were synced from MikroTik (devices without config_path or private_key)
        # These are devices that were imported from MikroTik peers, not created locally
        for profile in self._mikrotik_profiles:
            devices_to_remove = []
            for device in profile.devices:
                # Devices synced from MikroTik have empty private_key_encrypted and config_path
                if not device.private_key_encrypted and not device.config_path:
                    devices_to_remove.append(device)
                    logger.info(f"Removing MikroTik-synced device: {device.name}")
            
            # Remove the devices
            for device in devices_to_remove:
                profile.devices.remove(device)
            
            # Save profile if devices were removed
            if devices_to_remove:
                self._profile_manager.save_profile(profile)
        
        # Reload profiles to update UI
        self._load_profiles()
        self._update_status_bar("MikroTik management disabled")
    
    def _on_mikrotik_selected(self, index: int):
        """Handle MikroTik router selection change."""
        if index < 0 or index >= len(self._mikrotik_profiles):
            return
        
        profile = self._mikrotik_profiles[index]
        self._current_profile = profile
        self._update_profile_card()
        
        # Highlight devices from this profile in the table
        self._highlight_profile_devices(profile.name)
    
    def _highlight_profile_devices(self, profile_name: str):
        """Highlight devices from a specific profile in the table with purple background."""
        if not self.chk_mikrotik_enabled.isChecked():
            return
        
        # Find which devices belong to this profile
        profile_device_uuids = set()
        for client_entry in self._all_clients:
            if client_entry is not None:
                entry_profile, entry_device = client_entry
                if entry_profile.name == profile_name:
                    profile_device_uuids.add(entry_device.uuid)
        
        # Highlight matching rows
        highlight_color = QColor(124, 58, 237, 50)  # Purple with transparency
        normal_color = QColor(0, 0, 0, 0)  # Transparent
        
        for row, device in enumerate(self._devices):
            color = highlight_color if device.uuid in profile_device_uuids else normal_color
            for col in range(self.devices_table.columnCount()):
                item = self.devices_table.item(row, col)
                if item:
                    item.setBackground(color)
    
    def _update_profile_card(self):
        """Update the profile info card."""
        if not self._current_profile:
            self.lbl_host.setText("Host: —")
            self.lbl_port.setText("Port: —")
            self.lbl_tls.setText("TLS Verify: —")
            self.lbl_interface.setText("Interface: —")
            return
        
        p = self._current_profile
        self.lbl_host.setText(f"Host: {p.host or '—'}")
        self.lbl_port.setText(f"Port: {p.port}")
        self.lbl_tls.setText(f"TLS Verify: {'Yes' if p.verify_tls else 'No'}")
        self.lbl_interface.setText(f"Interface: {p.selected_interface or '—'}")
    
    def _update_devices_table(self):
        """Update the devices table."""
        if not self._current_profile:
            self.devices_table.setRowCount(0)
            self._devices = []
            return
        
        self._devices = self._current_profile.devices
        self.devices_table.setRowCount(len(self._devices))
        
        for row, device in enumerate(self._devices):
            # Create items and make them read-only
            items = [
                QTableWidgetItem(device.name),
                QTableWidgetItem(device.assigned_ip),
                QTableWidgetItem("Disconnected"),
                QTableWidgetItem("Yes" if device.enabled else "No"),
                QTableWidgetItem("—"),
                QTableWidgetItem(device.created_at.strftime("%Y-%m-%d %H:%M") if device.created_at else "—"),
            ]
            
            for col, item in enumerate(items):
                # Make item read-only (not editable)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.devices_table.setItem(row, col, item)
    
    def _update_status_bar(self, message: str):
        """Update the status bar message."""
        self.status_bar.showMessage(message)
    
    def _check_for_updates_silent(self):
        """Check for updates silently on startup."""
        # Check if auto-update is enabled in settings
        if not self._settings.value("auto_check_updates", True, type=bool):
            logger.debug("Auto-update check disabled in settings")
            return
        
        from vpnmikro.ui.about_dialog import VERSION, UpdateCheckThread
        
        self._startup_update_thread = UpdateCheckThread(VERSION)
        self._startup_update_thread.update_available.connect(self._on_startup_update_available)
        self._startup_update_thread.start()
    
    def _on_startup_update_available(self, update_info):
        """Handle update available on startup."""
        if update_info is None:
            return  # No update, do nothing
        
        from vpnmikro.ui.about_dialog import VERSION
        
        # Show notification in tray
        self.tray_icon.showMessage(
            "Update Available",
            f"VPN Mikro {update_info.version} is available!\nClick to update.",
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )
        
        # Also show a non-blocking message
        reply = QMessageBox.question(
            self,
            "Update Available",
            f"<b>A new version of VPN Mikro is available!</b><br><br>"
            f"<b>Current version:</b> {VERSION}<br>"
            f"<b>New version:</b> {update_info.version}<br><br>"
            f"Would you like to open the About dialog to download the update?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Open About dialog
            from vpnmikro.ui.about_dialog import AboutDialog
            dialog = AboutDialog(self)
            dialog.exec()
    
    def _start_vpn_monitor(self):
        """Start VPN traffic monitor thread."""
        # Stop any existing monitor
        self._stop_vpn_monitor()
        
        if not self._connected_tunnel_name:
            return
        
        # Get stats interval from settings (in seconds, convert to ms)
        stats_interval = self._settings.value("stats_update_interval", 2, type=int) * 1000
        
        # Start traffic monitor thread
        self._traffic_monitor = TrafficMonitorThread(self._connected_tunnel_name, interval_ms=stats_interval)
        self._traffic_monitor.traffic_updated.connect(self._on_traffic_updated)
        self._traffic_monitor.start()
    
    def _stop_vpn_monitor(self):
        """Stop VPN traffic monitor thread."""
        if self._traffic_monitor:
            self._traffic_monitor.stop()
            self._traffic_monitor = None
    
    def _on_traffic_updated(self, rx_bytes: int, tx_bytes: int):
        """Handle traffic update from monitor thread."""
        row = self.devices_table.currentRow()
        if row >= 0:
            traffic_item = self.devices_table.item(row, 4)
            if traffic_item:
                # Format traffic as human-readable
                traffic_str = f"↓{self._format_bytes(rx_bytes)} ↑{self._format_bytes(tx_bytes)}"
                traffic_item.setText(traffic_str)
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes as human-readable string."""
        if bytes_val < 1024:
            return f"{bytes_val}B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f}KB"
        elif bytes_val < 1024 * 1024 * 1024:
            return f"{bytes_val / (1024 * 1024):.1f}MB"
        else:
            return f"{bytes_val / (1024 * 1024 * 1024):.2f}GB"
    
    def _set_connected_state(self, connected: bool):
        """Update UI for connected/disconnected state (MikroTik connection)."""
        # Note: This is for MikroTik connection, not VPN device connection
        
        # Enable/disable buttons that require MikroTik connection
        self.btn_add_device.setEnabled(connected)
        # Delete is always enabled - imported devices don't need MikroTik
        
        if connected:
            self.btn_add_device.setToolTip("Add a new device")
        else:
            self.btn_add_device.setToolTip("Connect to MikroTik first to add devices")
    
    def _get_selected_device(self) -> Optional[Device]:
        """Get the currently selected device."""
        row = self.devices_table.currentRow()
        if 0 <= row < len(self._devices):
            return self._devices[row]
        return None
    
    def _ensure_connection(self) -> bool:
        """Ensure we have an active MikroTik connection."""
        if self._ros_client and self._ros_client.is_connected:
            return True
        
        if not self._current_profile:
            QMessageBox.warning(self, "No Profile", "Please select a profile first.")
            return False
        
        # Check if profile has MikroTik host configured
        if not self._current_profile.host:
            QMessageBox.warning(
                self, "No MikroTik Host",
                "This profile has no MikroTik host configured.\n"
                "It may be a client-only profile imported from a .conf file."
            )
            return False
        
        try:
            username, password = self._profile_manager.decrypt_credentials(self._current_profile)
            if not username or not password:
                QMessageBox.warning(self, "Credentials Required", "Please configure credentials in Settings.")
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
            
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            QMessageBox.critical(self, "Connection Failed", str(e))
            return False
    
    # === Event Handlers ===
    
    def _on_connect_clicked(self):
        """Handle main Connect button click - connect selected VPN device."""
        # Check if "All VPN Clients" is selected
        if self.client_combo.currentIndex() == 0:
            QMessageBox.warning(
                self, "Select a Client",
                "Please select a specific VPN client to connect.\n\n"
                "The 'All VPN Clients' option is for viewing only."
            )
            return
        
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "No Selection", "Please select a device from the table.")
            return
        
        # Use the device connect logic
        self._on_connect_device()
    
    def _on_disconnect_clicked(self):
        """Handle main Disconnect button click - disconnect selected VPN device."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "No Selection", "Please select a device from the table.")
            return
        
        # Use the device disconnect logic
        self._on_disconnect_device()
    
    def _on_settings_clicked(self):
        """Handle Settings button click - open application settings."""
        from vpnmikro.ui.app_settings_dialog import AppSettingsDialog
        dialog = AppSettingsDialog(self)
        dialog.exec()
    
    def _on_mikrotik_settings(self):
        """Handle MikroTik Settings button click - open settings for selected MikroTik profile."""
        # Get the selected MikroTik profile from the combo
        mikrotik_index = self.mikrotik_combo.currentIndex()
        if mikrotik_index < 0 or mikrotik_index >= len(self._mikrotik_profiles):
            QMessageBox.warning(self, "No MikroTik", "Please select a MikroTik router first.")
            return
        
        mikrotik_profile = self._mikrotik_profiles[mikrotik_index]
        
        from vpnmikro.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(mikrotik_profile, self._profile_manager, self)
        if dialog.exec():
            # Reload profiles after settings change
            self._load_profiles()
            # Re-select the MikroTik profile
            if mikrotik_index < len(self._mikrotik_profiles):
                self.mikrotik_combo.setCurrentIndex(mikrotik_index)
                self._update_profile_card()
    
    def _on_test_connection(self):
        """Handle Test Connection button click."""
        # Get the selected MikroTik profile from the combo
        mikrotik_index = self.mikrotik_combo.currentIndex()
        if mikrotik_index < 0 or mikrotik_index >= len(self._mikrotik_profiles):
            QMessageBox.warning(self, "No MikroTik", "Please select a MikroTik router first.")
            return
        
        mikrotik_profile = self._mikrotik_profiles[mikrotik_index]
        
        # Check if profile has MikroTik host configured
        if not mikrotik_profile.host:
            QMessageBox.warning(
                self, "No MikroTik Host",
                "This profile has no MikroTik host configured."
            )
            return
        
        self._update_status_bar("Testing connection...")
        
        try:
            username, password = self._profile_manager.decrypt_credentials(mikrotik_profile)
            if not username or not password:
                QMessageBox.warning(self, "Credentials Required", "Please configure credentials in Settings for this MikroTik profile.")
                return
            
            client = ROSClient(
                mikrotik_profile.host,
                mikrotik_profile.port,
                verify_tls=mikrotik_profile.verify_tls
            )
            client.connect()
            success = client.login(username, password)
            client.disconnect()
            
            if success:
                QMessageBox.information(self, "Success", "Connection successful!")
                self._update_status_bar("Connection test: OK")
            else:
                QMessageBox.warning(self, "Failed", "Authentication failed.")
                self._update_status_bar("Connection test: Auth failed")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed:\n{e}")
            self._update_status_bar("Connection test: Failed")
    
    def _start_mikrotik_monitor(self):
        """Start the MikroTik connection monitor thread."""
        self._stop_mikrotik_monitor()  # Stop any existing monitor
        
        if self._ros_client:
            # Get interval from settings (default 5 seconds)
            interval_sec = self._settings.value("mikrotik_check_interval", 5, type=int)
            interval_ms = interval_sec * 1000
            
            self._mikrotik_monitor_thread = MikroTikMonitorThread(self._ros_client, interval_ms=interval_ms)
            self._mikrotik_monitor_thread.connection_lost.connect(self._on_mikrotik_connection_lost)
            self._mikrotik_monitor_thread.connection_ok.connect(self._on_mikrotik_connection_ok)
            self._mikrotik_monitor_thread.start()
            logger.info(f"MikroTik connection monitor started ({interval_sec} second interval)")
    
    def _stop_mikrotik_monitor(self):
        """Stop the MikroTik connection monitor thread."""
        if self._mikrotik_monitor_thread:
            self._mikrotik_monitor_thread.stop()
            self._mikrotik_monitor_thread = None
            logger.info("MikroTik connection monitor stopped")
    
    def _on_mikrotik_connection_lost(self, error_msg: str):
        """Handle MikroTik connection lost signal from monitor thread."""
        logger.warning(f"MikroTik connection lost: {error_msg}")
        
        # Stop the monitor thread
        self._stop_mikrotik_monitor()
        
        # Clear client references
        self._ros_client = None
        self._peer_manager = None
        
        # Update UI to show disconnected state
        self.btn_mikrotik_connect.setVisible(True)
        self.btn_mikrotik_connect.setEnabled(True)
        self.btn_mikrotik_disconnect.setVisible(False)
        self.lbl_mikrotik_status.setText("MikroTik: Connection Lost ✗")
        self.lbl_mikrotik_status.setStyleSheet("color: #EF4444;")  # Red
        self._set_connected_state(False)
        self._update_status_bar("MikroTik connection lost")
        
        # Show notification to user if enabled
        if self._settings.value("notify_mikrotik_lost", True, type=bool):
            if self.tray_icon and self.tray_icon.isVisible():
                self.tray_icon.showMessage(
                    "VPN Mikro",
                    "MikroTik connection lost. Please reconnect.",
                    QSystemTrayIcon.MessageIcon.Warning,
                    3000
                )
    
    def _on_mikrotik_connection_ok(self):
        """Handle MikroTik connection OK signal from monitor thread."""
        # Connection is still alive - nothing to do
        pass
    
    def _on_mikrotik_connect(self):
        """Handle MikroTik Connect button click."""
        # Get the selected MikroTik profile from the combo
        mikrotik_index = self.mikrotik_combo.currentIndex()
        if mikrotik_index < 0 or mikrotik_index >= len(self._mikrotik_profiles):
            QMessageBox.warning(self, "No MikroTik", "Please select a MikroTik router first.")
            return
        
        # Use the MikroTik profile, not the VPN client profile
        mikrotik_profile = self._mikrotik_profiles[mikrotik_index]
        
        # Check if profile has host configured
        if not mikrotik_profile.host:
            QMessageBox.warning(self, "No Host", "This profile has no MikroTik host configured.")
            return
        
        self._update_status_bar("Connecting to MikroTik...")
        self.btn_mikrotik_connect.setEnabled(False)
        QApplication.processEvents()
        
        try:
            username, password = self._profile_manager.decrypt_credentials(mikrotik_profile)
            if not username or not password:
                QMessageBox.warning(self, "Credentials Required", "Please configure credentials in Settings for this MikroTik profile.")
                self.btn_mikrotik_connect.setEnabled(True)
                return
            
            self._ros_client = ROSClient(
                mikrotik_profile.host,
                mikrotik_profile.port,
                verify_tls=mikrotik_profile.verify_tls
            )
            self._ros_client.connect()
            success = self._ros_client.login(username, password)
            
            if success:
                # Set the MikroTik profile as current for peer operations
                self._current_profile = mikrotik_profile
                
                self._peer_manager = WGPeerManager(self._ros_client)
                self._device_manager = DeviceManager(self._profile_manager, self._peer_manager)
                
                # Update UI
                self.btn_mikrotik_connect.setVisible(False)
                self.btn_mikrotik_disconnect.setVisible(True)
                self.lbl_mikrotik_status.setText("MikroTik: Connected ✓")
                self.lbl_mikrotik_status.setStyleSheet("color: #22C55E;")
                self._set_connected_state(True)
                self._update_status_bar(f"Connected to MikroTik: {mikrotik_profile.host}")
                
                # Load peers from MikroTik and sync with profile FIRST
                # (before starting monitor to avoid race condition)
                self._sync_peers_from_mikrotik()
                
                # Start connection monitor thread AFTER sync completes
                self._start_mikrotik_monitor()
            else:
                self._ros_client.disconnect()
                self._ros_client = None
                QMessageBox.warning(self, "Failed", "Authentication failed.")
                self.btn_mikrotik_connect.setEnabled(True)
                self._update_status_bar("MikroTik: Auth failed")
        except Exception as e:
            if self._ros_client:
                try:
                    self._ros_client.disconnect()
                except:
                    pass
                self._ros_client = None
            QMessageBox.critical(self, "Error", f"Connection failed:\n{e}")
            self.btn_mikrotik_connect.setEnabled(True)
            self._update_status_bar("MikroTik: Connection failed")
    
    def _on_mikrotik_disconnect(self):
        """Handle MikroTik Disconnect button click."""
        # Use the cleanup function to disconnect and remove synced devices
        self._cleanup_mikrotik_connection()
        self._set_connected_state(False)
    
    def _sync_peers_from_mikrotik(self):
        """Sync peers from MikroTik to the current profile."""
        if not self._peer_manager or not self._current_profile:
            return
        
        try:
            # Get the selected interface
            interface = self._current_profile.selected_interface
            if not interface:
                logger.warning("No WireGuard interface selected")
                return
            
            # Get peers from MikroTik
            peers = self._peer_manager.list_peers(interface)
            logger.info(f"Found {len(peers)} peers on MikroTik interface {interface}")
            
            # Get existing device UUIDs in profile
            existing_peer_ids = {d.peer_id for d in self._current_profile.devices if d.peer_id}
            
            # Add new peers that don't exist in profile
            new_devices_count = 0
            for peer in peers:
                # WGPeer is a dataclass, use attributes not dict methods
                peer_id = peer.id
                if peer_id and peer_id not in existing_peer_ids:
                    # Create new device from peer
                    from vpnmikro.core.models import Device
                    from datetime import datetime
                    import uuid as uuid_module
                    
                    # Get allowed address, split to get IP without CIDR
                    allowed_ip = ''
                    if peer.allowed_address:
                        allowed_ip = peer.allowed_address.split('/')[0]
                    
                    device = Device(
                        uuid=str(uuid_module.uuid4()),
                        name=peer.comment if peer.comment else f"Peer-{peer_id}",
                        assigned_ip=allowed_ip,
                        peer_id=peer_id,
                        private_key_encrypted=b'',  # No private key from MikroTik
                        public_key=peer.public_key,
                        config_path='',  # No config file yet
                        enabled=not peer.disabled,
                        created_at=datetime.now()
                    )
                    self._current_profile.devices.append(device)
                    new_devices_count += 1
                    logger.info(f"Added device from MikroTik: {device.name}")
            
            if new_devices_count > 0:
                # Save profile with new devices
                self._profile_manager.save_profile(self._current_profile)
                self._update_status_bar(f"Synced {new_devices_count} new devices from MikroTik")
            
            # Reload profiles and update UI
            self._load_profiles()
            
            # Re-select the current profile in combos
            for i, profile in enumerate(self._mikrotik_profiles):
                if profile.name == self._current_profile.name:
                    self.mikrotik_combo.setCurrentIndex(i)
                    break
            
        except Exception as e:
            logger.error(f"Failed to sync peers from MikroTik: {e}")
            QMessageBox.warning(self, "Sync Warning", f"Could not sync all peers:\n{e}")
    
    def _on_new_profile(self):
        """Handle New Profile button click."""
        from vpnmikro.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(None, self._profile_manager, self, new_profile=True)
        if dialog.exec():
            self._load_profiles()
    
    def _on_edit_profile(self):
        """Handle Edit Profile button click."""
        if not self._current_profile:
            QMessageBox.warning(self, "No Profile", "Please select a profile first.")
            return
        self._on_settings_clicked()
    
    def _on_delete_profile(self):
        """Handle Delete Profile button click."""
        if not self._current_profile:
            QMessageBox.warning(self, "No Profile", "Please select a profile first.")
            return
        
        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Delete profile '{self._current_profile.name}'?\n\nThis will also delete all associated devices.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._profile_manager.delete_profile(self._current_profile.name)
                self._current_profile = None
                self._load_profiles()
                self._update_profile_card()
                self._update_devices_table()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete profile: {e}")
    
    def _on_add_device(self):
        """Handle Add Device button click."""
        # Check if MikroTik management is enabled
        mikrotik_enabled = self.chk_mikrotik_enabled.isChecked()
        
        if not mikrotik_enabled:
            # Open manual VPN wizard for client-only mode
            from vpnmikro.ui.manual_vpn_wizard import ManualVPNWizard
            wizard = ManualVPNWizard(self._profile_manager, self)
            if wizard.exec():
                # Reload profiles to show new device
                self._load_profiles()
                if wizard.created_device:
                    # Show success with public key
                    from PyQt6.QtWidgets import QDialog, QDialogButtonBox
                    
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle("Success")
                    msg_box.setIcon(QMessageBox.Icon.Information)
                    msg_box.setText(f"VPN profile '{wizard.created_device.name}' created successfully!")
                    msg_box.setInformativeText(f"Your Public Key:\n{wizard.created_device.public_key}")
                    msg_box.setDetailedText(f"Public Key (for server configuration):\n\n{wizard.created_device.public_key}")
                    
                    # Add copy button
                    copy_btn = msg_box.addButton("Copy Public Key", QMessageBox.ButtonRole.ActionRole)
                    msg_box.addButton(QMessageBox.StandardButton.Ok)
                    
                    msg_box.exec()
                    
                    if msg_box.clickedButton() == copy_btn:
                        QApplication.clipboard().setText(wizard.created_device.public_key)
            return
        
        # MikroTik mode - need connection
        if not self._ensure_connection():
            return
        
        if not self._current_profile.selected_interface:
            QMessageBox.warning(self, "Configuration Required", "Please configure WireGuard interface in Settings.")
            return
        
        name, ok = QInputDialog.getText(self, "Add Device", "Device name:", text="my-device")
        if not ok or not name:
            return
        
        name = name.strip()
        if not all(c.isalnum() or c in "-_" for c in name):
            QMessageBox.warning(self, "Invalid Name", "Use only letters, numbers, hyphens, and underscores.")
            return
        
        try:
            device = self._device_manager.create_device(self._current_profile, name)
            # Reload everything to get updated device list
            self._load_profiles()  # Refresh client combo
            QMessageBox.information(self, "Success", f"Device '{name}' created.\nIP: {device.assigned_ip}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create device: {e}")
    
    def _on_import_device(self):
        """Handle Import Device button click."""
        # If no profile exists, create a default one for imported devices
        if not self._current_profile:
            # Check if we have any profiles at all
            profiles = self._profile_manager.list_profiles()
            if profiles:
                # Use the first available profile
                self._current_profile = self._profile_manager.load_profile(profiles[0])
            else:
                # Create a default profile for imported devices
                from vpnmikro.core.models import Profile
                default_profile = Profile(
                    name="Imported-VPNs",
                    host="",  # No MikroTik host
                    port=8729,
                )
                self._profile_manager.save_profile(default_profile)
                self._current_profile = default_profile
                self._load_profiles()  # Refresh the UI
        
        from vpnmikro.ui.import_dialog import ImportConfigDialog
        dialog = ImportConfigDialog(self._current_profile, self._profile_manager, self)
        if dialog.exec():
            # Reload everything to get updated device list
            self._load_profiles()  # Refresh client combo
    
    def _on_connect_device(self):
        """Handle Connect Device button click."""
        # Check if "All VPN Clients" is selected
        if self.client_combo.currentIndex() == 0:
            QMessageBox.warning(
                self, "Select a Client",
                "Please select a specific VPN client to connect.\n\n"
                "The 'All VPN Clients' option is for viewing only."
            )
            return
        
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "No Selection", "Please select a device.")
            return
        
        if not self._device_manager:
            self._device_manager = DeviceManager(self._profile_manager)
        
        # Store device info for callback
        self._pending_device = device
        
        # Get tunnel name for verification
        from vpnmikro.core.wg_controller_win import WGController
        tunnel_name = WGController.make_tunnel_name(device.name)
        self._connected_tunnel_name = tunnel_name
        
        # Lock buttons during connection
        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setVisible(False)
        self.client_combo.setEnabled(False)
        self.status_pill.setText("Connecting...")
        self.status_pill.setProperty("status", "connecting")
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)
        self._update_status_bar("Connecting...")
        
        # Get connection timeout from settings
        connect_timeout = self._settings.value("vpn_connect_timeout", 5, type=int)
        
        # Run connect in background thread with verification
        self._vpn_worker = VPNWorkerThread(
            self._device_manager, self._current_profile, device.uuid, "connect", tunnel_name, connect_timeout
        )
        self._vpn_worker.finished.connect(self._on_connect_finished)
        self._vpn_worker.status_update.connect(self._on_connect_status_update)
        self._vpn_worker.start()
    
    def _on_connect_status_update(self, status: str):
        """Handle status update during connection."""
        self._update_status_bar(status)
    
    def _on_connect_finished(self, success: bool, message: str):
        """Handle connect operation completion."""
        device = getattr(self, '_pending_device', None)
        
        if success:
            # Tunnel name already set in _on_connect_device
            self._is_connected = True
            
            # Connection successful - update UI
            row = self.devices_table.currentRow()
            if row >= 0:
                status_item = self.devices_table.item(row, 2)
                if status_item:
                    status_item.setText("Active")
            
            device_name = device.name if device else "VPN"
            self._update_status_bar(f"VPN Connected: {device_name}")
            self._update_tray_state(True)
            
            # Start connection monitor
            self._start_vpn_monitor()
            
            # Update UI - show disconnect, hide connect
            self.btn_connect.setVisible(False)
            self.btn_disconnect.setVisible(True)
            self.btn_disconnect.setEnabled(True)
            self.client_combo.setEnabled(False)
            self.status_pill.setText("Connected")
            self.status_pill.setProperty("status", "connected")
            self.status_pill.style().unpolish(self.status_pill)
            self.status_pill.style().polish(self.status_pill)
        else:
            # Clear tunnel name on failure
            self._connected_tunnel_name = None
            
            # Handle errors
            if message == "permission_cancelled":
                QMessageBox.warning(
                    self, "Cancelled",
                    "Administrator approval was cancelled.\n"
                    "VPN connection requires administrator privileges."
                )
            elif message.startswith("admin_required:"):
                QMessageBox.warning(self, "Admin Required", message[15:])
            elif message.startswith("verify_failed:"):
                # Connection verification failed - disconnect the tunnel
                error_detail = message[14:]
                try:
                    if device and self._device_manager:
                        self._device_manager.disconnect_device(self._current_profile, device.uuid)
                except Exception:
                    pass
                
                QMessageBox.warning(
                    self, "Connection Failed",
                    f"VPN tunnel started but verification failed.\n\n"
                    f"{error_detail}\n\n"
                    "Possible causes:\n"
                    "• VPN server is not reachable\n"
                    "• Firewall blocking traffic\n"
                    "• Invalid configuration\n"
                    "• Server-side issue"
                )
            else:
                error_msg = message[6:] if message.startswith("error:") else message
                QMessageBox.critical(self, "Error", f"Failed to connect: {error_msg}")
            self._reset_connect_buttons()
        
        # Cleanup
        self._pending_device = None
        self._vpn_worker = None
    
    def _reset_connect_buttons(self):
        """Reset buttons to disconnected state."""
        self.btn_connect.setVisible(True)
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setVisible(False)
        self.client_combo.setEnabled(True)  # Unlock combo when disconnected
        self.status_pill.setText("Disconnected")
        self.status_pill.setProperty("status", "disconnected")
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)
    
    def _on_disconnect_device(self):
        """Handle Disconnect Device button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "No Selection", "Please select a device.")
            return
        
        if not self._device_manager:
            self._device_manager = DeviceManager(self._profile_manager)
        
        # Stop VPN monitor FIRST to prevent interference
        self._stop_vpn_monitor()
        
        # Store device info for callback
        self._pending_device = device
        
        # Lock buttons during disconnection
        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(False)
        self.status_pill.setText("Disconnecting...")
        self.status_pill.setProperty("status", "connecting")
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)
        self._update_status_bar("Disconnecting...")
        
        # Run disconnect in background thread to avoid UI freeze
        self._vpn_worker = VPNWorkerThread(
            self._device_manager, self._current_profile, device.uuid, "disconnect"
        )
        self._vpn_worker.finished.connect(self._on_disconnect_finished)
        self._vpn_worker.start()
    
    def _on_disconnect_finished(self, success: bool, message: str):
        """Handle disconnect operation completion."""
        if success:
            # Update table status
            row = self.devices_table.currentRow()
            if row >= 0:
                status_item = self.devices_table.item(row, 2)
                if status_item:
                    status_item.setText("Disconnected")
                traffic_item = self.devices_table.item(row, 4)
                if traffic_item:
                    traffic_item.setText("—")
            
            self._update_status_bar("VPN Disconnected")
            self._update_tray_state(False)
            
            # Clear tunnel name
            self._connected_tunnel_name = None
            self._is_connected = False
            
            # Reset to disconnected state
            self._reset_connect_buttons()
        else:
            # Handle errors - keep in connected state
            if message == "permission_cancelled":
                QMessageBox.warning(
                    self, "Cancelled",
                    "Administrator approval was cancelled."
                )
            elif message.startswith("admin_required:"):
                QMessageBox.warning(self, "Admin Required", message[15:])
            else:
                error_msg = message[6:] if message.startswith("error:") else message
                QMessageBox.critical(self, "Error", f"Failed to disconnect: {error_msg}")
            
            # Keep in connected state
            self.btn_connect.setVisible(False)
            self.btn_disconnect.setVisible(True)
            self.btn_disconnect.setEnabled(True)
        
        # Cleanup
        self._pending_device = None
        self._vpn_worker = None
    
    def _on_export_device(self):
        """Handle Export button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "No Selection", "Please select a device.")
            return
        
        from vpnmikro.ui.export_dialog import ExportDialog
        dialog = ExportDialog(device.name, device.config_path, self)
        dialog.exec()
    
    def _on_device_settings(self):
        """Handle Device Settings button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "No Selection", "Please select a device.")
            return
        
        # Read config content
        config_content = ""
        if device.config_path:
            config_path = Path(device.config_path)
            if config_path.exists():
                try:
                    config_content = config_path.read_text(encoding="utf-8")
                except Exception:
                    pass
        
        from vpnmikro.ui.device_settings_dialog import DeviceSettingsDialog
        dialog = DeviceSettingsDialog(device, config_content, self)
        if dialog.exec():
            # Refresh device list if settings were saved
            self._update_devices_table()
    
    def _on_device_double_click(self, row: int, col: int):
        """Handle double-click on device row - open settings."""
        self._on_device_settings()
    
    def _on_device_row_clicked(self, row: int, col: int):
        """Handle single click on device row - update combo box."""
        if row < 0 or row >= len(self._devices):
            return
        
        device = self._devices[row]
        
        # Find this device in the client combo and select it
        for i, client_entry in enumerate(self._all_clients):
            if client_entry is not None:
                profile, entry_device = client_entry
                if entry_device.uuid == device.uuid:
                    # Block signals to avoid recursive calls
                    self.client_combo.blockSignals(True)
                    self.client_combo.setCurrentIndex(i)
                    self.client_combo.blockSignals(False)
                    
                    # Also update current profile
                    self._current_profile = profile
                    self._profile_manager.set_current_profile(profile.name)
                    
                    # Update MikroTik combo if profile has MikroTik
                    if profile.host:
                        for j, mikrotik_profile in enumerate(self._mikrotik_profiles):
                            if mikrotik_profile.name == profile.name:
                                self.mikrotik_combo.blockSignals(True)
                                self.mikrotik_combo.setCurrentIndex(j)
                                self.mikrotik_combo.blockSignals(False)
                                self._update_profile_card()
                                break
                    break
    
    def _on_show_qr(self):
        """Handle QR button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "No Selection", "Please select a device.")
            return
        
        try:
            config_path = Path(device.config_path)
            if not config_path.exists():
                QMessageBox.warning(self, "Error", "Config file not found.")
                return
            
            content = config_path.read_text(encoding="utf-8")
            
            from vpnmikro.ui.qr_dialog import QRCodeDialog
            dialog = QRCodeDialog(device.name, content, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to show QR: {e}")
    
    def _on_copy_key(self):
        """Handle Copy Key button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "No Selection", "Please select a device.")
            return
        
        QApplication.clipboard().setText(device.public_key)
        self._update_status_bar("Public key copied to clipboard")
    
    def _on_delete_device(self):
        """Handle Delete Device button click."""
        device = self._get_selected_device()
        if not device:
            QMessageBox.warning(self, "No Selection", "Please select a device.")
            return
        
        # Find the profile that contains this device
        device_profile = None
        for profile_name in self._profile_manager.list_profiles():
            try:
                profile = self._profile_manager.load_profile(profile_name)
                for d in profile.devices:
                    if d.uuid == device.uuid:
                        device_profile = profile
                        break
                if device_profile:
                    break
            except Exception:
                pass
        
        if not device_profile:
            QMessageBox.warning(self, "Error", "Could not find profile for this device.")
            return
        
        # Check if it's a local-only device (imported or manual without MikroTik)
        is_imported = device.peer_id == "imported"
        is_manual = not device_profile.host  # No MikroTik host = manual profile
        is_local_only = is_imported or is_manual
        
        if is_local_only:
            msg = f"Delete device '{device.name}'?\n\nThis will remove the local config file."
        else:
            msg = f"Delete device '{device.name}'?\n\nThis will remove the peer from MikroTik."
        
        reply = QMessageBox.question(
            self, "Delete Device",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            if is_local_only:
                # Delete local device (no MikroTik needed)
                # Remove config file
                if device.config_path:
                    config_path = Path(device.config_path)
                    if config_path.exists():
                        config_path.unlink()
                
                # Remove from profile
                device_profile.devices = [
                    d for d in device_profile.devices if d.uuid != device.uuid
                ]
                self._profile_manager.save_profile(device_profile)
            else:
                # Delete MikroTik device - requires connection
                self._current_profile = device_profile
                if not self._ensure_connection():
                    return
                self._device_manager.delete_device(device_profile, device.uuid)
            
            # Reload everything to get updated device list
            self._load_profiles()  # Refresh client combo
            self._update_status_bar(f"Device '{device.name}' deleted")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete device: {e}")
    
def run_modern_app():
    """Run the modern VPN Mikro application."""
    import tempfile
    import os
    
    # Single instance check using a lock file
    lock_file = Path(tempfile.gettempdir()) / "vpnmikro.lock"
    
    # Try to acquire lock
    try:
        if lock_file.exists():
            # Check if the process is still running
            try:
                pid = int(lock_file.read_text().strip())
                # Check if process exists (Windows)
                import ctypes
                kernel32 = ctypes.windll.kernel32
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    # Process is running - show message and exit
                    app = QApplication(sys.argv)
                    msg = QMessageBox()
                    msg.setWindowTitle("VPN Mikro")
                    msg.setText("Η εφαρμογή είναι ήδη ανοιχτή.\nThe application is already running.")
                    msg.setIcon(QMessageBox.Icon.Information)
                    msg.setWindowIcon(get_window_icon())
                    msg.exec()
                    sys.exit(0)
            except (ValueError, OSError):
                pass  # Lock file is stale, continue
        
        # Write our PID to lock file
        lock_file.write_text(str(os.getpid()))
    except Exception as e:
        logger.warning(f"Could not create lock file: {e}")
    
    app = QApplication(sys.argv)
    app.setApplicationName("VPN Mikro")
    
    # Clean up lock file on exit
    def cleanup():
        try:
            if lock_file.exists():
                lock_file.unlink()
        except Exception:
            pass
    
    import atexit
    atexit.register(cleanup)
    
    # Check for first run
    from vpnmikro.ui.wizard import check_first_run, SetupWizard
    
    if check_first_run():
        logger.info("First run detected, launching setup wizard")
        # Apply theme to wizard too
        app.setStyleSheet(load_theme())
        
        wizard = SetupWizard()
        result = wizard.exec()
        
        if result != wizard.DialogCode.Accepted:
            cleanup()
            sys.exit(0)
    
    window = ModernMainWindow()
    window.show()
    
    sys.exit(app.exec())
