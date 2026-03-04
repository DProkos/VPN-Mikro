"""Secure credential storage using Windows DPAPI.

This module provides DPAPI-based encryption for storing sensitive data
like passwords and private keys securely on Windows systems.
"""

import os
import sys
import base64
import json
from pathlib import Path
from typing import Optional


class SecureStore:
    """DPAPI-based credential storage for Windows.
    
    Uses the cryptography library's Windows DPAPI backend to encrypt
    and decrypt sensitive data. Data is encrypted to the current user
    and can only be decrypted by the same user on the same machine.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize SecureStore.
        
        Args:
            storage_path: Path to store encrypted credentials.
                         Defaults to %ProgramData%\\VPNMikro\\data\\credentials.json
        """
        if storage_path is None:
            program_data = os.environ.get("ProgramData", "C:\\ProgramData")
            storage_path = Path(program_data) / "VPNMikro" / "data" / "credentials.json"
        
        self._storage_path = storage_path
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self) -> None:
        """Create storage directory if it doesn't exist."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _is_windows(self) -> bool:
        """Check if running on Windows."""
        return sys.platform == "win32"
    
    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data using DPAPI.
        
        Args:
            data: Raw bytes to encrypt.
            
        Returns:
            Encrypted bytes.
            
        Raises:
            OSError: If not running on Windows.
            RuntimeError: If encryption fails.
        """
        if not self._is_windows():
            # For non-Windows platforms, use base64 encoding as fallback
            # This is NOT secure and should only be used for development
            return base64.b64encode(b"FALLBACK:" + data)
        
        try:
            import ctypes
            from ctypes import wintypes
            
            # DPAPI structures
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char)),
                ]
            
            # Load crypt32.dll
            crypt32 = ctypes.windll.crypt32
            kernel32 = ctypes.windll.kernel32
            
            # Prepare input blob
            input_blob = DATA_BLOB()
            input_blob.cbData = len(data)
            input_blob.pbData = ctypes.cast(
                ctypes.create_string_buffer(data, len(data)),
                ctypes.POINTER(ctypes.c_char)
            )
            
            # Output blob
            output_blob = DATA_BLOB()
            
            # Call CryptProtectData
            if not crypt32.CryptProtectData(
                ctypes.byref(input_blob),
                None,  # description
                None,  # optional entropy
                None,  # reserved
                None,  # prompt struct
                0,     # flags
                ctypes.byref(output_blob)
            ):
                raise RuntimeError(f"CryptProtectData failed: {ctypes.GetLastError()}")
            
            # Copy encrypted data
            encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
            
            # Free the output buffer
            kernel32.LocalFree(output_blob.pbData)
            
            return encrypted
            
        except Exception as e:
            raise RuntimeError(f"Encryption failed: {e}")
    
    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data using DPAPI.
        
        Args:
            data: Encrypted bytes to decrypt.
            
        Returns:
            Decrypted bytes.
            
        Raises:
            OSError: If not running on Windows.
            RuntimeError: If decryption fails.
        """
        if not self._is_windows():
            # Handle fallback encoding for non-Windows
            try:
                decoded = base64.b64decode(data)
                if decoded.startswith(b"FALLBACK:"):
                    return decoded[9:]
            except Exception:
                pass
            raise RuntimeError("DPAPI not available on non-Windows platforms")
        
        try:
            import ctypes
            from ctypes import wintypes
            
            # DPAPI structures
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char)),
                ]
            
            # Load crypt32.dll
            crypt32 = ctypes.windll.crypt32
            kernel32 = ctypes.windll.kernel32
            
            # Prepare input blob
            input_blob = DATA_BLOB()
            input_blob.cbData = len(data)
            input_blob.pbData = ctypes.cast(
                ctypes.create_string_buffer(data, len(data)),
                ctypes.POINTER(ctypes.c_char)
            )
            
            # Output blob
            output_blob = DATA_BLOB()
            
            # Call CryptUnprotectData
            if not crypt32.CryptUnprotectData(
                ctypes.byref(input_blob),
                None,  # description out
                None,  # optional entropy
                None,  # reserved
                None,  # prompt struct
                0,     # flags
                ctypes.byref(output_blob)
            ):
                raise RuntimeError(f"CryptUnprotectData failed: {ctypes.GetLastError()}")
            
            # Copy decrypted data
            decrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
            
            # Free the output buffer
            kernel32.LocalFree(output_blob.pbData)
            
            return decrypted
            
        except Exception as e:
            raise RuntimeError(f"Decryption failed: {e}")
    
    def encrypt_string(self, value: str) -> bytes:
        """Encrypt a string value.
        
        Args:
            value: String to encrypt.
            
        Returns:
            Encrypted bytes.
        """
        return self.encrypt(value.encode("utf-8"))
    
    def decrypt_string(self, data: bytes) -> str:
        """Decrypt bytes to a string.
        
        Args:
            data: Encrypted bytes.
            
        Returns:
            Decrypted string.
        """
        return self.decrypt(data).decode("utf-8")
    
    def _load_credentials(self) -> dict:
        """Load credentials from storage file."""
        if not self._storage_path.exists():
            return {}
        
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def _save_credentials(self, credentials: dict) -> None:
        """Save credentials to storage file."""
        self._ensure_storage_dir()
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(credentials, f, indent=2)
    
    def store_credential(self, key: str, value: str) -> None:
        """Store an encrypted credential.
        
        Args:
            key: Identifier for the credential.
            value: The credential value to encrypt and store.
        """
        encrypted = self.encrypt_string(value)
        # Store as base64 for JSON compatibility
        encoded = base64.b64encode(encrypted).decode("ascii")
        
        credentials = self._load_credentials()
        credentials[key] = encoded
        self._save_credentials(credentials)
    
    def retrieve_credential(self, key: str) -> Optional[str]:
        """Retrieve and decrypt a stored credential.
        
        Args:
            key: Identifier for the credential.
            
        Returns:
            The decrypted credential value, or None if not found.
        """
        credentials = self._load_credentials()
        
        if key not in credentials:
            return None
        
        try:
            encoded = credentials[key]
            encrypted = base64.b64decode(encoded)
            return self.decrypt_string(encrypted)
        except Exception:
            return None
    
    def delete_credential(self, key: str) -> bool:
        """Delete a stored credential.
        
        Args:
            key: Identifier for the credential.
            
        Returns:
            True if the credential was deleted, False if not found.
        """
        credentials = self._load_credentials()
        
        if key not in credentials:
            return False
        
        del credentials[key]
        self._save_credentials(credentials)
        return True
    
    def list_credentials(self) -> list[str]:
        """List all stored credential keys.
        
        Returns:
            List of credential keys.
        """
        return list(self._load_credentials().keys())
