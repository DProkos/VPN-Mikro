"""About dialog with version and license information."""

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTextEdit, QWidget, QMessageBox, QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon

from vpnmikro.ui.assets import get_window_icon, load_theme

# Application version
VERSION = "0.0.5"

# Copyright information
COPYRIGHT_YEAR = "2024-2025"
AUTHOR = "Dionisis Prokos"
APP_DESCRIPTION = "WireGuard VPN Manager for MikroTik Routers"


class UpdateCheckThread(QThread):
    """Background thread for checking updates."""
    update_available = pyqtSignal(object)  # UpdateInfo or None
    error_occurred = pyqtSignal(str)
    
    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version
    
    def run(self):
        try:
            from vpnmikro.core.updater import check_for_updates
            update_info = check_for_updates(self.current_version)
            self.update_available.emit(update_info)
        except Exception as e:
            self.error_occurred.emit(str(e))


class DownloadThread(QThread):
    """Background thread for downloading updates."""
    progress = pyqtSignal(int, int)  # downloaded, total
    finished = pyqtSignal(object)  # Path or None
    error_occurred = pyqtSignal(str)
    
    def __init__(self, update_info):
        super().__init__()
        self.update_info = update_info
    
    def run(self):
        try:
            from vpnmikro.core.updater import download_update
            path = download_update(self.update_info, self._progress_callback)
            self.finished.emit(path)
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def _progress_callback(self, downloaded, total):
        self.progress.emit(downloaded, total)


