# Quick Start Guide

## First Launch

When you first launch VPN Mikro, you'll see the setup wizard. You can choose between two modes:

### Option 1: MikroTik Mode (Recommended for MikroTik users)

1. Enter your MikroTik router details:
   - **Host**: IP address or domain (e.g., `192.168.88.1`)
   - **Port**: API-SSL port (default: `8729`)
   - **Username**: MikroTik admin username
   - **Password**: MikroTik admin password

2. Click **Test Connection** to verify

3. Select your WireGuard interface from the dropdown

4. Enter the VPN endpoint (public IP:port of your router)

5. Create your first device

### Option 2: Client-Only Mode

If you don't have a MikroTik router or want to connect to an existing WireGuard server:

1. Skip the MikroTik setup
2. Use the **Add** button to create a manual VPN profile
3. Enter the server details provided by your VPN administrator

## Creating Your First Profile

### With MikroTik Management

1. Enable **MikroTik Management** checkbox
2. Select your MikroTik router from the dropdown
3. Click **Connect** to connect to the router
4. Click **Add** to create a new device
5. Enter a device name
6. The app will automatically:
   - Generate WireGuard keys
   - Allocate an IP address
   - Create the peer on MikroTik
   - Generate the config file

### Without MikroTik (Manual Profile)

1. Keep **MikroTik Management** unchecked
2. Click **Add** to open the Manual VPN Wizard
3. Follow the wizard steps:
   - **Profile Name**: Give your VPN a name
   - **Server Details**: Enter endpoint and server public key
   - **Client Details**: Enter your assigned IP and DNS
   - **Routing**: Choose full tunnel or split tunnel
4. Click **Create Profile**
5. Copy the displayed **Public Key** and send it to your VPN administrator

## Connecting to VPN

1. Select your VPN client from the dropdown in the top bar
2. Click **Connect**
3. If prompted, approve the Administrator request (required for first-time tunnel installation)
4. The status pill will show "Connected" and traffic stats will appear

## Disconnecting

1. Click **Disconnect** in the top bar
2. The VPN tunnel will be stopped

## Tips

- The app minimizes to system tray when closed while connected
- Double-click the tray icon to restore the window
- Right-click the tray icon for quick connect/disconnect options
