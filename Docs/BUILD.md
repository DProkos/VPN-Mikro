# Building VPN Mikro

This guide explains how to build VPN Mikro as a standalone Windows executable.

## Prerequisites

1. **Python 3.11+**
2. **Nuitka**: `pip install nuitka`
3. **NSIS** (optional, for installer): Download from https://nsis.sourceforge.io/Download
4. **Visual Studio Build Tools** (for C compilation)

## Build Script

The `build.py` script handles the entire build process.

### Usage

```bash
# Build everything (onedir + installer)
python build.py

# Build only standalone folder
python build.py onedir

# Build only NSIS installer (requires onedir first)
python build.py nsis
```

### Output

After building, you'll find:

- `dist/VPNMikro/` - Portable standalone folder
  - `VPNMikro.exe` - Main executable (~15 MB)
  - `logo/` - Application logos
  - `assets/` - UI assets
  - `wintun/` - WireGuard binaries
  - `licenses/` - License and Terms of Service files
  
- `dist/VPNMikro-Setup-0.0.3.exe` - NSIS installer (~500 KB compressed)

## Logo Files

The build uses these logo files from the `logo/` folder:

| File | Usage |
|------|-------|
| `logo-main.ico` | EXE icon, installer icon, shortcuts |
| `logo_no_BG.ico` | Window title bar, system tray |
| `logo_no_BG.png` | Top bar logo in application |

## Administrator Rights

The application requires administrator rights for WireGuard tunnel management. This is handled by:

1. **UAC Admin flag**: Nuitka builds with `--windows-uac-admin` to request elevation on launch
2. **NSIS installer**: Requests admin rights during installation

## Build Configuration

Edit `build.py` to change:

```python
APP_NAME = "VPNMikro"
APP_VERSION = "0.0.3"
APP_PUBLISHER = "Dionisis Prokos"
APP_DESCRIPTION = "WireGuard VPN Manager for MikroTik"
```

## Build Optimizations

The build script includes several optimizations:

- `--lto=yes` - Link-time optimization for smaller, faster code
- `--remove-output` - Removes intermediate build files
- `--windows-console-mode=disable` - No console window
- `creationflags=subprocess.CREATE_NO_WINDOW` - Hidden PowerShell windows

## NSIS Installer Features

The installer includes:
- Welcome and license pages
- Custom install directory selection
- Start Menu shortcuts with icons
- Desktop shortcut
- Add/Remove Programs entry
- Uninstaller with optional data cleanup

## Troubleshooting

### Nuitka not found
```bash
pip install nuitka
```

### NSIS not found
The build script auto-detects NSIS in common locations:
- `C:\Program Files (x86)\NSIS\`
- `C:\Program Files\NSIS\`

If not found, download and install NSIS from https://nsis.sourceforge.io/Download

### Missing icon
Ensure `logo/logo-main.ico` exists. Create from PNG using online converter if needed.

### Build fails with PyQt6 errors
```bash
pip install --upgrade nuitka pyqt6
```

### Installer output in wrong location
The installer is created in `dist/VPNMikro-Setup-X.X.X.exe`

### PowerShell window appears during operation
This was fixed in v0.0.3 by adding `creationflags=subprocess.CREATE_NO_WINDOW` to all subprocess calls.
