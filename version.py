#!/usr/bin/env python3
"""
VPN Mikro Version Manager
=========================
Script to update version number across all project files.

Usage:
    python version.py                    # Show current version
    python version.py 0.0.2              # Set new version
    python version.py --bump patch       # Bump patch: 0.0.1 -> 0.0.2
    python version.py --bump minor       # Bump minor: 0.0.1 -> 0.1.0
    python version.py --bump major       # Bump major: 0.0.1 -> 1.0.0
"""

import re
import sys
from pathlib import Path

# Files that contain version information
VERSION_FILES = [
    ("vpnmikro/ui/about_dialog.py", r'VERSION = "[^"]+"', 'VERSION = "{version}"'),
    ("build.py", r'APP_VERSION = "[^"]+"', 'APP_VERSION = "{version}"'),
    ("pyproject.toml", r'version = "[^"]+"', 'version = "{version}"'),
]


def get_current_version() -> str:
    """Get current version from about_dialog.py."""
    about_file = Path("vpnmikro/ui/about_dialog.py")
    if not about_file.exists():
        return "0.0.0"
    
    content = about_file.read_text(encoding="utf-8")
    match = re.search(r'VERSION = "([^"]+)"', content)
    if match:
        return match.group(1)
    return "0.0.0"


def parse_version(version: str) -> tuple:
    """Parse version string to tuple (major, minor, patch)."""
    parts = version.split(".")
    return (
        int(parts[0]) if len(parts) > 0 else 0,
        int(parts[1]) if len(parts) > 1 else 0,
        int(parts[2]) if len(parts) > 2 else 0,
    )


def bump_version(current: str, bump_type: str) -> str:
    """Bump version based on type."""
    major, minor, patch = parse_version(current)
    
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")


def update_version(new_version: str) -> bool:
    """Update version in all files."""
    print(f"\nUpdating version to: {new_version}\n")
    
    success = True
    for file_path, pattern, replacement in VERSION_FILES:
        path = Path(file_path)
        if not path.exists():
            print(f"  ⚠ File not found: {file_path}")
            continue
        
        content = path.read_text(encoding="utf-8")
        new_content = re.sub(pattern, replacement.format(version=new_version), content)
        
        if content != new_content:
            path.write_text(new_content, encoding="utf-8")
            print(f"  ✓ Updated: {file_path}")
        else:
            print(f"  - No change: {file_path}")
    
    return success


def main():
    current = get_current_version()
    
    if len(sys.argv) == 1:
        # Show current version
        print(f"\nVPN Mikro Version: {current}\n")
        print("Usage:")
        print("  python version.py 0.0.2          # Set specific version")
        print("  python version.py --bump patch   # Bump patch version")
        print("  python version.py --bump minor   # Bump minor version")
        print("  python version.py --bump major   # Bump major version")
        return
    
    if sys.argv[1] == "--bump":
        if len(sys.argv) < 3:
            print("Error: Specify bump type (major, minor, patch)")
            sys.exit(1)
        
        bump_type = sys.argv[2].lower()
        new_version = bump_version(current, bump_type)
    else:
        new_version = sys.argv[1]
        # Validate version format
        if not re.match(r'^\d+\.\d+\.\d+$', new_version):
            print(f"Error: Invalid version format: {new_version}")
            print("Expected format: X.Y.Z (e.g., 0.0.1)")
            sys.exit(1)
    
    print(f"Current version: {current}")
    update_version(new_version)
    print(f"\n✓ Version updated to {new_version}")


if __name__ == "__main__":
    main()
