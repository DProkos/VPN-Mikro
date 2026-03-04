"""Windows WireGuard tunnel service controller.

This module provides functionality to install, uninstall, and manage
WireGuard tunnel services on Windows using wireguard.exe.
"""

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .logger import get_logger
from .models import TunnelStatus


class WGControllerError(Exception):
    """Base exception for WGController errors."""
    pass


class AdminRightsError(WGControllerError):
    """Raised when admin rights are required but not available."""
    pass


class TunnelInstallError(WGControllerError):
    """Raised when tunnel installation fails."""
    pass


class TunnelUninstallError(WGControllerError):
    """Raised when tunnel uninstallation fails."""
    pass


def get_wireguard_exe_path() -> Path:
    """Get the path to wireguard.exe.
    
    Searches in order:
    1. wintun/ folder (bundled - preferred)
    2. bin/ folder (legacy)
    3. System PATH
    
    Returns:
        Path to wireguard.exe
        
    Raises:
        FileNotFoundError: If wireguard.exe not found.
    """
    # Get the base directory
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent.parent.parent
    
    # Check wintun folder first (new location)
    wintun_path = base_dir / "wintun" / "wireguard.exe"
    if wintun_path.exists():
        return wintun_path
    
    # Check bin folder (legacy location)
    bin_path = base_dir / "bin" / "wireguard.exe"
    if bin_path.exists():
        return bin_path
    
    # Check system PATH
    system_wg = shutil.which("wireguard")
    if system_wg:
        return Path(system_wg)
    
    raise FileNotFoundError(
        f"wireguard.exe not found. Searched:\n"
        f"  - {wintun_path}\n"
        f"  - {bin_path}\n"
        f"  - System PATH\n"
        "Please ensure WireGuard is bundled with the application."
    )


