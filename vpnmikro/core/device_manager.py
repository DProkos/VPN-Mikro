"""Device lifecycle management orchestrator.

This module provides the DeviceManager class that orchestrates device
creation, deletion, and connection management by coordinating between
ProfileManager, WGPeerManager, WGConfigBuilder, IPAllocator, and WGController.
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .ip_allocator import IPAllocator
from .logger import get_logger
from .models import Device, Profile, TunnelStatus
from .profiles import ProfileManager
from .secure_store import SecureStore
from .wg_config import WGConfigBuilder
from .wg_controller_win import (
    WGController,
    WGControllerError,
    AdminRightsError,
    TunnelInstallError,
    TunnelUninstallError,
)
from ..mikrotik.wg_manager import WGPeerManager, WGPeerManagerError


class DeviceManagerError(Exception):
    """Base exception for DeviceManager errors."""
    pass


class DeviceCreationError(DeviceManagerError):
    """Raised when device creation fails."""
    pass


class DeviceDeletionError(DeviceManagerError):
    """Raised when device deletion fails."""
    pass


class DeviceNotFoundError(DeviceManagerError):
    """Raised when a device is not found."""
    pass


class PoolExhaustedError(DeviceManagerError):
    """Raised when the IP pool is exhausted."""
    pass


class DeviceManager:
    """High-level orchestration for device lifecycle management.
    
    Coordinates between multiple components to manage the complete
    lifecycle of VPN devices:
    - Creation: generate keys → allocate IP → add peer → write config
    - Deletion: 2-phase deletion with pending_delete flag
    - Connection: install/uninstall tunnel services
    
    Attributes:
        profile_manager: Manages profile persistence.
        peer_manager: Manages MikroTik WireGuard peers.
        config_builder: Generates WireGuard configurations.
        wg_controller: Controls Windows tunnel services.
        secure_store: Encrypts sensitive data.
    """
    
    CONFIG_DIR = Path(os.environ.get("ProgramData", "C:\\ProgramData")) / "VPNMikro" / "configs"
    
    def __init__(
        self,
        profile_manager: ProfileManager,
        peer_manager: Optional[WGPeerManager] = None,
        config_builder: Optional[WGConfigBuilder] = None,
        wg_controller: Optional[WGController] = None,
        secure_store: Optional[SecureStore] = None,
    ):
        """Initialize DeviceManager.
        
        Args:
            profile_manager: ProfileManager instance for profile persistence.
            peer_manager: WGPeerManager instance for MikroTik operations.
                         Can be None if not connected to router.
            config_builder: WGConfigBuilder instance. Creates new if not provided.
            wg_controller: WGController instance. Creates new if not provided.
            secure_store: SecureStore instance. Creates new if not provided.
        """
        self._logger = get_logger("device_manager")
        self._profile_manager = profile_manager
        self._peer_manager = peer_manager
        self._config_builder = config_builder or WGConfigBuilder()
        self._wg_controller = wg_controller or WGController()
        self._secure_store = secure_store or SecureStore()
        
        # Ensure config directory exists
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    def set_peer_manager(self, peer_manager: WGPeerManager) -> None:
        """Set or update the peer manager.
        
        Args:
            peer_manager: WGPeerManager instance for MikroTik operations.
        """
        self._peer_manager = peer_manager

    def _get_device_by_uuid(self, profile: Profile, device_uuid: str) -> Optional[Device]:
        """Find a device in a profile by UUID.
        
        Args:
            profile: Profile to search in.
            device_uuid: UUID of the device to find.
            
        Returns:
            Device if found, None otherwise.
        """
        for device in profile.devices:
            if device.uuid == device_uuid:
                return device
        return None
    
    def _require_peer_manager(self) -> WGPeerManager:
        """Get peer manager, raising if not available.
        
        Returns:
            The WGPeerManager instance.
            
        Raises:
            DeviceManagerError: If peer manager is not set.
        """
        if self._peer_manager is None:
            raise DeviceManagerError(
                "Not connected to MikroTik router. "
                "Please connect before managing devices."
            )
        return self._peer_manager
    
    def create_device(self, profile: Profile, device_name: str) -> Device:
        """Create a new device with full provisioning.
        
        This method:
        1. Generates a new WireGuard keypair
        2. Allocates the next available IP from the pool
        3. Creates a peer on the MikroTik router
        4. Generates and writes the config file
        5. Saves the device to the profile
        
        If peer creation fails, the IP allocation is rolled back.
        
        Args:
            profile: Profile to create the device in.
            device_name: Human-readable name for the device.
            
        Returns:
            The created Device object.
            
        Raises:
            DeviceCreationError: If device creation fails.
            PoolExhaustedError: If no IPs are available.
        """
        peer_manager = self._require_peer_manager()
        
        if not profile.selected_interface:
            raise DeviceCreationError("No WireGuard interface selected in profile")
        
        if not profile.endpoint:
            raise DeviceCreationError("No endpoint configured in profile")
        
        if not profile.server_public_key:
            raise DeviceCreationError("No server public key configured in profile")
        
        self._logger.info(f"Creating device: {device_name}")
        
        # Step 1: Generate keypair
        self._logger.debug("Generating WireGuard keypair")
        private_key, public_key = WGConfigBuilder.generate_keypair()
        
        # Step 2: Allocate IP
        self._logger.debug("Allocating IP address")
        allocator = IPAllocator(profile.ip_pool)
        
        try:
            # Get used IPs from existing peers
            peers = peer_manager.list_peers(profile.selected_interface)
            peer_dicts = [{"allowed_address": p.allowed_address} for p in peers]
            used_ips = allocator.get_used_ips(peer_dicts)
            
            # Check if pool is exhausted
            if allocator.is_pool_exhausted(used_ips):
                raise PoolExhaustedError(
                    f"No available IPs in pool {profile.ip_pool}. "
                    "Please expand the pool or delete unused devices."
                )
            
            # Allocate next IP
            assigned_ip = allocator.allocate_next(used_ips)
            if not assigned_ip:
                raise PoolExhaustedError(f"No available IPs in pool {profile.ip_pool}")
            
            self._logger.info(f"Allocated IP: {assigned_ip}")
            
        except WGPeerManagerError as e:
            raise DeviceCreationError(f"Failed to fetch existing peers: {e}")
        
        # Step 3: Create peer on MikroTik (with rollback on failure)
        peer_id = None
        try:
            self._logger.debug("Creating peer on MikroTik")
            peer_id = peer_manager.add_peer(
                interface=profile.selected_interface,
                public_key=public_key,
                allowed_address=f"{assigned_ip}/32",
                comment=f"VPNMikro: {device_name}"
            )
            self._logger.info(f"Created peer with ID: {peer_id}")
            
        except WGPeerManagerError as e:
            # Rollback: IP allocation is stateless, so nothing to rollback there
            self._logger.error(f"Failed to create peer, rolling back: {e}")
            raise DeviceCreationError(f"Failed to create peer on MikroTik: {e}")
        
        # Step 4: Generate and write config
        try:
            self._logger.debug("Generating WireGuard config")
            
            config_content = self._config_builder.build_config(
                private_key=private_key,
                address=assigned_ip,
                server_public_key=profile.server_public_key,
                endpoint=profile.endpoint,
                tunnel_mode=profile.tunnel_mode,
                split_subnets=profile.split_subnets if profile.tunnel_mode == "split" else None,
                dns=profile.dns,
                mtu=profile.mtu,
                keepalive=profile.keepalive,
            )
            
            # Generate tunnel name and config path
            tunnel_name = WGController.make_tunnel_name(device_name)
            config_path = self.CONFIG_DIR / f"{tunnel_name}.conf"
            
            self._config_builder.write_config(config_content, config_path)
            self._logger.info(f"Wrote config to: {config_path}")
            
        except Exception as e:
            # Rollback: Remove the peer we just created
            self._logger.error(f"Failed to write config, rolling back peer: {e}")
            try:
                peer_manager.remove_peer(peer_id)
            except WGPeerManagerError as rollback_error:
                self._logger.warning(f"Rollback failed: {rollback_error}")
            raise DeviceCreationError(f"Failed to generate config: {e}")
        
        # Step 5: Create and save device
        try:
            device = Device(
                uuid=str(uuid.uuid4()),
                name=device_name,
                assigned_ip=assigned_ip,
                peer_id=peer_id,
                private_key_encrypted=self._secure_store.encrypt_string(private_key),
                public_key=public_key,
                config_path=str(config_path),
                created_at=datetime.now(),
                enabled=True,
                pending_delete=False,
            )
            
            # Add to profile and save
            profile.devices.append(device)
            self._profile_manager.save_profile(profile)
            
            self._logger.info(f"Device created successfully: {device.uuid}")
            return device
            
        except Exception as e:
            # Rollback: Remove peer and config file
            self._logger.error(f"Failed to save device, rolling back: {e}")
            try:
                peer_manager.remove_peer(peer_id)
            except WGPeerManagerError:
                pass
            try:
                config_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise DeviceCreationError(f"Failed to save device: {e}")

    def delete_device(self, profile: Profile, device_uuid: str) -> None:
        """Delete a device with 2-phase deletion.
        
        Phase 1: Mark device as pending_delete
        Phase 2: Remove peer from MikroTik, then delete local record
        
        The local record is only removed if the MikroTik peer removal succeeds.
        This ensures consistency between local and remote state.
        
        Args:
            profile: Profile containing the device.
            device_uuid: UUID of the device to delete.
            
        Raises:
            DeviceNotFoundError: If device is not found.
            DeviceDeletionError: If deletion fails.
        """
        peer_manager = self._require_peer_manager()
        
        device = self._get_device_by_uuid(profile, device_uuid)
        if not device:
            raise DeviceNotFoundError(f"Device not found: {device_uuid}")
        
        self._logger.info(f"Deleting device: {device.name} ({device_uuid})")
        
        # Phase 1: Mark as pending delete
        if not device.pending_delete:
            device.pending_delete = True
            self._profile_manager.save_profile(profile)
            self._logger.debug("Marked device as pending_delete")
        
        # Phase 2: Remove from MikroTik
        try:
            self._logger.debug(f"Removing peer from MikroTik: {device.peer_id}")
            peer_manager.remove_peer(device.peer_id)
            self._logger.info("Peer removed from MikroTik")
            
        except WGPeerManagerError as e:
            # Check if peer doesn't exist (already deleted)
            error_str = str(e).lower()
            if "does not exist" in error_str or "no such item" in error_str:
                self._logger.warning("Peer already removed from MikroTik")
            else:
                # Keep pending_delete flag set for retry
                raise DeviceDeletionError(f"Failed to remove peer from MikroTik: {e}")
        
        # Phase 3: Delete local config file
        try:
            config_path = Path(device.config_path)
            if config_path.exists():
                config_path.unlink()
                self._logger.debug(f"Deleted config file: {config_path}")
        except OSError as e:
            self._logger.warning(f"Could not delete config file: {e}")
        
        # Phase 4: Remove from profile (only after MikroTik removal succeeded)
        profile.devices = [d for d in profile.devices if d.uuid != device_uuid]
        self._profile_manager.save_profile(profile)
        
        self._logger.info(f"Device deleted successfully: {device_uuid}")
    
    def enable_device(self, profile: Profile, device_uuid: str, enabled: bool) -> None:
        """Enable or disable a device's peer on MikroTik.
        
        Args:
            profile: Profile containing the device.
            device_uuid: UUID of the device.
            enabled: True to enable, False to disable.
            
        Raises:
            DeviceNotFoundError: If device is not found.
            DeviceManagerError: If the operation fails.
        """
        peer_manager = self._require_peer_manager()
        
        device = self._get_device_by_uuid(profile, device_uuid)
        if not device:
            raise DeviceNotFoundError(f"Device not found: {device_uuid}")
        
        action = "Enabling" if enabled else "Disabling"
        self._logger.info(f"{action} device: {device.name}")
        
        try:
            if enabled:
                peer_manager.enable_peer(device.peer_id)
            else:
                peer_manager.disable_peer(device.peer_id)
            
            # Update local state
            device.enabled = enabled
            self._profile_manager.save_profile(profile)
            
            self._logger.info(f"Device {action.lower()}d successfully")
            
        except WGPeerManagerError as e:
            raise DeviceManagerError(f"Failed to {action.lower()} device: {e}")
    
    def connect_device(self, profile: Profile, device_uuid: str) -> None:
        """Connect a device by installing its tunnel service.
        
        May require administrator privileges on first connect.
        
        Args:
            profile: Profile containing the device.
            device_uuid: UUID of the device to connect.
            
        Raises:
            DeviceNotFoundError: If device is not found.
            AdminRightsError: If admin rights are required.
            DeviceManagerError: If connection fails.
        """
        device = self._get_device_by_uuid(profile, device_uuid)
        if not device:
            raise DeviceNotFoundError(f"Device not found: {device_uuid}")
        
        self._logger.info(f"Connecting device: {device.name}")
        
        config_path = Path(device.config_path)
        if not config_path.exists():
            raise DeviceManagerError(f"Config file not found: {config_path}")
        
        # Check if tunnel is already running
        tunnel_name = config_path.stem
        if self._wg_controller.is_tunnel_running(tunnel_name):
            self._logger.info(f"Device already connected: {device.name}")
            return  # Already connected, nothing to do
        
        try:
            self._wg_controller.install_tunnel(config_path)
            self._logger.info(f"Device connected: {device.name}")
            
        except AdminRightsError:
            # Re-raise admin rights error for UI to handle
            raise
        except (TunnelInstallError, WGControllerError) as e:
            raise DeviceManagerError(f"Failed to connect: {e}")
    
    def disconnect_device(self, profile: Profile, device_uuid: str) -> None:
        """Disconnect a device by uninstalling its tunnel service.
        
        Args:
            profile: Profile containing the device.
            device_uuid: UUID of the device to disconnect.
            
        Raises:
            DeviceNotFoundError: If device is not found.
            AdminRightsError: If admin rights are required.
            DeviceManagerError: If disconnection fails.
        """
        device = self._get_device_by_uuid(profile, device_uuid)
        if not device:
            raise DeviceNotFoundError(f"Device not found: {device_uuid}")
        
        self._logger.info(f"Disconnecting device: {device.name}")
        
        # Get tunnel name from config path
        tunnel_name = Path(device.config_path).stem
        
        try:
            self._wg_controller.uninstall_tunnel(tunnel_name)
            self._logger.info(f"Device disconnected: {device.name}")
            
        except AdminRightsError:
            # Re-raise admin rights error for UI to handle
            raise
        except (TunnelUninstallError, WGControllerError) as e:
            raise DeviceManagerError(f"Failed to disconnect: {e}")
    
    def get_device_status(self, profile: Profile, device_uuid: str) -> TunnelStatus:
        """Get the connection status of a device.
        
        Args:
            profile: Profile containing the device.
            device_uuid: UUID of the device.
            
        Returns:
            TunnelStatus with current state information.
            
        Raises:
            DeviceNotFoundError: If device is not found.
        """
        device = self._get_device_by_uuid(profile, device_uuid)
        if not device:
            raise DeviceNotFoundError(f"Device not found: {device_uuid}")
        
        tunnel_name = Path(device.config_path).stem
        return self._wg_controller.get_tunnel_status(tunnel_name)
    
    def is_device_connected(self, profile: Profile, device_uuid: str) -> bool:
        """Check if a device is currently connected.
        
        Args:
            profile: Profile containing the device.
            device_uuid: UUID of the device.
            
        Returns:
            True if the device's tunnel is running.
            
        Raises:
            DeviceNotFoundError: If device is not found.
        """
        status = self.get_device_status(profile, device_uuid)
        return status.running
    
    def export_config(self, profile: Profile, device_uuid: str, out_path: Path) -> None:
        """Export a device's config file to a specified location.
        
        Args:
            profile: Profile containing the device.
            device_uuid: UUID of the device.
            out_path: Destination path for the config file.
            
        Raises:
            DeviceNotFoundError: If device is not found.
            DeviceManagerError: If export fails.
        """
        device = self._get_device_by_uuid(profile, device_uuid)
        if not device:
            raise DeviceNotFoundError(f"Device not found: {device_uuid}")
        
        self._logger.info(f"Exporting config for device: {device.name}")
        
        config_path = Path(device.config_path)
        if not config_path.exists():
            raise DeviceManagerError(f"Config file not found: {config_path}")
        
        try:
            # Read and write config content
            config_content = config_path.read_text(encoding="utf-8")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(config_content, encoding="utf-8")
            
            self._logger.info(f"Config exported to: {out_path}")
            
        except OSError as e:
            raise DeviceManagerError(f"Failed to export config: {e}")
    
    def get_config_content(self, profile: Profile, device_uuid: str) -> str:
        """Get the raw config content for a device.
        
        Useful for QR code generation.
        
        Args:
            profile: Profile containing the device.
            device_uuid: UUID of the device.
            
        Returns:
            The WireGuard config file content.
            
        Raises:
            DeviceNotFoundError: If device is not found.
            DeviceManagerError: If reading fails.
        """
        device = self._get_device_by_uuid(profile, device_uuid)
        if not device:
            raise DeviceNotFoundError(f"Device not found: {device_uuid}")
        
        config_path = Path(device.config_path)
        if not config_path.exists():
            raise DeviceManagerError(f"Config file not found: {config_path}")
        
        try:
            return config_path.read_text(encoding="utf-8")
        except OSError as e:
            raise DeviceManagerError(f"Failed to read config: {e}")
    
    def cleanup_pending_deletes(self, profile: Profile) -> int:
        """Clean up devices that were marked for deletion but not completed.
        
        This handles cases where deletion was interrupted.
        
        Args:
            profile: Profile to clean up.
            
        Returns:
            Number of devices cleaned up.
        """
        peer_manager = self._require_peer_manager()
        cleaned = 0
        
        pending_devices = [d for d in profile.devices if d.pending_delete]
        
        for device in pending_devices:
            self._logger.info(f"Cleaning up pending delete: {device.name}")
            try:
                self.delete_device(profile, device.uuid)
                cleaned += 1
            except DeviceDeletionError as e:
                self._logger.warning(f"Could not clean up device {device.name}: {e}")
        
        return cleaned
    
    def refresh_device_status(self, profile: Profile, device_uuid: str) -> Device:
        """Refresh a device's enabled status from MikroTik.
        
        Syncs the local enabled state with the actual peer state on MikroTik.
        
        Args:
            profile: Profile containing the device.
            device_uuid: UUID of the device.
            
        Returns:
            The updated Device object.
            
        Raises:
            DeviceNotFoundError: If device is not found.
            DeviceManagerError: If refresh fails.
        """
        peer_manager = self._require_peer_manager()
        
        device = self._get_device_by_uuid(profile, device_uuid)
        if not device:
            raise DeviceNotFoundError(f"Device not found: {device_uuid}")
        
        try:
            peer = peer_manager.get_peer_by_id(
                profile.selected_interface,
                device.peer_id
            )
            
            if peer:
                # Update local state if different
                if device.enabled != (not peer.disabled):
                    device.enabled = not peer.disabled
                    self._profile_manager.save_profile(profile)
            
            return device
            
        except WGPeerManagerError as e:
            raise DeviceManagerError(f"Failed to refresh device status: {e}")
