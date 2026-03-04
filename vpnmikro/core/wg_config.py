"""WireGuard configuration file generator.

This module provides functionality for generating WireGuard keypairs,
preshared keys, and configuration files for VPN clients.

Uses PyNaCl/libsodium for Curve25519 key generation - NO custom crypto.
"""

import base64
import secrets
from pathlib import Path
from typing import Optional

from nacl.bindings import crypto_scalarmult_base


class WGConfigBuilder:
    """WireGuard configuration file generator.
    
    Uses PyNaCl/libsodium for Curve25519 key generation.
    NO custom crypto - only random + clamp + encode.
    """
    
    # WireGuard config template
    CONFIG_TEMPLATE = """[Interface]
PrivateKey = {private_key}
Address = {address}/32
{dns_line}{mtu_line}
[Peer]
PublicKey = {server_public_key}
Endpoint = {endpoint}
AllowedIPs = {allowed_ips}
{keepalive_line}"""

    @staticmethod
    def _clamp_private_key(key: bytes) -> bytes:
        """Clamp a 32-byte key per Curve25519 spec.
        
        Per RFC 7748, the private key must be clamped:
        - Clear bits 0, 1, 2 of the first byte
        - Clear bit 7 of the last byte
        - Set bit 6 of the last byte
        
        Args:
            key: 32 random bytes.
            
        Returns:
            Clamped 32-byte key suitable for Curve25519.
        """
        key_list = list(key)
        key_list[0] &= 248   # Clear bits 0, 1, 2
        key_list[31] &= 127  # Clear bit 7
        key_list[31] |= 64   # Set bit 6
        return bytes(key_list)

    @staticmethod
    def generate_keypair() -> tuple[str, str]:
        """Generate WireGuard keypair using PyNaCl/libsodium.
        
        Returns:
            Tuple of (private_key_b64, public_key_b64) in WireGuard format.
            - Private key: 32 random bytes, clamped per Curve25519 spec
            - Public key: crypto_scalarmult_base(private_key)
            - Both base64 encoded
        """
        # Generate 32 random bytes for private key
        private_key_raw = secrets.token_bytes(32)
        
        # Clamp per Curve25519 spec
        private_key_clamped = WGConfigBuilder._clamp_private_key(private_key_raw)
        
        # Derive public key using libsodium's crypto_scalarmult_base
        public_key_raw = crypto_scalarmult_base(private_key_clamped)
        
        # Base64 encode both keys
        private_key_b64 = base64.b64encode(private_key_clamped).decode("ascii")
        public_key_b64 = base64.b64encode(public_key_raw).decode("ascii")
        
        return private_key_b64, public_key_b64
    
    @staticmethod
    def generate_preshared_key() -> str:
        """Generate optional preshared key.
        
        Returns:
            32 random bytes, base64 encoded.
        """
        psk_raw = secrets.token_bytes(32)
        return base64.b64encode(psk_raw).decode("ascii")
    
    @staticmethod
    def get_allowed_ips(tunnel_mode: str, split_subnets: Optional[list[str]] = None) -> str:
        """Get AllowedIPs string based on tunnel mode.
        
        Args:
            tunnel_mode: "full" for all traffic, "split" for specific subnets.
            split_subnets: List of CIDR subnets for split mode.
            
        Returns:
            Comma-separated AllowedIPs string.
        """
        if tunnel_mode == "full":
            return "0.0.0.0/0, ::/0"
        elif tunnel_mode == "split":
            if split_subnets:
                return ", ".join(split_subnets)
            # Default to private ranges if no subnets specified
            return "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16"
        else:
            # Default to full tunnel for unknown modes
            return "0.0.0.0/0, ::/0"

    def build_config(
        self,
        private_key: str,
        address: str,
        server_public_key: str,
        endpoint: str,
        tunnel_mode: str = "full",
        split_subnets: Optional[list[str]] = None,
        dns: Optional[str] = None,
        mtu: Optional[int] = None,
        keepalive: Optional[int] = 25,
    ) -> str:
        """Build a WireGuard configuration file content.
        
        Args:
            private_key: Base64-encoded private key.
            address: Client IP address (without /32 suffix).
            server_public_key: Server's base64-encoded public key.
            endpoint: Server endpoint (domain:port or ip:port).
            tunnel_mode: "full" or "split" tunnel mode.
            split_subnets: List of CIDR subnets for split mode.
            dns: Optional DNS server override.
            mtu: Optional MTU value.
            keepalive: Optional PersistentKeepalive interval (default 25).
            
        Returns:
            Complete WireGuard configuration file content.
        """
        # Build optional lines
        dns_line = f"DNS = {dns}\n" if dns else ""
        mtu_line = f"MTU = {mtu}\n" if mtu else ""
        keepalive_line = f"PersistentKeepalive = {keepalive}" if keepalive else ""
        
        # Get AllowedIPs based on tunnel mode
        allowed_ips = self.get_allowed_ips(tunnel_mode, split_subnets)
        
        # Format the config
        config = self.CONFIG_TEMPLATE.format(
            private_key=private_key,
            address=address,
            dns_line=dns_line,
            mtu_line=mtu_line,
            server_public_key=server_public_key,
            endpoint=endpoint,
            allowed_ips=allowed_ips,
            keepalive_line=keepalive_line,
        )
        
        # Clean up any double newlines from optional fields
        while "\n\n\n" in config:
            config = config.replace("\n\n\n", "\n\n")
        
        return config.strip() + "\n"
    
    def write_config(self, config: str, path: Path) -> None:
        """Write configuration content to a file.
        
        Creates parent directories if they don't exist.
        
        Args:
            config: Configuration file content.
            path: Path to write the .conf file.
        """
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write config file
        path.write_text(config, encoding="utf-8")
