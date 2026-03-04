"""QR code generation for WireGuard configurations.

This module provides functionality for generating QR codes from WireGuard
configuration content, compatible with the WireGuard mobile app import feature.

Requirements: 5.2, 5.3
"""

import io
from pathlib import Path
from typing import Optional

import qrcode
from qrcode.constants import ERROR_CORRECT_L


class QRGenerator:
    """Generate QR codes from WireGuard configuration content.
    
    The generated QR codes are compatible with the WireGuard mobile app
    import feature, allowing users to scan and import configurations directly.
    """
    
    # QR code settings optimized for WireGuard configs
    DEFAULT_BOX_SIZE = 10
    DEFAULT_BORDER = 4
    
    @staticmethod
    def generate_qr_image(config_content: str, box_size: int = DEFAULT_BOX_SIZE, 
                          border: int = DEFAULT_BORDER):
        """Generate a QR code image from configuration content.
        
        Args:
            config_content: WireGuard configuration file content.
            box_size: Size of each box in pixels (default 10).
            border: Border size in boxes (default 4).
            
        Returns:
            PIL Image object containing the QR code.
        """
        qr = qrcode.QRCode(
            version=None,  # Auto-determine version based on data
            error_correction=ERROR_CORRECT_L,
            box_size=box_size,
            border=border,
        )
        qr.add_data(config_content)
        qr.make(fit=True)
        
        return qr.make_image(fill_color="black", back_color="white")
    
    @staticmethod
    def generate_qr_bytes(config_content: str, format: str = "PNG") -> bytes:
        """Generate QR code as bytes for embedding in UI.
        
        Args:
            config_content: WireGuard configuration file content.
            format: Image format (PNG, JPEG, etc.).
            
        Returns:
            Image data as bytes.
        """
        img = QRGenerator.generate_qr_image(config_content)
        
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        buffer.seek(0)
        
        return buffer.getvalue()
    
    @staticmethod
    def save_qr_image(config_content: str, output_path: Path) -> None:
        """Save QR code image to a file.
        
        Args:
            config_content: WireGuard configuration file content.
            output_path: Path to save the image file.
        """
        img = QRGenerator.generate_qr_image(config_content)
        
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        img.save(str(output_path))
    
    @staticmethod
    def generate_from_config_file(config_path: Path) -> bytes:
        """Generate QR code from a configuration file.
        
        Args:
            config_path: Path to the .conf file.
            
        Returns:
            PNG image data as bytes.
            
        Raises:
            FileNotFoundError: If config file doesn't exist.
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        config_content = config_path.read_text(encoding="utf-8")
        return QRGenerator.generate_qr_bytes(config_content)
