# VPN Mikro Documentation

VPN Mikro is a PyQt6 desktop application for Windows that provides a modern interface for managing WireGuard VPN connections. It supports both MikroTik router integration and standalone client-only mode.

**Author:** Dionisis Prokos  
**Version:** 0.0.3  
**License:** Proprietary - See Terms of Service

## Table of Contents

- [Quick Start Guide](Docs/QUICK_START.md)
- [User Guide](Docs/USER_GUIDE.md)
- [MikroTik Setup](Docs/MIKROTIK_SETUP.md)
- [Troubleshooting](Docs/TROUBLESHOOTING.md)
- [Build Guide](Docs/BUILD.md)
- [Update Server Setup](Docs/UPDATE_SERVER.md)
- [Changelog](Docs/CHANGELOG.md)

## Features

### Core Features
- 🔐 Secure credential storage using Windows DPAPI
- 🌐 MikroTik router integration via API
- 📱 QR code generation for mobile device setup
- 🔄 Real-time traffic statistics (non-blocking)
- 🖥️ System tray integration with custom logo
- 💾 Settings persistence between sessions
- 🔄 Automatic peer sync from MikroTik
- 🔄 Auto-update system with changelog display
- 📋 Terms of Service and licensing

### Client Modes
1. **MikroTik Mode**: Full integration with MikroTik routers for automatic peer management
2. **Client-Only Mode**: Manual VPN profile creation without MikroTik

### UI Features
- Modern dark theme dashboard
- Custom application logo in title bar and tray
- All VPN clients view with profile highlighting
- One-click connect/disconnect
- Traffic statistics (rx/tx bytes) - updated in background
- Device management table with click-to-select
- Transparent labels for clean appearance
- Resizable table columns with saved positions

### Performance
- Background thread for traffic statistics (no UI freeze)
- Real-time MikroTik connection monitoring (every 5 seconds)
- Hidden PowerShell windows for all system commands

## System Requirements

- Windows 10/11 (64-bit)
- Administrator rights (for VPN tunnel installation)
- Network access to MikroTik router (if using MikroTik mode)

## Installation

1. Download the latest release installer (`VPNMikro-Setup-x.x.x.exe`)
2. Run the installer (requires Administrator)
3. Launch VPN Mikro from Start Menu or Desktop shortcut

No additional software installation required - WireGuard binaries are bundled.

## Quick Links

- [Create your first VPN profile](QUICK_START.md#first-profile)
- [Connect to MikroTik router](MIKROTIK_SETUP.md)
- [Import existing WireGuard config](USER_GUIDE.md#import-config)
- [Export config for mobile](USER_GUIDE.md#export-qr)
- [Build from source](BUILD.md)
