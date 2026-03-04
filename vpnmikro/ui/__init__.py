"""PyQt6 user interface components."""

from vpnmikro.ui.main_window import MainWindow, run_app
from vpnmikro.ui.dashboard import ModernMainWindow, run_modern_app
from vpnmikro.ui.connection_tab import ConnectionTab
from vpnmikro.ui.vpn_servers_tab import VPNServersTab
from vpnmikro.ui.devices_tab import DevicesTab
from vpnmikro.ui.advanced_tab import AdvancedTab
from vpnmikro.ui.wizard import SetupWizard, check_first_run
from vpnmikro.ui.about_dialog import AboutDialog, get_version
from vpnmikro.ui.settings_dialog import SettingsDialog
from vpnmikro.ui.assets import icon, load_theme, Icons

__all__ = [
    "MainWindow",
    "run_app",
    "ModernMainWindow",
    "run_modern_app",
    "ConnectionTab",
    "VPNServersTab",
    "DevicesTab",
    "AdvancedTab",
    "SetupWizard",
    "check_first_run",
    "AboutDialog",
    "get_version",
    "SettingsDialog",
    "icon",
    "load_theme",
    "Icons",
]