class WGController:
    """Windows WireGuard tunnel service controller.
    
    Manages WireGuard tunnel services using wireguard.exe commands:
    - /installtunnelservice: Creates and starts a Windows service
    - /uninstalltunnelservice: Stops and removes the service
    
    Tunnel services are named WireGuardTunnel$<tunnel_name>.
    
    Attributes:
        CONFIG_DIR: Directory for storing config files
        TUNNEL_PREFIX: Prefix for generated tunnel names
    """
    
    CONFIG_DIR = Path(os.environ.get("ProgramData", "C:\\ProgramData")) / "VPNMikro" / "configs"
    TUNNEL_PREFIX = "vpnmikro-"
    
    # Pattern for safe tunnel name characters
    SAFE_CHARS_PATTERN = re.compile(r'[^a-zA-Z0-9_-]')
    
    def __init__(self, wireguard_exe_path: Optional[Path] = None):
        """Initialize the WGController.
        
        Args:
            wireguard_exe_path: Optional custom path to wireguard.exe.
                               If not provided, auto-detects location.
        """
        self._logger = get_logger("wg_controller")
        
        if wireguard_exe_path:
            self._wireguard_exe = Path(wireguard_exe_path)
        else:
            try:
                self._wireguard_exe = get_wireguard_exe_path()
            except FileNotFoundError:
                self._wireguard_exe = None
        
        # Ensure config directory exists
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def make_tunnel_name(device_name: str) -> str:
        """Generate a safe tunnel name from device name.
        
        Creates a slug that:
        - Is prefixed with "vpnmikro-"
        - Contains only alphanumeric characters, hyphens, and underscores
        - Is lowercase
        - Has no leading/trailing hyphens or underscores
        
        Args:
            device_name: Human-readable device name
            
        Returns:
            Safe tunnel name (e.g., "vpnmikro-laptop01")
        """
        if not device_name:
            device_name = "device"
        
        # Convert to lowercase
        slug = device_name.lower()
        
        # Replace spaces and common separators with hyphens
        slug = slug.replace(" ", "-").replace(".", "-").replace("_", "-")
        
        # Remove any characters that aren't alphanumeric, hyphen, or underscore
        slug = WGController.SAFE_CHARS_PATTERN.sub("", slug)
        
        # Collapse multiple hyphens
        while "--" in slug:
            slug = slug.replace("--", "-")
        
        # Remove leading/trailing hyphens and underscores
        slug = slug.strip("-_")
        
        # Ensure we have something
        if not slug:
            slug = "device"
        
        # Truncate if too long (Windows service names have limits)
        max_slug_len = 50
        if len(slug) > max_slug_len:
            slug = slug[:max_slug_len].rstrip("-_")
        
        return f"{WGController.TUNNEL_PREFIX}{slug}"
    
    def _get_wireguard_exe(self) -> Path:
        """Get the path to wireguard.exe.
        
        Returns:
            Path to wireguard.exe
            
        Raises:
            WGControllerError: If wireguard.exe is not found
        """
        if self._wireguard_exe is None:
            try:
                self._wireguard_exe = get_wireguard_exe_path()
            except FileNotFoundError as e:
                raise WGControllerError(str(e))
        
        if not self._wireguard_exe.exists():
            raise WGControllerError(
                f"wireguard.exe not found at {self._wireguard_exe}. "
                "Please ensure WireGuard is bundled with the application."
            )
        return self._wireguard_exe

    def _run_wireguard_command(
        self,
        args: list[str],
        check: bool = True
    ) -> subprocess.CompletedProcess:
        """Run a wireguard.exe command.
        
        Args:
            args: Command arguments (without the exe path)
            check: Whether to raise on non-zero exit code
            
        Returns:
            CompletedProcess result
            
        Raises:
            AdminRightsError: If admin rights are required
            WGControllerError: If command execution fails
        """
        exe_path = self._get_wireguard_exe()
        cmd = [str(exe_path)] + args
        
        self._logger.debug(f"Running WireGuard command: {' '.join(args)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if check and result.returncode != 0:
                stderr = result.stderr.strip() if result.stderr else ""
                stdout = result.stdout.strip() if result.stdout else ""
                error_msg = stderr or stdout or f"Exit code {result.returncode}"
                
                # Check for admin rights error
                if "access is denied" in error_msg.lower() or result.returncode == 5:
                    raise AdminRightsError(
                        "Administrator rights required. "
                        "Please run as Administrator to install VPN tunnel."
                    )
                
                raise WGControllerError(f"WireGuard command failed: {error_msg}")
            
            return result
            
        except subprocess.TimeoutExpired:
            raise WGControllerError("WireGuard command timed out")
        except FileNotFoundError:
            raise WGControllerError(f"wireguard.exe not found at {exe_path}")
        except PermissionError:
            raise AdminRightsError(
                "Administrator rights required. "
                "Please run as Administrator to install VPN tunnel."
            )
    
    def install_tunnel(self, config_path: Path, use_elevation: bool = True) -> bool:
        """Install and start a WireGuard tunnel service.
        
        Creates a Windows service named WireGuardTunnel$<config_name>
        that manages the VPN connection.
        
        Args:
            config_path: Path to the .conf file
            use_elevation: If True, use UAC elevation when needed
            
        Returns:
            True if installation succeeded
            
        Raises:
            TunnelInstallError: If installation fails
            AdminRightsError: If admin rights are required and elevation disabled
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise TunnelInstallError(f"Config file not found: {config_path}")
        
        if not config_path.suffix.lower() == ".conf":
            raise TunnelInstallError(f"Invalid config file extension: {config_path}")
        
        tunnel_name = config_path.stem
        self._logger.info(f"Installing tunnel service: {tunnel_name}")
        
        # Check if we need elevation
        from .elevation import is_admin, run_elevated_action
        
        if not is_admin() and use_elevation:
            self._logger.info("Requesting elevation for tunnel installation...")
            try:
                result = run_elevated_action(
                    "install_tunnel",
                    config=str(config_path)
                )
                
                if result["ok"]:
                    self._logger.info(f"Tunnel service installed successfully: {tunnel_name}")
                    return True
                else:
                    error_msg = result.get("stderr", "") or result.get("stdout", "") or "Unknown error"
                    raise TunnelInstallError(f"Failed to install tunnel: {error_msg}")
                    
            except PermissionError as e:
                raise AdminRightsError(str(e))
            except Exception as e:
                raise TunnelInstallError(f"Failed to install tunnel: {e}")
        
        # Already admin or elevation disabled - run directly
        try:
            self._run_wireguard_command(["/installtunnelservice", str(config_path)])
            self._logger.info(f"Tunnel service installed successfully: {tunnel_name}")
            return True
            
        except AdminRightsError:
            raise
        except WGControllerError as e:
            raise TunnelInstallError(f"Failed to install tunnel: {e}")
    
    def uninstall_tunnel(self, tunnel_name: str, use_elevation: bool = True) -> bool:
        """Stop and uninstall a WireGuard tunnel service.
        
        Removes the Windows service WireGuardTunnel$<tunnel_name>.
        
        Args:
            tunnel_name: Name of the tunnel (without WireGuardTunnel$ prefix)
            use_elevation: If True, use UAC elevation when needed
            
        Returns:
            True if uninstallation succeeded
            
        Raises:
            TunnelUninstallError: If uninstallation fails
            AdminRightsError: If admin rights are required and elevation disabled
        """
        self._logger.info(f"Uninstalling tunnel service: {tunnel_name}")
        
        # Check if we need elevation
        from .elevation import is_admin, run_elevated_action
        
        if not is_admin() and use_elevation:
            self._logger.info("Requesting elevation for tunnel uninstallation...")
            try:
                result = run_elevated_action(
                    "uninstall_tunnel",
                    tunnel=tunnel_name
                )
                
                if result["ok"]:
                    self._logger.info(f"Tunnel service uninstalled successfully: {tunnel_name}")
                    return True
                else:
                    error_msg = result.get("stderr", "") or result.get("stdout", "") or "Unknown error"
                    # Check if service doesn't exist (not an error)
                    if "does not exist" in error_msg.lower() or "not found" in error_msg.lower():
                        self._logger.warning(f"Tunnel service not found: {tunnel_name}")
                        return True
                    raise TunnelUninstallError(f"Failed to uninstall tunnel: {error_msg}")
                    
            except PermissionError as e:
                raise AdminRightsError(str(e))
            except Exception as e:
                raise TunnelUninstallError(f"Failed to uninstall tunnel: {e}")
        
        # Already admin or elevation disabled - run directly
        try:
            self._run_wireguard_command(["/uninstalltunnelservice", tunnel_name])
            self._logger.info(f"Tunnel service uninstalled successfully: {tunnel_name}")
            return True
            
        except AdminRightsError:
            raise
        except WGControllerError as e:
            # Check if service doesn't exist (not an error)
            if "does not exist" in str(e).lower() or "not found" in str(e).lower():
                self._logger.warning(f"Tunnel service not found: {tunnel_name}")
                return True
            raise TunnelUninstallError(f"Failed to uninstall tunnel: {e}")

    def is_tunnel_running(self, tunnel_name: str) -> bool:
        """Check if a tunnel service is currently running.
        
        Queries the Windows service WireGuardTunnel$<tunnel_name>.
        
        Args:
            tunnel_name: Name of the tunnel (without WireGuardTunnel$ prefix)
            
        Returns:
            True if the service is running, False otherwise
        """
        service_name = f"WireGuardTunnel${tunnel_name}"
        
        try:
            # Use sc query to check service status
            result = subprocess.run(
                ["sc", "query", service_name],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode != 0 or not result.stdout:
                # Service doesn't exist or query failed
                return False
            
            # Parse output for RUNNING state
            output = result.stdout.upper()
            return "RUNNING" in output and "STATE" in output
            
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            self._logger.warning(f"Could not query service status for {tunnel_name}")
            return False
        except Exception:
            return False
    
    def get_tunnel_status(self, tunnel_name: str) -> TunnelStatus:
        """Get detailed status of a tunnel service.
        
        Returns status information including whether the service is running.
        Note: Handshake time and traffic stats are best-effort and may not
        always be available.
        
        Args:
            tunnel_name: Name of the tunnel (without WireGuardTunnel$ prefix)
            
        Returns:
            TunnelStatus with current state information
        """
        running = self.is_tunnel_running(tunnel_name)
        
        # Create basic status
        status = TunnelStatus(
            running=running,
            tunnel_name=tunnel_name,
            last_handshake=None,
            rx_bytes=0,
            tx_bytes=0
        )
        
        # If running, try to get additional stats (best-effort)
        if running:
            try:
                stats = self._get_tunnel_stats(tunnel_name)
                if stats:
                    status.rx_bytes = stats.get("rx_bytes", 0)
                    status.tx_bytes = stats.get("tx_bytes", 0)
                    status.last_handshake = stats.get("last_handshake")
            except Exception as e:
                self._logger.debug(f"Could not get tunnel stats: {e}")
        
        return status
    
    def _get_tunnel_stats(self, tunnel_name: str) -> Optional[dict]:
        """Get tunnel statistics using Windows API (fast, no subprocess).
        
        Uses iphlpapi.dll to get network adapter statistics directly.
        Falls back to PowerShell if needed.
        
        Args:
            tunnel_name: Name of the tunnel (also the network adapter name)
            
        Returns:
            Dictionary with stats or None if unavailable
        """
        # Try fast method first using Windows registry/WMI
        try:
            return self._get_tunnel_stats_fast(tunnel_name)
        except Exception:
            pass
        
        # Fallback to PowerShell (slower but reliable)
        try:
            cmd = [
                "powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                f"Get-NetAdapterStatistics -Name '{tunnel_name}' -ErrorAction SilentlyContinue | "
                "Select-Object -Property ReceivedBytes,SentBytes | ConvertTo-Json"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                return None
            
            import json
            data = json.loads(result.stdout)
            
            return {
                "rx_bytes": data.get("ReceivedBytes", 0) or 0,
                "tx_bytes": data.get("SentBytes", 0) or 0,
                "last_handshake": None
            }
            
        except Exception as e:
            self._logger.debug(f"Could not get tunnel stats: {e}")
            return None
    
    def _get_tunnel_stats_fast(self, tunnel_name: str) -> Optional[dict]:
        """Get tunnel statistics using WMI (faster than PowerShell subprocess).
        
        Args:
            tunnel_name: Name of the tunnel adapter
            
        Returns:
            Dictionary with stats or None if unavailable
        """
        try:
            import wmi
            c = wmi.WMI()
            
            # Query network adapter statistics
            for adapter in c.Win32_PerfRawData_Tcpip_NetworkInterface():
                # Match adapter name (WMI uses slightly different naming)
                if tunnel_name.lower() in adapter.Name.lower():
                    return {
                        "rx_bytes": int(adapter.BytesReceivedPersec or 0),
                        "tx_bytes": int(adapter.BytesSentPersec or 0),
                        "last_handshake": None
                    }
            return None
        except ImportError:
            # WMI module not available, use alternative
            return self._get_tunnel_stats_registry(tunnel_name)
        except Exception:
            return None
    
    def _get_tunnel_stats_registry(self, tunnel_name: str) -> Optional[dict]:
        """Get tunnel statistics from Windows registry (fastest method).
        
        Args:
            tunnel_name: Name of the tunnel adapter
            
        Returns:
            Dictionary with stats or None if unavailable
        """
        try:
            import winreg
            
            # Network adapters are stored in registry
            key_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
            
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                # This is a simplified approach - actual implementation would need
                # to map adapter GUID to name
                pass
            
            return None  # Registry method needs more work, fallback to PowerShell
        except Exception:
            return None
    
    def get_config_path(self, tunnel_name: str) -> Path:
        """Get the expected config file path for a tunnel.
        
        Args:
            tunnel_name: Name of the tunnel
            
        Returns:
            Path to the config file
        """
        return self.CONFIG_DIR / f"{tunnel_name}.conf"
    
    def list_installed_tunnels(self) -> list[str]:
        """List all installed VPN Mikro tunnel services.
        
        Returns:
            List of tunnel names (without WireGuardTunnel$ prefix)
        """
        tunnels = []
        
        try:
            # Query all WireGuard tunnel services
            result = subprocess.run(
                ["sc", "query", "type=", "service", "state=", "all"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode == 0 and result.stdout:
                # Parse output for WireGuardTunnel$vpnmikro-* services
                for line in result.stdout.split("\n"):
                    if "WireGuardTunnel$" in line and self.TUNNEL_PREFIX in line:
                        # Extract service name
                        parts = line.split("WireGuardTunnel$")
                        if len(parts) > 1:
                            tunnel_name = parts[1].strip()
                            if tunnel_name.startswith(self.TUNNEL_PREFIX):
                                tunnels.append(tunnel_name)
            
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as e:
            self._logger.warning(f"Could not list tunnel services: {e}")
        except Exception as e:
            self._logger.warning(f"Error listing tunnels: {e}")
        
        return tunnels
    
    def list_all_wireguard_tunnels(self) -> list[str]:
        """List ALL WireGuard tunnel services (not just VPN Mikro ones).
        
        Returns:
            List of all tunnel names (without WireGuardTunnel$ prefix)
        """
        tunnels = []
        
        try:
            # Query all WireGuard tunnel services
            result = subprocess.run(
                ["sc", "query", "type=", "service", "state=", "all"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode == 0 and result.stdout:
                # Parse output for ALL WireGuardTunnel$ services
                for line in result.stdout.split("\n"):
                    if "WireGuardTunnel$" in line:
                        # Extract service name
                        parts = line.split("WireGuardTunnel$")
                        if len(parts) > 1:
                            tunnel_name = parts[1].strip()
                            if tunnel_name:
                                tunnels.append(tunnel_name)
            
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as e:
            self._logger.warning(f"Could not list tunnel services: {e}")
        except Exception as e:
            self._logger.warning(f"Error listing tunnels: {e}")
        
        return tunnels
    
    def get_any_running_tunnel(self) -> Optional[str]:
        """Get the name of any running WireGuard tunnel.
        
        Returns:
            Name of a running tunnel, or None if no tunnels are running
        """
        for tunnel_name in self.list_all_wireguard_tunnels():
            if self.is_tunnel_running(tunnel_name):
                return tunnel_name
        return None
    
    def cleanup_orphaned_configs(self) -> int:
        """Remove config files for tunnels that are no longer installed.
        
        Returns:
            Number of config files removed
        """
        removed = 0
        installed = set(self.list_installed_tunnels())
        
        try:
            for config_file in self.CONFIG_DIR.glob(f"{self.TUNNEL_PREFIX}*.conf"):
                tunnel_name = config_file.stem
                if tunnel_name not in installed:
                    try:
                        config_file.unlink()
                        self._logger.info(f"Removed orphaned config: {config_file}")
                        removed += 1
                    except OSError as e:
                        self._logger.warning(f"Could not remove {config_file}: {e}")
        except OSError as e:
            self._logger.warning(f"Could not scan config directory: {e}")
        
        return removed
