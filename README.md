# VPN Mikro

<p align="center">
  <img src="logo/logo_no_BG.png" alt="VPN Mikro Logo" width="128" height="128">
</p>

<p align="center">
  <strong>WireGuard VPN Manager για MikroTik Routers</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.0.5-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.11%2B-green.svg" alt="Python">
  <img src="https://img.shields.io/badge/license-Proprietary-red.svg" alt="License">
</p>

---
## Download Exe

[⬇ Download Outlook Credential Cleaner](https://github.com/DProkos/VPN-Mikro/releases/download/VPN/VPNMikro-Setup-0.0.5.exe)


VPN Mikro είναι μια PyQt6 desktop εφαρμογή για Windows που παρέχει ένα σύγχρονο interface για τη διαχείριση WireGuard VPN συνδέσεων. Υποστηρίζει τόσο ολοκλήρωση με MikroTik routers όσο και standalone client-only mode.

## ✨ Χαρακτηριστικά

### Βασικά
- 🔐 Ασφαλής αποθήκευση credentials με Windows DPAPI
- 🌐 Ολοκλήρωση με MikroTik routers μέσω API
- 📱 Δημιουργία QR codes για mobile συσκευές
- 🔄 Real-time στατιστικά traffic (non-blocking)
- 🖥️ System tray integration
- 💾 Αποθήκευση ρυθμίσεων μεταξύ sessions
- 🔄 Αυτόματος συγχρονισμός peers από MikroTik
- 🔄 Auto-update σύστημα με changelog

### Modes Λειτουργίας
1. **MikroTik Mode**: Πλήρης ολοκλήρωση με MikroTik routers για αυτόματη διαχείριση peers
2. **Client-Only Mode**: Χειροκίνητη δημιουργία VPN profiles χωρίς MikroTik

### UI
- Modern dark theme dashboard
- Custom application logo σε title bar και tray
- One-click connect/disconnect
- Traffic statistics (rx/tx bytes)
- Device management table με click-to-select
- Resizable table columns

## 📋 Απαιτήσεις Συστήματος

- Windows 10/11 (64-bit)
- Administrator rights (για εγκατάσταση VPN tunnel)
- Network πρόσβαση σε MikroTik router (αν χρησιμοποιείτε MikroTik mode)

## 🚀 Εγκατάσταση

### Από Installer (Συνιστάται)
1. Κατεβάστε το τελευταίο release (`VPNMikro-Setup-x.x.x.exe`)
2. Τρέξτε τον installer (απαιτεί Administrator)
3. Εκκινήστε το VPN Mikro από το Start Menu ή Desktop shortcut

### Από Source
```bash
# Clone το repository
git clone https://github.com/yourusername/vpnmikro.git
cd vpnmikro

# Εγκατάσταση dependencies
pip install -e .

# Εκκίνηση
python vpnmikro.py
```

## 📖 Γρήγορη Εκκίνηση

### MikroTik Mode
1. Εισάγετε τα στοιχεία του MikroTik router (Host, Port, Username, Password)
2. Κάντε κλικ στο **Test Connection** για επαλήθευση
3. Επιλέξτε το WireGuard interface
4. Εισάγετε το VPN endpoint (public IP:port)
5. Δημιουργήστε τη πρώτη σας συσκευή

### Client-Only Mode
1. Παραλείψτε το MikroTik setup
2. Χρησιμοποιήστε το **Add** για να δημιουργήσετε manual VPN profile
3. Εισάγετε τα στοιχεία του server που σας δόθηκαν

## 🛠️ Build από Source

### Prerequisites
- Python 3.11+
- Nuitka: `pip install nuitka`
- NSIS (προαιρετικό, για installer)
- Visual Studio Build Tools

### Build Commands
```bash
# Build everything (onedir + installer)
python build.py

# Build μόνο standalone folder
python build.py onedir

# Build μόνο NSIS installer
python build.py nsis
```

### Output
- `dist/VPNMikro/` - Portable standalone folder
- `dist/VPNMikro-Setup-x.x.x.exe` - NSIS installer

## 📁 Δομή Project

```
vpnmikro/
├── vpnmikro/
│   ├── core/           # Core functionality
│   │   ├── device_manager.py
│   │   ├── ip_allocator.py
│   │   ├── profiles.py
│   │   ├── qr_generator.py
│   │   ├── secure_store.py
│   │   ├── updater.py
│   │   ├── wg_config.py
│   │   └── wg_controller_win.py
│   ├── mikrotik/       # MikroTik integration
│   │   ├── ros_client.py
│   │   └── wg_manager.py
│   └── ui/             # PyQt6 UI components
│       ├── dashboard.py
│       ├── main_window.py
│       ├── wizard.py
│       └── ...
├── assets/             # Icons και theme
├── logo/               # Application logos
├── wintun/             # WireGuard binaries
├── Docs/               # Documentation
├── build.py            # Build script
└── vpnmikro.py         # Entry point
```

## 📚 Documentation

| Document | Περιγραφή |
|----------|-----------|
| [Quick Start](Docs/QUICK_START.md) | Γρήγορη εκκίνηση |
| [User Guide](Docs/USER_GUIDE.md) | Πλήρης οδηγός χρήσης |
| [MikroTik Setup](Docs/MIKROTIK_SETUP.md) | Ρύθμιση MikroTik router |
| [Build Guide](Docs/BUILD.md) | Οδηγίες build |
| [Update Server](Docs/UPDATE_SERVER.md) | Ρύθμιση update server |
| [Troubleshooting](Docs/TROUBLESHOOTING.md) | Επίλυση προβλημάτων |
| [Changelog](Docs/CHANGELOG.md) | Ιστορικό αλλαγών |

## 🔧 Dependencies

```
PyQt6>=6.5.0
PyNaCl>=1.5.0
cryptography>=41.0.0
qrcode[pil]>=7.4.0
```

## 📝 License

Proprietary - Δείτε [Terms of Service](licenses/TERMS_OF_SERVICE.txt)

## 👤 Author

**Dionisis Prokos**

---

<p align="center">
  Made with ❤️ for the MikroTik community
</p>

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


