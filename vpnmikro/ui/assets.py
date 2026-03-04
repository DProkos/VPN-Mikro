"""Asset loading utilities for VPN Mikro UI.

Provides helper functions for loading icons and stylesheets.
"""

import sys
from pathlib import Path
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize

# Asset directories
ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
THEME_FILE = ASSETS_DIR / "theme.qss"
LOGO_DIR = Path(__file__).resolve().parents[2] / "logo"

# Cached window icon
_window_icon: QIcon | None = None


def get_window_icon() -> QIcon:
    """Get the application window icon.
    
    Returns:
        QIcon for window title bar (logo_no_BG.ico)
    """
    global _window_icon
    
    if _window_icon is not None:
        return _window_icon
    
    # Try different possible paths for the icon
    icon_paths = [
        LOGO_DIR / "logo_no_BG.ico",
        Path(__file__).parent.parent.parent / "logo" / "logo_no_BG.ico",
        Path(sys.executable).parent / "logo" / "logo_no_BG.ico",
    ]
    
    for icon_path in icon_paths:
        if icon_path.exists():
            _window_icon = QIcon(str(icon_path))
            return _window_icon
    
    # Return empty icon if not found
    _window_icon = QIcon()
    return _window_icon


def icon(name: str) -> QIcon:
    """Load an SVG icon by name.
    
    Args:
        name: Icon name without extension (e.g., "settings", "plug")
        
    Returns:
        QIcon loaded from the SVG file
    """
    icon_path = ICONS_DIR / f"{name}.svg"
    if icon_path.exists():
        return QIcon(str(icon_path))
    return QIcon()


def load_theme() -> str:
    """Load the application theme stylesheet.
    
    Replaces relative icon paths with absolute paths for proper loading.
    
    Returns:
        QSS stylesheet content as string
    """
    if not THEME_FILE.exists():
        return ""
    
    content = THEME_FILE.read_text(encoding="utf-8")
    
    # Replace relative paths with absolute paths for icons
    # QSS needs forward slashes even on Windows
    icons_path = str(ICONS_DIR).replace("\\", "/")
    content = content.replace("url(assets/icons/", f"url({icons_path}/")
    
    return content


# Common icon sizes
ICON_SIZE_SM = QSize(16, 16)
ICON_SIZE_MD = QSize(18, 18)
ICON_SIZE_LG = QSize(24, 24)


# Icon name constants for consistency
class Icons:
    """Icon name constants."""
    PLUG = "plug"
    UNPLUG = "unplug"
    PROFILE = "profile"
    SERVER = "server"
    SHIELD = "shield"
    SETTINGS = "settings"
    PLUS = "plus"
    TRASH = "trash"
    DOWNLOAD = "download"
    QRCODE = "qrcode"
    COPY = "copy"
    KEY = "key"
    REFRESH = "refresh"
    CHECK = "check"
    X = "x"
    INFO = "info"
    CHEVRON_UP = "chevron-up"
    CHEVRON_DOWN = "chevron-down"
