"""Auto-update functionality for VPN Mikro.

Checks for updates from a remote JSON file and downloads new versions.
"""

import json
import os
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from vpnmikro.core.logger import get_logger

logger = get_logger(__name__)

# Update server configuration
# Change this URL to your actual update server
UPDATE_URL = "https://raw.githubusercontent.com/your-repo/vpnmikro/main/update.json"

# Example update.json format:
# {
#     "version": "1.0.0",
#     "download_url": "https://example.com/vpnmikro-setup-1.0.0.exe",
#     "changelog": "- New feature 1\n- Bug fix 2",
#     "release_date": "2025-12-26",
#     "min_version": "0.0.1"
# }


@dataclass
class UpdateInfo:
    """Information about an available update."""
    version: str
    download_url: str
    changelog: str
    release_date: str
    min_version: str = "0.0.0"


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """Parse version string into tuple of integers.
    
    Args:
        version_str: Version string like "1.2.3"
        
    Returns:
        Tuple of (major, minor, patch)
    """
    try:
        parts = version_str.strip().split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return (0, 0, 0)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings.
    
    Args:
        v1: First version string
        v2: Second version string
        
    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
    """
    v1_tuple = parse_version(v1)
    v2_tuple = parse_version(v2)
    
    if v1_tuple < v2_tuple:
        return -1
    elif v1_tuple > v2_tuple:
        return 1
    return 0


def check_for_updates(current_version: str, update_url: str = UPDATE_URL) -> Optional[UpdateInfo]:
    """Check if a new version is available.
    
    Args:
        current_version: Current application version
        update_url: URL to the update JSON file
        
    Returns:
        UpdateInfo if update available, None otherwise
    """
    try:
        logger.info(f"Checking for updates at {update_url}")
        
        # Create request with user agent
        request = Request(
            update_url,
            headers={"User-Agent": f"VPNMikro/{current_version}"}
        )
        
        # Fetch update info with timeout
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        
        # Parse update info
        remote_version = data.get("version", "0.0.0")
        
        # Compare versions
        if compare_versions(remote_version, current_version) > 0:
            logger.info(f"Update available: {remote_version} (current: {current_version})")
            return UpdateInfo(
                version=remote_version,
                download_url=data.get("download_url", ""),
                changelog=data.get("changelog", ""),
                release_date=data.get("release_date", ""),
                min_version=data.get("min_version", "0.0.0")
            )
        else:
            logger.info(f"No update available (current: {current_version}, remote: {remote_version})")
            return None
            
    except HTTPError as e:
        logger.warning(f"HTTP error checking for updates: {e.code} {e.reason}")
        return None
    except URLError as e:
        logger.warning(f"Network error checking for updates: {e.reason}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid update JSON: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error checking for updates: {e}")
        return None


def download_update(update_info: UpdateInfo, progress_callback=None) -> Optional[Path]:
    """Download the update installer.
    
    Args:
        update_info: Information about the update
        progress_callback: Optional callback(downloaded, total) for progress
        
    Returns:
        Path to downloaded file, or None on failure
    """
    if not update_info.download_url:
        logger.error("No download URL provided")
        return None
    
    try:
        logger.info(f"Downloading update from {update_info.download_url}")
        
        # Create request
        request = Request(
            update_info.download_url,
            headers={"User-Agent": f"VPNMikro/Updater"}
        )
        
        # Get filename from URL
        filename = update_info.download_url.split("/")[-1]
        if not filename.endswith(".exe"):
            filename = f"vpnmikro-setup-{update_info.version}.exe"
        
        # Download to temp directory
        temp_dir = Path(tempfile.gettempdir())
        download_path = temp_dir / filename
        
        with urlopen(request, timeout=300) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8192
            
            with open(download_path, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback and total_size > 0:
                        progress_callback(downloaded, total_size)
        
        logger.info(f"Update downloaded to {download_path}")
        return download_path
        
    except Exception as e:
        logger.error(f"Error downloading update: {e}")
        return None


def install_update(installer_path: Path) -> bool:
    """Launch the installer and exit the application.
    
    Args:
        installer_path: Path to the downloaded installer
        
    Returns:
        True if installer launched successfully
    """
    if not installer_path.exists():
        logger.error(f"Installer not found: {installer_path}")
        return False
    
    try:
        logger.info(f"Launching installer: {installer_path}")
        
        # Launch installer
        subprocess.Popen(
            [str(installer_path)],
            shell=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error launching installer: {e}")
        return False
