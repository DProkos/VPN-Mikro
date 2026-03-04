"""IP address allocation from CIDR pool.

This module provides IP address allocation functionality for WireGuard peers,
ensuring unique addresses are assigned from a configured pool while excluding
network (.0) and gateway (.1) addresses.
"""

import ipaddress
from typing import Optional, Set


class IPAllocator:
    """IP address allocation from a CIDR pool.
    
    Allocates unique IP addresses from a configured CIDR range,
    excluding network address (.0) and gateway address (.1).
    
    Attributes:
        pool_cidr: The CIDR string defining the IP pool.
        network: The parsed IPv4Network object.
    """
    
    def __init__(self, pool_cidr: str) -> None:
        """Initialize the allocator with a CIDR pool.
        
        Args:
            pool_cidr: CIDR notation string (e.g., "10.66.0.0/24").
            
        Raises:
            ValueError: If the CIDR string is invalid.
        """
        self.pool_cidr = pool_cidr
        try:
            self.network = ipaddress.IPv4Network(pool_cidr, strict=False)
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError) as e:
            raise ValueError(f"Invalid CIDR format: {pool_cidr}") from e
    
    @property
    def network_address(self) -> str:
        """Get the network address (.0)."""
        return str(self.network.network_address)
    
    @property
    def gateway_address(self) -> str:
        """Get the gateway address (.1)."""
        return str(self.network.network_address + 1)
    
    @property
    def usable_host_count(self) -> int:
        """Get the number of usable host addresses.
        
        This equals 2^(32-prefix) - 2 (excluding network and broadcast).
        For our purposes, we also exclude .1 (gateway), so actual usable = num_addresses - 3.
        However, per the design spec, usable_host_count should equal 2^(32-prefix) - 2.
        """
        # Standard formula: total hosts minus network and broadcast
        return self.network.num_addresses - 2
    
    def _get_excluded_addresses(self) -> Set[str]:
        """Get addresses that should never be allocated.
        
        Returns:
            Set of IP addresses to exclude (.0 network and .1 gateway).
        """
        return {
            self.network_address,
            self.gateway_address,
        }
    
    def get_used_ips(self, peers: list[dict]) -> Set[str]:
        """Extract used IP addresses from peer list.
        
        Args:
            peers: List of peer dictionaries with 'allowed_address' field.
                   The allowed_address may be in CIDR format (e.g., "10.66.0.5/32").
        
        Returns:
            Set of IP addresses currently in use.
        """
        used = set()
        for peer in peers:
            allowed = peer.get("allowed_address", peer.get("allowed-address", ""))
            if allowed:
                # Strip CIDR suffix if present (e.g., "10.66.0.5/32" -> "10.66.0.5")
                ip_str = allowed.split("/")[0]
                try:
                    # Validate it's a proper IP
                    ipaddress.IPv4Address(ip_str)
                    used.add(ip_str)
                except ipaddress.AddressValueError:
                    # Skip invalid addresses
                    continue
        return used
    
    def allocate_next(self, used_ips: Set[str]) -> Optional[str]:
        """Allocate the next available IP address.
        
        Args:
            used_ips: Set of IP addresses already in use.
        
        Returns:
            The next available IP address, or None if pool is exhausted.
        """
        excluded = self._get_excluded_addresses()
        all_unavailable = used_ips | excluded
        
        # Iterate through all hosts in the network
        for host in self.network.hosts():
            ip_str = str(host)
            if ip_str not in all_unavailable:
                return ip_str
        
        return None
    
    def release_ip(self, ip: str) -> None:
        """Release an IP address back to the pool.
        
        This is a no-op since we don't maintain internal state of allocations.
        The used_ips set is passed to allocate_next() each time.
        
        Args:
            ip: The IP address to release.
        """
        # No-op: allocation state is managed externally via used_ips parameter
        pass
    
    def is_pool_exhausted(self, used_ips: Set[str]) -> bool:
        """Check if the IP pool is exhausted.
        
        Args:
            used_ips: Set of IP addresses already in use.
        
        Returns:
            True if no more addresses can be allocated.
        """
        return self.allocate_next(used_ips) is None
    
    def is_ip_in_pool(self, ip: str) -> bool:
        """Check if an IP address is within the pool range.
        
        Args:
            ip: The IP address to check.
        
        Returns:
            True if the IP is within the pool's network range.
        """
        try:
            addr = ipaddress.IPv4Address(ip)
            return addr in self.network
        except ipaddress.AddressValueError:
            return False
    
    def __repr__(self) -> str:
        return f"IPAllocator(pool_cidr='{self.pool_cidr}')"
