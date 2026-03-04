"""Core business logic and utilities."""

# Import modules that don't have circular dependencies first
from .secure_store import SecureStore
from .models import Profile, Device, WGInterface, WGPeer, TunnelStatus
from .profiles import ProfileManager
from .ip_allocator import IPAllocator
from .wg_config import WGConfigBuilder
from .rate_limiter import RateLimiter
from .wg_controller_win import (
    WGController,
    WGControllerError,
    AdminRightsError,
    TunnelInstallError,
    TunnelUninstallError,
)

# Lazy import for DeviceManager to avoid circular imports
# DeviceManager imports from mikrotik.wg_manager which imports from core.logger
def __getattr__(name):
    if name in (
        "DeviceManager",
        "DeviceManagerError",
        "DeviceCreationError",
        "DeviceDeletionError",
        "DeviceNotFoundError",
        "PoolExhaustedError",
    ):
        from .device_manager import (
            DeviceManager,
            DeviceManagerError,
            DeviceCreationError,
            DeviceDeletionError,
            DeviceNotFoundError,
            PoolExhaustedError,
        )
        return {
            "DeviceManager": DeviceManager,
            "DeviceManagerError": DeviceManagerError,
            "DeviceCreationError": DeviceCreationError,
            "DeviceDeletionError": DeviceDeletionError,
            "DeviceNotFoundError": DeviceNotFoundError,
            "PoolExhaustedError": PoolExhaustedError,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "SecureStore",
    "Profile",
    "Device",
    "WGInterface",
    "WGPeer",
    "TunnelStatus",
    "ProfileManager",
    "IPAllocator",
    "WGConfigBuilder",
    "RateLimiter",
    "WGController",
    "WGControllerError",
    "AdminRightsError",
    "TunnelInstallError",
    "TunnelUninstallError",
    "DeviceManager",
    "DeviceManagerError",
    "DeviceCreationError",
    "DeviceDeletionError",
    "DeviceNotFoundError",
    "PoolExhaustedError",
]
