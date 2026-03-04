# Troubleshooting Guide

## Common Issues

### Application Won't Start

#### "Application is already running"
- VPN Mikro only allows one instance
- Check system tray for existing instance
- If no instance visible, delete lock file: `%TEMP%\vpnmikro.lock`

#### Missing DLL Errors
- Ensure all files from the ZIP are extracted
- Don't move individual files out of the folder
- Re-extract the ZIP if files are missing

### Connection Issues

#### "Cannot connect to MikroTik"
1. Verify router IP address is correct
2. Check port 8728 (plain API) or 8729 (API-SSL) is open on router
3. Ensure API service is enabled on router
4. Test with: `telnet <router-ip> 8728`

#### "Invalid username or password"
1. Verify credentials are correct
2. Check user has API access rights
3. Ensure no typos in username/password




4. Try logging into router WebFig to verify credentials

#### "Credentials Required" when deleting device
- This happens for MikroTik-managed devices
- Connect to MikroTik first, then delete
- For manual/imported devices, no credentials needed

### VPN Connection Issues

#### "Connection Failed - No data received"
- **New in v0.0.4**: VPN now verifies traffic before confirming connection
- This error means the tunnel started but no data was received
- Possible causes:
  1. VPN server is not reachable
  2. Firewall blocking traffic
  3. Invalid configuration (wrong endpoint, keys)
  4. Server-side issue (peer not configured)
  5. Network routing problem

#### "Failed to connect: Permission denied"
- VPN tunnel installation requires Administrator rights
- Click "Yes" when prompted for elevation
- If no prompt appears, run app as Administrator

#### "Tunnel service failed to start"
1. Check Windows Services for `WireGuardTunnel$vpnmikro-*`
2. Ensure no conflicting WireGuard tunnels
3. Restart the application
4. Try disconnecting and reconnecting

#### Connected but no internet
1. Check DNS settings in profile
2. Verify server-side routing is configured
3. Check firewall rules on server
4. Try split tunnel mode instead of full tunnel

#### Handshake not completing
1. Verify server endpoint is correct
2. Check server public key matches
3. Ensure your public key is added to server
4. Check firewall allows UDP on WireGuard port

### UI Issues (Fixed in v0.0.4)

#### UI freezing on connect/disconnect
- **Fixed in v0.0.4**: All VPN operations now run in background thread
- If still occurring, update to latest version

#### UI freezing on second connect
- **Fixed in v0.0.4**: Removed blocking verification loop
- Connect/disconnect now fully non-blocking

### UI Issues (Fixed in v0.0.3)

#### PowerShell window appearing every second
- **Fixed in v0.0.3**: Added `CREATE_NO_WINDOW` flag to all subprocess calls
- If still occurring, update to latest version

#### UI freezing when connecting
- **Fixed in v0.0.3**: Traffic stats now collected in background thread
- If still occurring, update to latest version

#### Black backgrounds in wizard/dialogs
- **Fixed in v0.0.3**: Added transparent background styles
- If still occurring, update to latest version

### Traffic Statistics

#### Stats show ↓0B ↑0B
- **New in v0.0.4**: Traffic now displays in real-time
- If showing 0B after connection:
  1. Connection verification should have caught this
  2. Generate some traffic (browse a website)
  3. Check if VPN is actually working
  4. May indicate connection problem

#### Traffic not updating
- Stats update every 2 seconds in background
- Check if tunnel adapter exists in Windows
- PowerShell command used: `Get-NetAdapterStatistics`

### Device Management Issues

#### "Please select a specific VPN client"
- You have "All VPN Clients" selected
- Select a specific device from the dropdown
- Then click Connect

#### Device not appearing in list
1. Refresh the profile list
2. Check if device was created successfully
3. Look for error messages during creation
4. Verify profile file exists in `%ProgramData%\VPNMikro\data\`

#### Cannot delete device
- For MikroTik devices: Connect to router first
- For manual devices: Should delete without connection
- Check for error messages

### QR Code Issues

#### QR code not scanning
1. Ensure good lighting
2. Hold phone steady
3. Try zooming in on QR code
4. Export config file instead and transfer manually

### Profile Issues

#### Profile not saving
1. Check write permissions to `%ProgramData%\VPNMikro\`
2. Run as Administrator if needed
3. Check disk space

#### Credentials not remembered
1. Ensure "Remember credentials" is checked
2. Windows DPAPI requires user login
3. Credentials are user-specific

## Log Files

Logs are stored in: `%ProgramData%\VPNMikro\logs\`

### Enable Debug Logging
Currently, logging level is set in code. Check logs for detailed error messages.

### Log File Location
```
C:\ProgramData\VPNMikro\logs\vpnmikro.log
```

## Data Locations

| Data | Location |
|------|----------|
| Profiles | `%ProgramData%\VPNMikro\data\profiles.json` |
| Configs | `%ProgramData%\VPNMikro\configs\` |
| Logs | `%ProgramData%\VPNMikro\logs\` |
| Lock File | `%TEMP%\vpnmikro.lock` |
| Settings | Windows Registry: `HKCU\Software\VPNMikro` |

## Reset Application

To completely reset VPN Mikro:

1. Close the application
2. Delete folder: `C:\ProgramData\VPNMikro\`
3. Delete lock file: `%TEMP%\vpnmikro.lock`
4. Clear registry: `HKCU\Software\VPNMikro`
5. Restart application

**Warning**: This deletes all profiles and configurations!

## Getting Help

If issues persist:

1. Check log files for error details
2. Note the exact error message
3. Document steps to reproduce
4. Include system information (Windows version, etc.)
