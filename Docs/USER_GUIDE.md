# User Guide

## Dashboard Overview

The main dashboard consists of:

### Top Bar
- **Logo**: VPN Mikro logo (clickable area)
- **VPN Client Selector**: Dropdown to select which VPN to connect
- **Status Pill**: Shows connection status (Connected/Disconnected)
- **Traffic Stats**: Shows download (↓) and upload (↑) bytes
- **Connect/Disconnect**: Main connection buttons
- **Settings**: Access application settings

### Left Panel
- **MikroTik Management**: Enable/disable MikroTik router integration
  - When enabled, shows router selector and connection buttons
  - Devices from selected MikroTik profile are highlighted in purple
- **Quick Actions**: New, Edit, Delete profile buttons

### Right Panel (Devices)
- **Devices Table**: Shows all VPN devices with:
  - Name
  - IP Address
  - Status (Active/Disconnected)
  - Enabled (Yes/No)
  - Last Handshake
  - Created Date
- **Action Buttons**: Add, Import, Settings, Export, QR, Copy Key, Delete
- **Click to Select**: Clicking a device row updates the combo box selection

## Settings Persistence

VPN Mikro remembers your settings between sessions:
- MikroTik Management enabled/disabled
- Selected MikroTik router
- Selected VPN client
- Window size and position

Settings are automatically saved when you close the application.

## Managing VPN Clients

### Viewing All Clients
- Select **"All VPN Clients"** from the dropdown
- The devices table shows all devices from all profiles

### Selecting a Specific Client
- Choose a specific VPN client from the dropdown
- The device will be highlighted in the table
- Click **Connect** to establish the VPN connection
- Clicking a row in the table also updates the combo box

### Connection Locking
- While connected, the VPN client selector is locked
- You must disconnect before switching to another VPN

## Creating Devices

### With MikroTik Management

1. Enable **MikroTik Management** checkbox
2. Select your MikroTik router from the dropdown
3. Click **Connect** to connect to the router
4. Existing peers are automatically synced from MikroTik
5. Click **Add** to create a new device
6. Enter device name
7. Device is automatically created with:
   - Generated keypair
   - Allocated IP from pool
   - Peer created on MikroTik

### Automatic Peer Sync

When you connect to MikroTik:
- All existing WireGuard peers are discovered
- New peers are added to your local profile
- Existing peers are kept in sync

### Manual VPN Profile (Without MikroTik)

1. Disable **MikroTik Management** (or leave unchecked)
2. Click **Add**
3. Follow the wizard:

#### Step 1: Profile Name
- Enter a descriptive name for your VPN

#### Step 2: Server Details
- **Server Endpoint**: `hostname:port` (e.g., `vpn.example.com:51820`)
- **Server Public Key**: The WireGuard public key of the server

#### Step 3: Client Details
- **Client IP**: Your assigned IP address (e.g., `10.0.0.5`)
- **DNS Servers**: Optional DNS servers (e.g., `1.1.1.1, 8.8.8.8`)

#### Step 4: Routing
- **Full Tunnel**: Route all traffic through VPN (`0.0.0.0/0`)
- **Split Tunnel**: Only route specific subnets

#### Step 5: Summary
- Review your settings
- Click **Create Profile**
- **Copy the Public Key** displayed and send to your VPN administrator

## Importing Configurations

### Import WireGuard Config File

1. Click **Import**
2. Select a `.conf` file
3. The device will be added to your profile

## Exporting Configurations

### Export Config File

1. Select a device in the table
2. Click **Export**
3. Choose save location
4. The `.conf` file is saved

### Generate QR Code

1. Select a device in the table
2. Click **QR**
3. Scan the QR code with WireGuard mobile app

### Copy Public Key

1. Select a device in the table
2. Click **Copy Key**
3. The device's public key is copied to clipboard

## Deleting Devices

### MikroTik-Managed Devices
- Requires MikroTik connection
- Removes peer from router and local config

### Manual/Imported Devices
- Deletes locally without MikroTik connection
- Only removes local config file

## System Tray

### Tray Icon
- Shows VPN Mikro logo in system tray
- Tooltip shows connection status

### Tray Menu (Right-click)
- **Show**: Open main window
- **Connect**: Connect to selected VPN
- **Disconnect**: Disconnect from VPN
- **Exit**: Close application completely

### Minimize to Tray
- Closing the window minimizes to tray (not exit)
- VPN remains active in background
- Double-click tray icon to restore window
- Use **Exit** from tray menu to fully close

## Settings

Access settings via the gear icon in the top bar:

### Application Settings

The main settings dialog has three tabs:

#### General Tab
- **Start with Windows**: Launch VPN Mikro automatically on Windows startup
- **Start minimized**: Start in system tray instead of showing window
- **Auto-check for updates**: Check for new versions on startup

#### Paths Tab
Shows the locations where VPN Mikro stores data:
- **Profiles**: VPN profile configurations
- **Configs**: WireGuard configuration files
- **Logs**: Application log files
- **Temp**: Temporary files

Each path has an "Open" button to open the folder in Explorer.

#### About Tab
- Version information
- Author credits
- Copyright notice

### MikroTik Profile Settings

Click the settings button next to the MikroTik Connect button to edit:
- MikroTik connection details (host, port)
- Credentials (username, password)
- VPN server settings
- IP Pool configuration

## Auto-Update

VPN Mikro can automatically check for updates:

1. On startup (if enabled in settings)
2. Manually via Settings → About → Check for Updates

When an update is available:
- A notification appears
- Click to download the new version
- The installer will be downloaded to your Downloads folder

## MikroTik Connection Monitor

When connected to MikroTik, VPN Mikro monitors the connection:
- Checks every 30 seconds if connection is alive
- If connection is lost:
  - Shows "Connection Lost" status in red
  - Displays a tray notification
  - Automatically updates UI to disconnected state
- Click "Connect" to reconnect
