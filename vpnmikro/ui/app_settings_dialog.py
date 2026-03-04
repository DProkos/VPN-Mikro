"""Application settings dialog for VPN Mikro.

Contains general application settings like:
- Check for updates
- Startup with Windows
- Data paths
- About information
"""

import os
import sys
import winreg
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QCheckBox, QLineEdit, QGroupBox,
    QMessageBox, QFileDialog, QProgressDialog, QSpinBox, QFormLayout
)
from PyQt6.QtCore import Qt

from vpnmikro.ui.assets import get_window_icon, load_theme, icon, Icons, ICON_SIZE_MD
from vpnmikro.ui.about_dialog import VERSION, AUTHOR, COPYRIGHT_YEAR, APP_DESCRIPTION
from vpnmikro.core.logger import get_logger

logger = get_logger(__name__)

# Registry key for startup
STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "VPNMikro"


class AppSettingsDialog(QDialog):
    """Application settings dialog.
    
    Tabs:
    - General: Startup, updates
    - Paths: Data locations
    - About: Version info
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application Settings")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        self.setWindowIcon(get_window_icon())
        self.setStyleSheet(load_theme())
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # General tab
        self.tabs.addTab(self._create_general_tab(), "General")
        
        # Advanced tab (timers, etc.)
        self.tabs.addTab(self._create_advanced_tab(), "Advanced")
        
        # Paths tab
        self.tabs.addTab(self._create_paths_tab(), "Paths")
        
        # About tab
        self.tabs.addTab(self._create_about_tab(), "About")
        
        layout.addWidget(self.tabs)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("Save")
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.clicked.connect(self._save_settings)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
    
    def _create_general_tab(self) -> QWidget:
        """Create the General settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Startup group
        startup_group = QGroupBox("Startup")
        startup_layout = QVBoxLayout(startup_group)
        
        self.chk_start_with_windows = QCheckBox("Start VPN Mikro with Windows")
        self.chk_start_with_windows.setToolTip("Automatically start the application when Windows starts")
        startup_layout.addWidget(self.chk_start_with_windows)
        
        self.chk_start_minimized = QCheckBox("Start minimized to tray")
        self.chk_start_minimized.setToolTip("Start the application minimized to system tray")
        startup_layout.addWidget(self.chk_start_minimized)
        
        layout.addWidget(startup_group)
        
        # Updates group
        updates_group = QGroupBox("Updates")
        updates_layout = QVBoxLayout(updates_group)
        
        self.chk_auto_update = QCheckBox("Check for updates on startup")
        self.chk_auto_update.setToolTip("Automatically check for new versions when the application starts")
        self.chk_auto_update.setChecked(True)
        updates_layout.addWidget(self.chk_auto_update)
        
        # Check now button
        btn_row = QHBoxLayout()
        self.btn_check_updates = QPushButton(" Check for Updates Now")
        self.btn_check_updates.setIcon(icon(Icons.REFRESH))
        self.btn_check_updates.setIconSize(ICON_SIZE_MD)
        self.btn_check_updates.clicked.connect(self._check_for_updates)
        btn_row.addWidget(self.btn_check_updates)
        btn_row.addStretch()
        updates_layout.addLayout(btn_row)
        
        # Version info
        version_label = QLabel(f"Current version: {VERSION}")
        version_label.setObjectName("MutedLabel")
        updates_layout.addWidget(version_label)
        
        layout.addWidget(updates_group)
        
        layout.addStretch()
        return widget
    
    def _create_advanced_tab(self) -> QWidget:
        """Create the Advanced settings tab with timers and timeouts."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Connection Monitoring group
        monitor_group = QGroupBox("Connection Monitoring")
        monitor_layout = QFormLayout(monitor_group)
        
        # MikroTik connection check interval
        self.spin_mikrotik_interval = QSpinBox()
        self.spin_mikrotik_interval.setRange(3, 60)
        self.spin_mikrotik_interval.setValue(5)
        self.spin_mikrotik_interval.setSuffix(" seconds")
        self.spin_mikrotik_interval.setToolTip("How often to check if MikroTik connection is alive")
        monitor_layout.addRow("MikroTik check interval:", self.spin_mikrotik_interval)
        
        # VPN stats update interval
        self.spin_stats_interval = QSpinBox()
        self.spin_stats_interval.setRange(1, 10)
        self.spin_stats_interval.setValue(1)
        self.spin_stats_interval.setSuffix(" seconds")
        self.spin_stats_interval.setToolTip("How often to update VPN traffic statistics")
        monitor_layout.addRow("Stats update interval:", self.spin_stats_interval)
        
        layout.addWidget(monitor_group)
        
        # Timeouts group
        timeout_group = QGroupBox("Timeouts")
        timeout_layout = QFormLayout(timeout_group)
        
        # Connection timeout
        self.spin_connect_timeout = QSpinBox()
        self.spin_connect_timeout.setRange(5, 60)
        self.spin_connect_timeout.setValue(10)
        self.spin_connect_timeout.setSuffix(" seconds")
        self.spin_connect_timeout.setToolTip("Maximum time to wait for VPN handshake")
        timeout_layout.addRow("VPN connection timeout:", self.spin_connect_timeout)
        
        # MikroTik API timeout
        self.spin_api_timeout = QSpinBox()
        self.spin_api_timeout.setRange(5, 30)
        self.spin_api_timeout.setValue(10)
        self.spin_api_timeout.setSuffix(" seconds")
        self.spin_api_timeout.setToolTip("Maximum time to wait for MikroTik API response")
        timeout_layout.addRow("MikroTik API timeout:", self.spin_api_timeout)
        
        layout.addWidget(timeout_group)
        
        # Notifications group
        notif_group = QGroupBox("Notifications")
        notif_layout = QVBoxLayout(notif_group)
        
        self.chk_notify_connect = QCheckBox("Show notification on VPN connect")
        self.chk_notify_connect.setChecked(True)
        notif_layout.addWidget(self.chk_notify_connect)
        
        self.chk_notify_disconnect = QCheckBox("Show notification on VPN disconnect")
        self.chk_notify_disconnect.setChecked(False)
        notif_layout.addWidget(self.chk_notify_disconnect)
        
        self.chk_notify_mikrotik_lost = QCheckBox("Show notification when MikroTik connection lost")
        self.chk_notify_mikrotik_lost.setChecked(True)
        notif_layout.addWidget(self.chk_notify_mikrotik_lost)
        
        layout.addWidget(notif_group)
        
        # Reset button
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        self.btn_reset_defaults = QPushButton(" Reset to Defaults")
        self.btn_reset_defaults.setIcon(icon(Icons.REFRESH))
        self.btn_reset_defaults.setIconSize(ICON_SIZE_MD)
        self.btn_reset_defaults.setToolTip("Reset all advanced settings to default values")
        self.btn_reset_defaults.clicked.connect(self._reset_to_defaults)
        reset_layout.addWidget(self.btn_reset_defaults)
        layout.addLayout(reset_layout)
        
        layout.addStretch()
        return widget
    
    def _reset_to_defaults(self):
        """Reset all advanced settings to default values."""
        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            "Are you sure you want to reset all settings to default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Reset Connection Monitoring
            self.spin_mikrotik_interval.setValue(5)
            self.spin_stats_interval.setValue(2)
            
            # Reset Timeouts
            self.spin_connect_timeout.setValue(5)
            self.spin_api_timeout.setValue(10)
            
            # Reset Notifications
            self.chk_notify_connect.setChecked(True)
            self.chk_notify_disconnect.setChecked(False)
            self.chk_notify_mikrotik_lost.setChecked(True)
            
            # Reset General settings
            self.chk_start_minimized.setChecked(False)
            self.chk_auto_update.setChecked(True)
            
            QMessageBox.information(
                self,
                "Settings Reset",
                "All settings have been reset to default values.\n\n"
                "Click 'Save' to apply the changes."
            )
    
    def _create_paths_tab(self) -> QWidget:
        """Create the Paths settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Paths info group
        paths_group = QGroupBox("Data Locations")
        paths_layout = QVBoxLayout(paths_group)
        
        # Profiles path
        profiles_row = QHBoxLayout()
        profiles_row.addWidget(QLabel("Profiles:"))
        program_data = os.environ.get("ProgramData", "C:\\ProgramData")
        self.profiles_path = QLineEdit(f"{program_data}\\VPNMikro\\data")
        self.profiles_path.setReadOnly(True)
        profiles_row.addWidget(self.profiles_path)
        btn_open_profiles = QPushButton("Open")
        btn_open_profiles.clicked.connect(lambda: self._open_folder(self.profiles_path.text()))
        profiles_row.addWidget(btn_open_profiles)
        paths_layout.addLayout(profiles_row)
        
        # Configs path
        configs_row = QHBoxLayout()
        configs_row.addWidget(QLabel("Configs:"))
        self.configs_path = QLineEdit(f"{program_data}\\VPNMikro\\configs")
        self.configs_path.setReadOnly(True)
        configs_row.addWidget(self.configs_path)
        btn_open_configs = QPushButton("Open")
        btn_open_configs.clicked.connect(lambda: self._open_folder(self.configs_path.text()))
        configs_row.addWidget(btn_open_configs)
        paths_layout.addLayout(configs_row)
        
        # Logs path
        logs_row = QHBoxLayout()
        logs_row.addWidget(QLabel("Logs:"))
        self.logs_path = QLineEdit(f"{program_data}\\VPNMikro\\logs")
        self.logs_path.setReadOnly(True)
        logs_row.addWidget(self.logs_path)
        btn_open_logs = QPushButton("Open")
        btn_open_logs.clicked.connect(lambda: self._open_folder(self.logs_path.text()))
        logs_row.addWidget(btn_open_logs)
        paths_layout.addLayout(logs_row)
        
        # Temp path
        temp_row = QHBoxLayout()
        temp_row.addWidget(QLabel("Temp:"))
        import tempfile
        self.temp_path = QLineEdit(tempfile.gettempdir())
        self.temp_path.setReadOnly(True)
        temp_row.addWidget(self.temp_path)
        btn_open_temp = QPushButton("Open")
        btn_open_temp.clicked.connect(lambda: self._open_folder(self.temp_path.text()))
        temp_row.addWidget(btn_open_temp)
        paths_layout.addLayout(temp_row)
        
        layout.addWidget(paths_group)
        
        # Note
        note_label = QLabel(
            "<i>Note: These paths are fixed and cannot be changed. "
            "Click 'Open' to view the folder contents.</i>"
        )
        note_label.setObjectName("MutedLabel")
        note_label.setWordWrap(True)
        layout.addWidget(note_label)
        
        layout.addStretch()
        return widget
    
    def _create_about_tab(self) -> QWidget:
        """Create the About tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Logo and title
        from PyQt6.QtGui import QPixmap
        
        header = QHBoxLayout()
        
        logo_label = QLabel()
        logo_path = Path(__file__).parent.parent.parent / "logo" / "logo_no_BG.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                logo_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(logo_label)
        
        title_layout = QVBoxLayout()
        title = QLabel("VPN Mikro")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #7C3AED;")
        title_layout.addWidget(title)
        
        version = QLabel(f"Version {VERSION}")
        version.setObjectName("MutedLabel")
        title_layout.addWidget(version)
        
        header.addLayout(title_layout)
        header.addStretch()
        
        layout.addLayout(header)
        layout.addSpacing(10)
        
        # Description
        desc = QLabel(APP_DESCRIPTION)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        layout.addSpacing(10)
        
        # Copyright and License
        copyright_label = QLabel(
            f"<b>© {COPYRIGHT_YEAR} {AUTHOR}</b><br>"
            f"All rights reserved.<br><br>"
            f"<b>License:</b> Proprietary Software<br>"
            f"This software is the exclusive property of {AUTHOR}.<br>"
            f"Unauthorized copying, modification, distribution, or use<br>"
            f"of this software is strictly prohibited.<br><br>"
            f"<span style='color: #9AA4B2;'>"
            f"<b>Third-Party Notices:</b><br>"
            f"• WireGuard® is a registered trademark of Jason A. Donenfeld.<br>"
            f"• MikroTik® is a registered trademark of MikroTikls SIA."
            f"</span>"
        )
        copyright_label.setWordWrap(True)
        copyright_label.setStyleSheet("padding: 10px; background: #171A21; border-radius: 8px;")
        layout.addWidget(copyright_label)
        
        # Contact info
        contact_label = QLabel(
            f"<span style='color: #9AA4B2;'>"
            f"<b>Developer:</b> {AUTHOR}"
            f"</span>"
        )
        contact_label.setWordWrap(True)
        contact_label.setStyleSheet("padding: 10px; margin-top: 5px;")
        layout.addWidget(contact_label)
        
        layout.addStretch()
        return widget
    
    def _load_settings(self):
        """Load current settings."""
        from PyQt6.QtCore import QSettings
        settings = QSettings("VPNMikro", "VPNMikro")
        
        # Load startup settings
        self.chk_start_with_windows.setChecked(self._is_startup_enabled())
        self.chk_start_minimized.setChecked(settings.value("start_minimized", False, type=bool))
        self.chk_auto_update.setChecked(settings.value("auto_check_updates", True, type=bool))
        
        # Load advanced settings
        self.spin_mikrotik_interval.setValue(settings.value("mikrotik_check_interval", 5, type=int))
        self.spin_stats_interval.setValue(settings.value("stats_update_interval", 1, type=int))
        self.spin_connect_timeout.setValue(settings.value("vpn_connect_timeout", 10, type=int))
        self.spin_api_timeout.setValue(settings.value("mikrotik_api_timeout", 10, type=int))
        
        # Load notification settings
        self.chk_notify_connect.setChecked(settings.value("notify_vpn_connect", True, type=bool))
        self.chk_notify_disconnect.setChecked(settings.value("notify_vpn_disconnect", False, type=bool))
        self.chk_notify_mikrotik_lost.setChecked(settings.value("notify_mikrotik_lost", True, type=bool))
    
    def _save_settings(self):
        """Save settings and close dialog."""
        from PyQt6.QtCore import QSettings
        settings = QSettings("VPNMikro", "VPNMikro")
        
        # Save startup with Windows
        if self.chk_start_with_windows.isChecked():
            self._enable_startup()
        else:
            self._disable_startup()
        
        # Save general settings
        settings.setValue("start_minimized", self.chk_start_minimized.isChecked())
        settings.setValue("auto_check_updates", self.chk_auto_update.isChecked())
        
        # Save advanced settings
        settings.setValue("mikrotik_check_interval", self.spin_mikrotik_interval.value())
        settings.setValue("stats_update_interval", self.spin_stats_interval.value())
        settings.setValue("vpn_connect_timeout", self.spin_connect_timeout.value())
        settings.setValue("mikrotik_api_timeout", self.spin_api_timeout.value())
        
        # Save notification settings
        settings.setValue("notify_vpn_connect", self.chk_notify_connect.isChecked())
        settings.setValue("notify_vpn_disconnect", self.chk_notify_disconnect.isChecked())
        settings.setValue("notify_mikrotik_lost", self.chk_notify_mikrotik_lost.isChecked())
        
        self.accept()
    
    def _is_startup_enabled(self) -> bool:
        """Check if startup with Windows is enabled."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, APP_NAME)
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception:
            return False
    
    def _enable_startup(self):
        """Enable startup with Windows."""
        try:
            # Get executable path
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = f'"{sys.executable}" "{Path(__file__).parent.parent.parent / "vpnmikro.py"}"'
            
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(key)
            logger.info("Startup with Windows enabled")
        except Exception as e:
            logger.error(f"Failed to enable startup: {e}")
            QMessageBox.warning(self, "Error", f"Failed to enable startup with Windows:\n{e}")
    
    def _disable_startup(self):
        """Disable startup with Windows."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_WRITE)
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass  # Already disabled
            winreg.CloseKey(key)
            logger.info("Startup with Windows disabled")
        except Exception as e:
            logger.error(f"Failed to disable startup: {e}")
    
    def _open_folder(self, path: str):
        """Open a folder in Windows Explorer."""
        folder = Path(path)
        if folder.exists():
            os.startfile(str(folder))
        else:
            # Create folder if it doesn't exist
            try:
                folder.mkdir(parents=True, exist_ok=True)
                os.startfile(str(folder))
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open folder:\n{e}")
    
    def _check_for_updates(self):
        """Check for updates."""
        self.btn_check_updates.setEnabled(False)
        self.btn_check_updates.setText(" Checking...")
        
        from vpnmikro.ui.about_dialog import UpdateCheckThread
        
        self._update_thread = UpdateCheckThread(VERSION)
        self._update_thread.update_available.connect(self._on_update_check_complete)
        self._update_thread.error_occurred.connect(self._on_update_check_error)
        self._update_thread.start()
    
    def _on_update_check_complete(self, update_info):
        """Handle update check completion."""
        self.btn_check_updates.setEnabled(True)
        self.btn_check_updates.setText(" Check for Updates Now")
        
        if update_info is None:
            QMessageBox.information(
                self,
                "No Updates",
                f"You are running the latest version ({VERSION})."
            )
        else:
            reply = QMessageBox.question(
                self,
                "Update Available",
                f"<b>A new version is available!</b><br><br>"
                f"<b>Current version:</b> {VERSION}<br>"
                f"<b>New version:</b> {update_info.version}<br>"
                f"<b>Release date:</b> {update_info.release_date}<br><br>"
                f"<b>Changelog:</b><br>{update_info.changelog.replace(chr(10), '<br>')}<br><br>"
                f"Do you want to download and install the update?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._download_update(update_info)
    
    def _on_update_check_error(self, error_msg):
        """Handle update check error."""
        self.btn_check_updates.setEnabled(True)
        self.btn_check_updates.setText(" Check for Updates Now")
        
        QMessageBox.warning(
            self,
            "Update Check Failed",
            f"Could not check for updates:\n{error_msg}"
        )
    
    def _download_update(self, update_info):
        """Download the update."""
        from vpnmikro.ui.about_dialog import DownloadThread
        
        self._progress_dialog = QProgressDialog(
            "Downloading update...", "Cancel", 0, 100, self
        )
        self._progress_dialog.setWindowTitle("Downloading Update")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setValue(0)
        
        self._download_thread = DownloadThread(update_info)
        self._download_thread.progress.connect(self._on_download_progress)
        self._download_thread.finished.connect(self._on_download_complete)
        self._download_thread.error_occurred.connect(self._on_download_error)
        self._download_thread.start()
    
    def _on_download_progress(self, downloaded, total):
        """Update download progress."""
        if total > 0:
            percent = int((downloaded / total) * 100)
            self._progress_dialog.setValue(percent)
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self._progress_dialog.setLabelText(
                f"Downloading update... {downloaded_mb:.1f} MB / {total_mb:.1f} MB"
            )
    
    def _on_download_complete(self, installer_path):
        """Handle download completion."""
        self._progress_dialog.close()
        
        if installer_path is None:
            QMessageBox.warning(self, "Download Failed", "Failed to download the update.")
            return
        
        reply = QMessageBox.question(
            self,
            "Download Complete",
            f"Update downloaded!\n\nDo you want to install it now?\nThe application will close.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            from vpnmikro.core.updater import install_update
            if install_update(installer_path):
                from PyQt6.QtWidgets import QApplication
                QApplication.quit()
    
    def _on_download_error(self, error_msg):
        """Handle download error."""
        self._progress_dialog.close()
        QMessageBox.warning(self, "Download Failed", f"Failed to download:\n{error_msg}")
