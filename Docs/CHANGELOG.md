# Changelog

All notable changes to VPN Mikro are documented in this file.

## [0.0.4] - 2025-12-27

### Added
- **Connection Verification**: VPN connection now verifies traffic before showing "Connected"
  - Waits up to 5 seconds for received bytes
  - Shows "Verifying... (1/5)" progress in status bar
  - Automatically disconnects if no traffic received
  - Clear error message with possible causes
- **Real-Time Traffic Display**: Traffic column shows live download/upload stats
  - Format: `↓X.XMB ↑X.XMB`
  - Updates every 2 seconds
  - Non-blocking background thread

### Changed
- **VPN Operations in Background**: Connect/Disconnect now run in background thread
  - UI remains responsive during operations
  - No more freezing on second connect attempt
  - Status updates shown in real-time

### Fixed
- **UI Freeze on Second Connect**: Fixed critical bug where UI would freeze on second VPN connection
  - Root cause: Blocking `time.sleep()` loop in main thread
  - Solution: Moved all VPN operations to `VPNWorkerThread`
- **UI Freeze on Disconnect**: Disconnect operation also moved to background thread
- **False "Connected" Status**: Previously showed "Connected" even when VPN wasn't working
  - Now verifies actual traffic before confirming connection

### Technical
- Added `VPNWorkerThread` class for non-blocking VPN operations
- Added `TrafficMonitorThread` class for real-time traffic stats
- Added `status_update` signal for progress feedback during connection
- Added `_on_connect_status_update()` for status bar updates
- Added `_format_bytes()` helper for human-readable traffic display
- Removed blocking verification loop from connect flow

---

## [0.0.3] - 2025-12-26

### Added
- **Terms of Service**: Added comprehensive Terms of Service document
  - Clarifies VPN Mikro is a management tool, not a VPN provider
  - Governing law: Greece
  - Accessible from About dialog
- **Real-Time MikroTik Monitor**: Background thread monitors MikroTik connection every 5 seconds
  - Immediate detection of connection loss
  - Automatic UI update when connection drops

### Changed
- **Traffic Stats Optimization**: Moved traffic statistics collection to background thread
  - Uses ThreadPoolExecutor for non-blocking stats updates
  - Eliminates UI freezing during VPN connection
  - Added `_stats_pending` flag to prevent overlapping requests
- **Build Improvements**: Enhanced Nuitka build configuration
  - Added `--lto=yes` for link-time optimization
  - Added `--remove-output` for cleaner builds
  - Fixed NSIS installer path to use compiled files from `dist/`

### Fixed
- **UI Freeze on Connect**: Fixed 1-second UI freeze when connecting to VPN
  - Traffic stats now collected asynchronously
  - Proper callback handling with `future.add_done_callback()`
- **PowerShell Window Popup**: Fixed PowerShell window appearing every second
  - Added `creationflags=subprocess.CREATE_NO_WINDOW` to all subprocess calls
  - Added `-WindowStyle Hidden` to PowerShell commands
- **Wizard Window Icon**: Added window icon to Setup Wizard
- **Wizard Transparent Backgrounds**: Fixed black backgrounds in wizard labels

### Technical
- Added `MikroTikMonitorThread` class for real-time connection monitoring
- Added `_apply_traffic_stats()` method for thread-safe UI updates
- Added `_stats_executor` ThreadPoolExecutor for background stats collection
- Added proper executor cleanup in `_on_tray_exit()`
- Added QWizard styles to `theme.qss` for transparent backgrounds

---

## [0.0.2] - 2025-12-26

### Added
- **Auto-Update System**: Check for updates on startup and from About dialog
  - Downloads new versions automatically
  - Configurable auto-check setting
- **Application Settings Dialog**: New settings dialog with tabs:
  - General: Start with Windows, Start minimized, Auto-check updates
  - Paths: Shows data locations (Profiles, Configs, Logs, Temp)
  - About: Version, author, copyright info
- **MikroTik Connection Monitor**: Automatically detects when MikroTik connection is lost
  - Checks connection every 30 seconds
  - Shows notification when connection drops
  - Updates UI to show disconnected state
- **MikroTik Settings Button**: Quick access to MikroTik profile settings
- **Resizable Table Columns**: Device table columns can be resized and positions are saved

### Changed
- **Settings Button**: Top-right settings now opens App Settings (not MikroTik settings)
- **MikroTik Cleanup**: Synced devices are removed when disabling MikroTik or disconnecting

### Fixed
- **MikroTik Profile Selection**: Fixed using wrong profile for MikroTik connection
- **WGPeer Dataclass Access**: Fixed treating WGPeer objects as dictionaries
- **Transparent Backgrounds**: Fixed black background in MikroTik container
- **Tray Icon TypeError**: Fixed error when clicking tray icon

### Technical
- Added `vpnmikro/core/updater.py` for update checking
- Added `vpnmikro/ui/app_settings_dialog.py` for app settings
- Added `_check_mikrotik_connection()` for connection monitoring
- Added `_cleanup_mikrotik_connection()` for proper cleanup
- Build script now supports NSIS installer creation

## [0.0.1] - 2025-12-25

### Added
- **Application Logo**: Custom logo displayed in window title bar, system tray, and all dialogs
- **Settings Persistence**: Application remembers your settings between sessions:
  - MikroTik Management enabled/disabled state
  - Selected MikroTik profile
  - Selected VPN client
  - Window size and position
- **MikroTik Sync**: When connecting to MikroTik, peers are automatically synced to the profile
- **Device Selection Sync**: Clicking a device in the table updates the combo box selection
- **Profile Highlighting**: When MikroTik Management is enabled, devices from the selected profile are highlighted with purple background
- **Build Script**: Python build script (`build.py`) for creating:
  - Nuitka standalone build (onedir)
  - NSIS installer with proper icons and shortcuts
  - Administrator manifest for automatic elevation

### Changed
- **Logo in Top Bar**: Replaced "VPN Mikro" text with logo image
- **Transparent Labels**: All labels now have transparent background for cleaner look
- **Tray Icon**: System tray now uses the application logo instead of generic shield icon
- **Single Instance**: "Already running" dialog now shows application icon

### Fixed
- **Checkbox Background**: Fixed black background on checkboxes inside cards
- **Lock File Cleanup**: Improved single-instance detection and lock file handling

### Technical
- Added `get_window_icon()` helper function in `assets.py`
- Added QSettings for persistent storage
- Added `_sync_peers_from_mikrotik()` for automatic peer discovery
- Added `_highlight_profile_devices()` for visual profile indication
- Added `_on_device_row_clicked()` for table-to-combo synchronization

---

## [0.0.1] - 2025-12-25

### Initial Release
- MikroTik router integration via API
- WireGuard tunnel management
- Profile and device management
- QR code generation for mobile
- Import/Export configurations
- System tray support
- Dark theme UI
- Custom application logo
- Settings persistence between sessions
- Automatic peer sync from MikroTik
- Device selection sync with table
- Profile highlighting for MikroTik devices
- Build script for Nuitka and NSIS
