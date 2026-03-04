"""Profile management with JSON persistence.

This module provides the ProfileManager class for managing MikroTik
connection profiles, including save/load/delete operations with
encrypted credential storage.
"""

import json
import os
from pathlib import Path
from typing import Optional

from .models import Profile
from .secure_store import SecureStore


class ProfileManager:
    """Manages MikroTik connection profiles with JSON persistence.
    
    Profiles are stored in %ProgramData%\\VPNMikro\\data\\profiles.json.
    Sensitive fields (username, password) are encrypted using DPAPI
    via SecureStore before storage.
    """
    
    def __init__(
        self,
        storage_path: Optional[Path] = None,
        secure_store: Optional[SecureStore] = None
    ):
        """Initialize ProfileManager.
        
        Args:
            storage_path: Path to profiles.json file.
                         Defaults to %ProgramData%\\VPNMikro\\data\\profiles.json
            secure_store: SecureStore instance for credential encryption.
                         Creates a new instance if not provided.
        """
        if storage_path is None:
            program_data = os.environ.get("ProgramData", "C:\\ProgramData")
            storage_path = Path(program_data) / "VPNMikro" / "data" / "profiles.json"
        
        self._storage_path = storage_path
        self._secure_store = secure_store or SecureStore()
        self._current_profile_name: Optional[str] = None
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self) -> None:
        """Create storage directory if it doesn't exist."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_all_profiles(self) -> dict:
        """Load all profiles from storage file.
        
        Returns:
            Dictionary mapping profile names to profile data.
        """
        if not self._storage_path.exists():
            return {"profiles": {}, "current": None}
        
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Handle legacy format without wrapper
                if "profiles" not in data:
                    return {"profiles": data, "current": None}
                return data
        except (json.JSONDecodeError, IOError):
            return {"profiles": {}, "current": None}
    
    def _save_all_profiles(self, data: dict) -> None:
        """Save all profiles to storage file.
        
        Args:
            data: Dictionary with "profiles" and "current" keys.
        """
        self._ensure_storage_dir()
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    
    def list_profiles(self) -> list[str]:
        """List all saved profile names.
        
        Returns:
            List of profile names.
        """
        data = self._load_all_profiles()
        return list(data["profiles"].keys())
    
    def load_profile(self, name: str) -> Profile:
        """Load a profile by name.
        
        Args:
            name: Profile name to load.
            
        Returns:
            The loaded Profile object.
            
        Raises:
            KeyError: If profile doesn't exist.
        """
        data = self._load_all_profiles()
        
        if name not in data["profiles"]:
            raise KeyError(f"Profile '{name}' not found")
        
        return Profile.from_dict(data["profiles"][name])
    
    def save_profile(self, profile: Profile) -> None:
        """Save a profile.
        
        If a profile with the same name exists, it will be overwritten.
        
        Args:
            profile: Profile object to save.
        """
        data = self._load_all_profiles()
        data["profiles"][profile.name] = profile.to_dict()
        self._save_all_profiles(data)
    
    def delete_profile(self, name: str) -> bool:
        """Delete a profile by name.
        
        Args:
            name: Profile name to delete.
            
        Returns:
            True if profile was deleted, False if not found.
        """
        data = self._load_all_profiles()
        
        if name not in data["profiles"]:
            return False
        
        del data["profiles"][name]
        
        # Clear current if it was the deleted profile
        if data["current"] == name:
            data["current"] = None
            self._current_profile_name = None
        
        self._save_all_profiles(data)
        return True
    
    def get_current_profile(self) -> Optional[Profile]:
        """Get the currently active profile.
        
        Returns:
            The current Profile, or None if no profile is selected.
        """
        data = self._load_all_profiles()
        current_name = self._current_profile_name or data.get("current")
        
        if current_name and current_name in data["profiles"]:
            return Profile.from_dict(data["profiles"][current_name])
        
        return None
    
    def set_current_profile(self, name: str) -> None:
        """Set the current active profile.
        
        Args:
            name: Profile name to set as current.
            
        Raises:
            KeyError: If profile doesn't exist.
        """
        data = self._load_all_profiles()
        
        if name not in data["profiles"]:
            raise KeyError(f"Profile '{name}' not found")
        
        data["current"] = name
        self._current_profile_name = name
        self._save_all_profiles(data)
    
    def profile_exists(self, name: str) -> bool:
        """Check if a profile exists.
        
        Args:
            name: Profile name to check.
            
        Returns:
            True if profile exists, False otherwise.
        """
        data = self._load_all_profiles()
        return name in data["profiles"]
    
    def device_name_exists(self, device_name: str, exclude_profile: str = None) -> Optional[str]:
        """Check if a device name exists in any profile.
        
        Args:
            device_name: Device name to check.
            exclude_profile: Profile name to exclude from check.
            
        Returns:
            Profile name where device exists, or None if not found.
        """
        data = self._load_all_profiles()
        
        for profile_name, profile_data in data["profiles"].items():
            if exclude_profile and profile_name == exclude_profile:
                continue
            
            devices = profile_data.get("devices", [])
            for device in devices:
                if device.get("name", "").lower() == device_name.lower():
                    return profile_name
        
        return None
    
    def fix_duplicate_device_names(self) -> list[str]:
        """Find and fix duplicate device names across all profiles.
        
        Renames duplicates by appending profile name.
        
        Returns:
            List of messages describing fixes made.
        """
        data = self._load_all_profiles()
        fixes = []
        seen_names = {}  # name -> (profile_name, device_index)
        
        for profile_name, profile_data in data["profiles"].items():
            devices = profile_data.get("devices", [])
            
            for i, device in enumerate(devices):
                device_name = device.get("name", "")
                name_lower = device_name.lower()
                
                if name_lower in seen_names:
                    # Duplicate found - rename this one
                    original_profile, _ = seen_names[name_lower]
                    new_name = f"{device_name}_{profile_name}"
                    
                    # Make sure new name is also unique
                    counter = 1
                    while new_name.lower() in seen_names:
                        new_name = f"{device_name}_{profile_name}_{counter}"
                        counter += 1
                    
                    fixes.append(
                        f"Renamed '{device_name}' in '{profile_name}' to '{new_name}' "
                        f"(duplicate of device in '{original_profile}')"
                    )
                    device["name"] = new_name
                    seen_names[new_name.lower()] = (profile_name, i)
                else:
                    seen_names[name_lower] = (profile_name, i)
        
        if fixes:
            self._save_all_profiles(data)
        
        return fixes
    
    def encrypt_credentials(self, username: str, password: str) -> tuple[bytes, bytes]:
        """Encrypt username and password for storage.
        
        Args:
            username: Plain text username.
            password: Plain text password.
            
        Returns:
            Tuple of (encrypted_username, encrypted_password).
        """
        return (
            self._secure_store.encrypt_string(username),
            self._secure_store.encrypt_string(password)
        )
    
    def decrypt_credentials(self, profile: Profile) -> tuple[str, str]:
        """Decrypt username and password from a profile.
        
        Args:
            profile: Profile with encrypted credentials.
            
        Returns:
            Tuple of (username, password).
            
        Raises:
            RuntimeError: If decryption fails.
        """
        username = ""
        password = ""
        
        if profile.username_encrypted:
            username = self._secure_store.decrypt_string(profile.username_encrypted)
        
        if profile.password_encrypted:
            password = self._secure_store.decrypt_string(profile.password_encrypted)
        
        return username, password
    
    def create_profile(
        self,
        name: str,
        host: str,
        username: str,
        password: str,
        port: int = 8729,
        verify_tls: bool = False,
        **kwargs
    ) -> Profile:
        """Create a new profile with encrypted credentials.
        
        This is a convenience method that handles credential encryption.
        
        Args:
            name: Profile name.
            host: MikroTik router IP or hostname.
            username: Plain text username (will be encrypted).
            password: Plain text password (will be encrypted).
            port: API-SSL port (default 8729).
            verify_tls: Whether to verify TLS certificates.
            **kwargs: Additional Profile fields.
            
        Returns:
            The created Profile object (not yet saved).
        """
        username_enc, password_enc = self.encrypt_credentials(username, password)
        
        return Profile(
            name=name,
            host=host,
            port=port,
            username_encrypted=username_enc,
            password_encrypted=password_enc,
            verify_tls=verify_tls,
            **kwargs
        )