class AboutDialog(QDialog):
    """About dialog showing version and license information.
    
    Displays:
    - Application name and version
    - Logo
    - Copyright information
    - License information from licenses/ folder
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About VPN Mikro")
        self.setMinimumSize(550, 450)
        self.setModal(True)
        self.setWindowIcon(get_window_icon())
        self.setStyleSheet(load_theme())
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the about dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header with logo and title
        header_layout = QHBoxLayout()
        
        # Logo
        logo_label = QLabel()
        logo_path = Path(__file__).parent.parent.parent / "logo" / "logo_no_BG.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                logo_label.setPixmap(pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(logo_label)
        
        # Title and version
        title_layout = QVBoxLayout()
        
        title_label = QLabel("VPN Mikro")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #7C3AED;")
        title_layout.addWidget(title_label)
        
        version_label = QLabel(f"Version {VERSION}")
        version_label.setStyleSheet("font-size: 14px; color: #9AA4B2;")
        title_layout.addWidget(version_label)
        
        desc_label = QLabel(APP_DESCRIPTION)
        desc_label.setStyleSheet("font-size: 12px; color: #E6E6E6;")
        title_layout.addWidget(desc_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        layout.addSpacing(10)
        
        # Copyright section
        copyright_frame = QLabel()
        copyright_frame.setText(
            f"<p style='color: #E6E6E6;'>"
            f"<b>© {COPYRIGHT_YEAR} {AUTHOR}</b><br>"
            f"All rights reserved.<br><br>"
            f"<span style='color: #9AA4B2;'>"
            f"This software is provided for managing WireGuard VPN connections<br>"
            f"through MikroTik routers or as standalone VPN client.</span>"
            f"</p>"
        )
        copyright_frame.setWordWrap(True)
        copyright_frame.setStyleSheet("padding: 10px; background: #171A21; border-radius: 8px;")
        layout.addWidget(copyright_frame)
        
        layout.addSpacing(10)
        
        # License tabs
        tab_widget = QTabWidget()
        
        # About tab
        about_text = QTextEdit()
        about_text.setHtml(f"""
            <h3 style="color: #7C3AED;">VPN Mikro</h3>
            <p><b>Version:</b> {VERSION}</p>
            <p><b>Author:</b> {AUTHOR}</p>
            <p><b>Copyright:</b> © {COPYRIGHT_YEAR}</p>
            
            <h4 style="color: #7C3AED;">Description</h4>
            <p>{APP_DESCRIPTION}</p>
            
            <h4 style="color: #7C3AED;">Features</h4>
            <ul>
                <li>MikroTik router integration via API</li>
                <li>WireGuard tunnel management</li>
                <li>QR code generation for mobile devices</li>
                <li>Import/Export configurations</li>
                <li>Secure credential storage (Windows DPAPI)</li>
            </ul>
            
            <h4 style="color: #7C3AED;">Trademarks</h4>
            <p style="color: #9AA4B2; font-size: 11px;">
                WireGuard® is a registered trademark of Jason A. Donenfeld.<br>
                MikroTik® is a registered trademark of MikroTikls SIA.
            </p>
        """)
        about_text.setReadOnly(True)
        tab_widget.addTab(about_text, "About")
        
        # Load licenses from licenses/ folder
        licenses_dir = Path(__file__).parent.parent.parent / "licenses"
        if licenses_dir.exists():
            for license_file in sorted(licenses_dir.glob("*.txt")):
                try:
                    content = license_file.read_text(encoding="utf-8")
                    tab_name = license_file.stem.replace("LICENSE-", "").replace("-", " ").title()
                    
                    text_edit = QTextEdit()
                    text_edit.setPlainText(content)
                    text_edit.setReadOnly(True)
                    
                    tab_widget.addTab(text_edit, tab_name)
                except Exception:
                    pass
        
        layout.addWidget(tab_widget)
        
        # Buttons row
        button_layout = QHBoxLayout()
        
        # Check for Updates button
        self.update_button = QPushButton("Check for Updates")
        self.update_button.clicked.connect(self._check_for_updates)
        self.update_button.setMinimumWidth(140)
        button_layout.addWidget(self.update_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setMinimumWidth(100)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def _check_for_updates(self):
        """Check for available updates."""
        self.update_button.setEnabled(False)
        self.update_button.setText("Checking...")
        
        self._update_thread = UpdateCheckThread(VERSION)
        self._update_thread.update_available.connect(self._on_update_check_complete)
        self._update_thread.error_occurred.connect(self._on_update_check_error)
        self._update_thread.start()
    
    def _on_update_check_complete(self, update_info):
        """Handle update check completion."""
        self.update_button.setEnabled(True)
        self.update_button.setText("Check for Updates")
        
        if update_info is None:
            QMessageBox.information(
                self,
                "No Updates",
                f"You are running the latest version ({VERSION})."
            )
        else:
            # Show update available dialog
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
        self.update_button.setEnabled(True)
        self.update_button.setText("Check for Updates")
        
        QMessageBox.warning(
            self,
            "Update Check Failed",
            f"Could not check for updates:\n{error_msg}"
        )
    
    def _download_update(self, update_info):
        """Download the update."""
        # Create progress dialog
        self._progress_dialog = QProgressDialog(
            "Downloading update...", "Cancel", 0, 100, self
        )
        self._progress_dialog.setWindowTitle("Downloading Update")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setValue(0)
        
        # Start download thread
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
            
            # Show size in MB
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self._progress_dialog.setLabelText(
                f"Downloading update... {downloaded_mb:.1f} MB / {total_mb:.1f} MB"
            )
    
    def _on_download_complete(self, installer_path):
        """Handle download completion."""
        self._progress_dialog.close()
        
        if installer_path is None:
            QMessageBox.warning(
                self,
                "Download Failed",
                "Failed to download the update. Please try again later."
            )
            return
        
        # Ask to install
        reply = QMessageBox.question(
            self,
            "Download Complete",
            f"Update downloaded successfully!\n\n"
            f"The installer will now launch. The application will close.\n\n"
            f"Do you want to install the update now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            from vpnmikro.core.updater import install_update
            if install_update(installer_path):
                # Close the application
                from PyQt6.QtWidgets import QApplication
                QApplication.quit()
            else:
                QMessageBox.warning(
                    self,
                    "Installation Failed",
                    f"Failed to launch the installer.\n\n"
                    f"You can manually run the installer from:\n{installer_path}"
                )
    
    def _on_download_error(self, error_msg):
        """Handle download error."""
        self._progress_dialog.close()
        
        QMessageBox.warning(
            self,
            "Download Failed",
            f"Failed to download the update:\n{error_msg}"
        )


def get_version() -> str:
    """Get the application version string.
    
    Returns:
        Version string (e.g., "1.0.0")
    """
    return VERSION
