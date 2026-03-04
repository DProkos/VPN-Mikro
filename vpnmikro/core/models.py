"""Data models for VPN Mikro.

This module defines the core data structures used throughout the application,
including Profile, Device, WireGuard interface/peer models, and tunnel status.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class WGInterface:
    """WireGuard interface on MikroTik router.
    
    Attributes:
        name: Interface name (e.g., "wireguard1").
        listen_port: UDP port the interface listens on.
        public_key: Server's public key for client configuration.
    """
    name: str
    listen_port: int
    public_key: str


@dataclass
class WGPeer:
    """WireGuard peer entry on MikroTik router.
    
    Attributes:
        id: MikroTik internal ID (e.g., "*1").
        interface: Name of the WireGuard interface this peer belongs to.
        public_key: Peer's public key.
        allowed_address: Allowed IP address/CIDR for this peer.
        endpoint: Optional endpoint address (IP:port).
        last_handshake: Time of last successful handshake.
        rx_bytes: Bytes received from this peer.
        tx_bytes: Bytes transmitted to this peer.
        disabled: Whether the peer is disabled.
        comment: Optional comment/description.
    """
    id: str
    interface: str
    public_key: str
    allowed_address: str
    endpoint: Optional[str] = None
    last_handshake: Optional[datetime] = None
    rx_bytes: int = 0
    tx_bytes: int = 0
    disabled: bool = False
    comment: Optional[str] = None


@dataclass
class TunnelStatus:
    """Status of a WireGuard tunnel service.
    
    Attributes:
        running: Whether the Windows service is running.
        tunnel_name: Name of the tunnel service.
        last_handshake: Time of last successful handshake (best-effort).
        rx_bytes: Bytes received (best-effort).
        tx_bytes: Bytes transmitted (best-effort).
    """
    running: bool
    tunnel_name: str
    last_handshake: Optional[datetime] = None
    rx_bytes: int = 0
    tx_bytes: int = 0


@dataclass
class Device:
    """Local representation of a VPN client device.
    
    Each device corresponds to one WireGuard peer on the MikroTik router
    and one local configuration file.
    
    Attributes:
        uuid: Unique identifier for this device.
        name: Human-readable device name.
        assigned_ip: IP address allocated from the pool.
        peer_id: MikroTik peer .id reference.
        private_key_encrypted: DPAPI-encrypted private key bytes.
        public_key: Device's public key (not sensitive).
        config_path: Path to the .conf file.
        created_at: When the device was created.
        enabled: Whether the peer is enabled on MikroTik.
        pending_delete: Flag for 2-phase safe deletion.
    """
    uuid: str
    name: str
    assigned_ip: str
    peer_id: str
    private_key_encrypted: bytes
    public_key: str
    config_path: str
    created_at: datetime
    enabled: bool = True
    pending_delete: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        import base64
        return {
            "uuid": self.uuid,
            "name": self.name,
            "assigned_ip": self.assigned_ip,
            "peer_id": self.peer_id,
            "private_key_encrypted": base64.b64encode(self.private_key_encrypted).decode("ascii"),
            "public_key": self.public_key,
            "config_path": self.config_path,
            "created_at": self.created_at.isoformat(),
            "enabled": self.enabled,
            "pending_delete": self.pending_delete,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Device":
        """Create Device from dictionary."""
        import base64
        return cls(
            uuid=data["uuid"],
            name=data["name"],
            assigned_ip=data["assigned_ip"],
            peer_id=data["peer_id"],
            private_key_encrypted=base64.b64decode(data["private_key_encrypted"]),
            public_key=data["public_key"],
            config_path=data["config_path"],
            created_at=datetime.fromisoformat(data["created_at"]),
            enabled=data.get("enabled", True),
            pending_delete=data.get("pending_delete", False),
        )


@dataclass
class Profile:
    """MikroTik connection profile with all settings.
    
    Stores connection credentials (encrypted), selected WireGuard interface,
    network settings, and associated devices.
    
    Attributes:
        name: Profile name/identifier.
        host: MikroTik router IP or hostname.
        port: API-SSL port (default 8729).
        username_encrypted: DPAPI-encrypted username bytes.
        password_encrypted: DPAPI-encrypted password bytes.
        verify_tls: Whether to verify TLS certificates (default OFF).
        selected_interface: Name of selected WireGuard interface.
        endpoint: Public endpoint (domain:port) for client configs.
        server_public_key: WireGuard server's public key.
        ip_pool: CIDR range for IP allocation.
        dns: DNS server override for client configs.
        mtu: MTU value for client configs.
        keepalive: PersistentKeepalive interval.
        tunnel_mode: "full" or "split" tunnel mode.
        split_subnets: List of subnets for split tunnel mode.
        devices: List of devices associated with this profile.
    """
    name: str
    host: str
    port: int = 8729
    username_encrypted: bytes = field(default_factory=bytes)
    password_encrypted: bytes = field(default_factory=bytes)
    verify_tls: bool = False
    selected_interface: Optional[str] = None
    endpoint: Optional[str] = None
    server_public_key: Optional[str] = None
    ip_pool: str = "10.66.0.0/24"
    dns: Optional[str] = None
    mtu: Optional[int] = None
    keepalive: Optional[int] = 20
    tunnel_mode: str = "full"
    split_subnets: list[str] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        import base64
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "username_encrypted": base64.b64encode(self.username_encrypted).decode("ascii") if self.username_encrypted else "",
            "password_encrypted": base64.b64encode(self.password_encrypted).decode("ascii") if self.password_encrypted else "",
            "verify_tls": self.verify_tls,
            "selected_interface": self.selected_interface,
            "endpoint": self.endpoint,
            "server_public_key": self.server_public_key,
            "ip_pool": self.ip_pool,
            "dns": self.dns,
            "mtu": self.mtu,
            "keepalive": self.keepalive,
            "tunnel_mode": self.tunnel_mode,
            "split_subnets": self.split_subnets,
            "devices": [d.to_dict() for d in self.devices],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        """Create Profile from dictionary."""
        import base64
        
        username_enc = data.get("username_encrypted", "")
        password_enc = data.get("password_encrypted", "")
        
        return cls(
            name=data["name"],
            host=data["host"],
            port=data.get("port", 8729),
            username_encrypted=base64.b64decode(username_enc) if username_enc else b"",
            password_encrypted=base64.b64decode(password_enc) if password_enc else b"",
            verify_tls=data.get("verify_tls", False),
            selected_interface=data.get("selected_interface"),
            endpoint=data.get("endpoint"),
            server_public_key=data.get("server_public_key"),
            ip_pool=data.get("ip_pool", "10.66.0.0/24"),
            dns=data.get("dns"),
            mtu=data.get("mtu"),
            keepalive=data.get("keepalive", 20),
            tunnel_mode=data.get("tunnel_mode", "full"),
            split_subnets=data.get("split_subnets", []),
            devices=[Device.from_dict(d) for d in data.get("devices", [])],
        )
