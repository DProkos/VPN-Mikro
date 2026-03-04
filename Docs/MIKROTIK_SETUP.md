# MikroTik Setup Guide

## Prerequisites

Before using VPN Mikro with MikroTik, ensure:

1. **RouterOS Version**: 7.x or later (WireGuard support)
2. **API-SSL Enabled**: Port 8729 accessible
3. **WireGuard Interface**: Already configured on the router
4. **User Permissions**: API access and WireGuard management rights

## MikroTik Router Configuration

### 1. Enable API-SSL Service

```routeros
/ip service
set api-ssl disabled=no port=8729
```

### 2. Create WireGuard Interface

```routeros
/interface wireguard
add listen-port=51820 name=wg0
```

### 3. Get Server Public Key

```routeros
/interface wireguard print
```

Note the `public-key` value - you'll need this in VPN Mikro.

### 4. Configure IP Address

```routeros
/ip address
add address=10.66.0.1/24 interface=wg0
```

### 5. Configure Firewall (Optional but Recommended)

```routeros
/ip firewall filter
add chain=input dst-port=51820 protocol=udp action=accept comment="WireGuard"
add chain=input dst-port=8729 protocol=tcp action=accept comment="API-SSL"
```

### 6. Configure NAT (For Internet Access)

```routeros
/ip firewall nat
add chain=srcnat out-interface=ether1 action=masquerade
```

## VPN Mikro Configuration

### 1. Enable MikroTik Management

1. Check **Enable MikroTik Management**
2. The MikroTik panel will appear

### 2. Connect to Router

1. Select your MikroTik from the dropdown (or add new)
2. Enter connection details:
   - **Host**: Router IP (e.g., `192.168.88.1`)
   - **Port**: `8729` (API-SSL)
   - **Username**: Admin username
   - **Password**: Admin password
3. Click **Test** to verify connection
4. Click **Connect** to establish connection

### 3. Configure VPN Server

1. Select WireGuard interface from dropdown
2. Enter **Endpoint**: Your public IP and WireGuard port (e.g., `vpn.example.com:51820`)
3. The server public key is auto-filled from the router

### 4. Create Devices

1. Click **Add**
2. Enter device name
3. The app automatically:
   - Generates WireGuard keypair
   - Allocates IP from pool (default: 10.66.0.0/24)
   - Creates peer on MikroTik
   - Generates config file

## IP Pool Configuration

Default pool: `10.66.0.0/24`

- `.0` (network) and `.1` (gateway) are excluded
- Available IPs: `.2` to `.254`
- Maximum 253 devices per pool

To change the pool:
1. Go to Settings → Advanced
2. Modify **IP Pool** field
3. Save changes

## Troubleshooting MikroTik Connection

### Connection Refused
- Verify API-SSL is enabled on port 8729
- Check firewall rules allow port 8729
- Verify router IP is correct

### Authentication Failed
- Verify username and password
- Check user has API access rights
- Ensure user has WireGuard management permissions

### TLS Certificate Error
- MikroTik uses self-signed certificates by default
- Keep **Verify TLS** unchecked for self-signed certs
- Or import a trusted certificate on the router

### WireGuard Interface Not Found
- Verify WireGuard interface exists on router
- Check RouterOS version is 7.x or later
- Ensure interface is not disabled

## Security Recommendations

1. **Use Strong Passwords**: Use complex passwords for MikroTik API access
2. **Limit API Access**: Restrict API access to specific IP addresses
3. **Use VPN for API**: Access API through VPN when possible
4. **Regular Updates**: Keep RouterOS updated
5. **Firewall Rules**: Only allow necessary ports
