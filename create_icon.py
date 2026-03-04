#!/usr/bin/env python3
"""
Create ICO file for VPN Mikro.

Requirements:
    pip install pillow

This creates a simple icon. For better quality from SVG, use online converters:
- https://convertio.co/svg-ico/
- https://cloudconvert.com/svg-to-ico
"""

import sys
from pathlib import Path

ICO_PATH = Path("logo/logo.ico")
PNG_PATH = Path("logo/logo.png")

def create_ico():
    """Create a simple ICO file."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Missing Pillow. Install with:")
        print("  pip install pillow")
        sys.exit(1)
    
    print("Creating icon...")
    
    # Create a 256x256 image
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw rounded rectangle background (blue)
    padding = 20
    draw.rounded_rectangle(
        [padding, padding, size - padding, size - padding],
        radius=30,
        fill=(30, 60, 114, 255)
    )
    
    # Draw "V" shape for VPN
    cx, cy = size // 2, size // 2
    v_points = [
        (cx - 70, cy - 50),
        (cx, cy + 60),
        (cx + 70, cy - 50),
        (cx + 50, cy - 50),
        (cx, cy + 20),
        (cx - 50, cy - 50),
    ]
    draw.polygon(v_points, fill=(100, 200, 255, 255))
    
    # Save as PNG
    img.save(PNG_PATH, format='PNG')
    print(f"Created: {PNG_PATH}")
    
    # Save as ICO
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ICO_PATH, format='ICO', sizes=sizes)
    print(f"Created: {ICO_PATH}")
    
    print("\nDone! Run: python build.py")


if __name__ == "__main__":
    create_ico()
