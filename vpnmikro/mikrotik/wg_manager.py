"""WireGuard peer management for MikroTik routers.

This module provides high-level operations for managing WireGuard
interfaces and peers on MikroTik routers via the API.
"""

from datetime import datetime
from typing import List, Optional

from vpnmikro.core.logger import get_logger
from vpnmikro.core.models import WGInterface, WGPeer
from vpnmikro.mikrotik.ros_client import ROSClient, ROSCommandError

logger = get_logger(__name__)


class WGPeerManagerError(Exception):
    """Base exception for WG peer manager errors."""
    pass


class WGPeerManager:
    """MikroTik WireGuard peer operations manager.
    
    Provides high-level methods for managing WireGuard interfaces and peers
    on MikroTik routers. Maps API errors to user-friendly messages.
    
    Attributes:
        client: The ROSClient instance for API communication.
    """
    
    # Error message mappings for user-friendly display
    ERROR_MESSAGES = {
        "no such item": "The specified item does not exist",
        "already have": "A peer with this public key already exists",
        "invalid value": "Invalid value provided",
        "permission denied": "Permission denied - check user privileges",
        "not allowed": "Operation not allowed",
    }
    
    def __init__(self, client: ROSClient):
        """Initialize the WG peer manager.
        
        Args:
            client: Connected ROSClient instance.
        """
        self.client = client
    
    def list_interfaces(self) -> List[WGInterface]:
        """List all WireGuard interfaces on the router.
        
        Returns:
            List of WGInterface objects.
            
        Raises:
            WGPeerManagerError: If the operation fails.
        """
        logger.debug("Fetching WireGuard interfaces")
        
        try:
            response = self.client.execute("/interface/wireguard/print")
            
            interfaces = []
            for item in response:
                interface = WGInterface(
                    name=item.get("name", ""),
                    listen_port=int(item.get("listen-port", 0)),
                    public_key=item.get("public-key", ""),
                )
                interfaces.append(interface)
            
            logger.info(f"Found {len(interfaces)} WireGuard interface(s)")
            return interfaces
            
        except ROSCommandError as e:
            raise WGPeerManagerError(self._map_error(str(e)))

    def list_peers(self, interface: str) -> List[WGPeer]:
        """List all peers for a WireGuard interface.
        
        Args:
            interface: Name of the WireGuard interface.
            
        Returns:
            List of WGPeer objects.
            
        Raises:
            WGPeerManagerError: If the operation fails.
        """
        logger.debug(f"Fetching peers for interface: {interface}")
        
        try:
            # Fetch all peers and filter locally by interface
            # MikroTik API query syntax varies by version, so we filter client-side
            response = self.client.execute("/interface/wireguard/peers/print")
            
            peers = []
            for item in response:
                # Filter by interface name
                peer_interface = item.get("interface", "")
                if peer_interface != interface:
                    continue
                    
                peer = WGPeer(
                    id=item.get(".id", ""),
                    interface=peer_interface,
                    public_key=item.get("public-key", ""),
                    allowed_address=item.get("allowed-address", ""),
                    endpoint=item.get("endpoint-address"),
                    last_handshake=self._parse_handshake(item.get("last-handshake")),
                    rx_bytes=int(item.get("rx", 0)),
                    tx_bytes=int(item.get("tx", 0)),
                    disabled=item.get("disabled", "false").lower() == "true",
                    comment=item.get("comment"),
                )
                peers.append(peer)
            
            logger.info(f"Found {len(peers)} peer(s) for interface {interface}")
            return peers
            
        except ROSCommandError as e:
            raise WGPeerManagerError(self._map_error(str(e)))
    
    def add_peer(
        self,
        interface: str,
        public_key: str,
        allowed_address: str,
        comment: Optional[str] = None
    ) -> str:
        """Add a new peer to a WireGuard interface.
        
        Args:
            interface: Name of the WireGuard interface.
            public_key: Peer's public key.
            allowed_address: Allowed IP address/CIDR (e.g., "10.66.0.2/32").
            comment: Optional comment/description.
            
        Returns:
            The MikroTik peer ID (e.g., "*1").
            
        Raises:
            WGPeerManagerError: If the operation fails.
        """
        logger.info(f"Adding peer to interface {interface}: {allowed_address}")
        
        params = {
            "interface": interface,
            "public-key": public_key,
            "allowed-address": allowed_address,
        }
        
        if comment:
            params["comment"] = comment
        
        try:
            response = self.client.execute("/interface/wireguard/peers/add", params)
            
            # The response should contain the new peer's ID
            if response and len(response) > 0:
                peer_id = response[0].get("ret", "")
                if peer_id:
                    logger.info(f"Created peer with ID: {peer_id}")
                    return peer_id
            
            # If no ID returned, try to find the peer by public key
            peers = self.list_peers(interface)
            for peer in peers:
                if peer.public_key == public_key:
                    logger.info(f"Found created peer with ID: {peer.id}")
                    return peer.id
            
            raise WGPeerManagerError("Peer created but ID could not be determined")
            
        except ROSCommandError as e:
            raise WGPeerManagerError(self._map_error(str(e)))

    def set_peer(self, peer_id: str, **kwargs) -> None:
        """Update a peer's properties.
        
        Args:
            peer_id: MikroTik peer ID (e.g., "*1").
            **kwargs: Properties to update (e.g., comment="new comment").
            
        Raises:
            WGPeerManagerError: If the operation fails.
        """
        logger.info(f"Updating peer {peer_id}: {kwargs}")
        
        params = {".id": peer_id}
        
        # Map Python-style keys to MikroTik API keys
        key_mapping = {
            "public_key": "public-key",
            "allowed_address": "allowed-address",
            "endpoint_address": "endpoint-address",
            "endpoint_port": "endpoint-port",
            "persistent_keepalive": "persistent-keepalive",
            "preshared_key": "preshared-key",
        }
        
        for key, value in kwargs.items():
            api_key = key_mapping.get(key, key.replace("_", "-"))
            if value is not None:
                params[api_key] = str(value)
        
        try:
            self.client.execute("/interface/wireguard/peers/set", params)
            logger.info(f"Updated peer {peer_id}")
            
        except ROSCommandError as e:
            raise WGPeerManagerError(self._map_error(str(e)))
    
    def remove_peer(self, peer_id: str) -> None:
        """Remove a peer from the router.
        
        Args:
            peer_id: MikroTik peer ID (e.g., "*1").
            
        Raises:
            WGPeerManagerError: If the operation fails.
        """
        logger.info(f"Removing peer: {peer_id}")
        
        try:
            self.client.execute("/interface/wireguard/peers/remove", {".id": peer_id})
            logger.info(f"Removed peer {peer_id}")
            
        except ROSCommandError as e:
            raise WGPeerManagerError(self._map_error(str(e)))
    
    def disable_peer(self, peer_id: str) -> None:
        """Disable a peer on the router.
        
        Args:
            peer_id: MikroTik peer ID (e.g., "*1").
            
        Raises:
            WGPeerManagerError: If the operation fails.
        """
        logger.info(f"Disabling peer: {peer_id}")
        
        try:
            self.client.execute(
                "/interface/wireguard/peers/set",
                {".id": peer_id, "disabled": "yes"}
            )
            logger.info(f"Disabled peer {peer_id}")
            
        except ROSCommandError as e:
            raise WGPeerManagerError(self._map_error(str(e)))
    
    def enable_peer(self, peer_id: str) -> None:
        """Enable a peer on the router.
        
        Args:
            peer_id: MikroTik peer ID (e.g., "*1").
            
        Raises:
            WGPeerManagerError: If the operation fails.
        """
        logger.info(f"Enabling peer: {peer_id}")
        
        try:
            self.client.execute(
                "/interface/wireguard/peers/set",
                {".id": peer_id, "disabled": "no"}
            )
            logger.info(f"Enabled peer {peer_id}")
            
        except ROSCommandError as e:
            raise WGPeerManagerError(self._map_error(str(e)))

    def _map_error(self, error_message: str) -> str:
        """Map API error to user-friendly message.
        
        Args:
            error_message: Original error message from API.
            
        Returns:
            User-friendly error message.
        """
        error_lower = error_message.lower()
        
        for pattern, friendly_msg in self.ERROR_MESSAGES.items():
            if pattern in error_lower:
                return friendly_msg
        
        # Return original message if no mapping found
        return error_message
    
    def _parse_handshake(self, handshake_str: Optional[str]) -> Optional[datetime]:
        """Parse MikroTik handshake timestamp.
        
        Args:
            handshake_str: Handshake string from API (e.g., "1h2m3s ago").
            
        Returns:
            Datetime of last handshake, or None if not available.
        """
        if not handshake_str:
            return None
        
        # MikroTik returns relative time like "1h2m3s ago" or absolute timestamps
        # For simplicity, we'll return None for relative times
        # A more complete implementation would parse these
        try:
            # Try ISO format first
            return datetime.fromisoformat(handshake_str)
        except (ValueError, TypeError):
            # Could implement relative time parsing here
            return None
    
    def get_peer_by_public_key(self, interface: str, public_key: str) -> Optional[WGPeer]:
        """Find a peer by its public key.
        
        Args:
            interface: Name of the WireGuard interface.
            public_key: Peer's public key to search for.
            
        Returns:
            WGPeer if found, None otherwise.
        """
        peers = self.list_peers(interface)
        for peer in peers:
            if peer.public_key == public_key:
                return peer
        return None
    
    def get_peer_by_id(self, interface: str, peer_id: str) -> Optional[WGPeer]:
        """Find a peer by its MikroTik ID.
        
        Args:
            interface: Name of the WireGuard interface.
            peer_id: MikroTik peer ID (e.g., "*1").
            
        Returns:
            WGPeer if found, None otherwise.
        """
        peers = self.list_peers(interface)
        for peer in peers:
            if peer.id == peer_id:
                return peer
        return None
