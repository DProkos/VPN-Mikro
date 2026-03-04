"""MikroTik RouterOS API-SSL client implementation.

This module provides a client for communicating with MikroTik routers
via the API-SSL protocol (default port 8729).
"""

import hashlib
import socket
import ssl
import time
from typing import Any, Dict, List, Optional

from vpnmikro.core.logger import get_logger

logger = get_logger(__name__)


class ROSClientError(Exception):
    """Base exception for ROS client errors."""
    pass


class ROSConnectionError(ROSClientError):
    """Connection-related errors."""
    pass


class ROSAuthenticationError(ROSClientError):
    """Authentication-related errors."""
    pass


class ROSCommandError(ROSClientError):
    """Command execution errors."""
    pass


class ROSClient:
    """MikroTik RouterOS API-SSL client.
    
    Implements the MikroTik API protocol over SSL for secure communication.
    Supports connection retry logic and TLS verification toggle.
    Also supports plain API (non-SSL) on port 8728.
    
    Attributes:
        host: MikroTik router hostname or IP address.
        port: API-SSL port (default 8729) or API port (8728).
        verify_tls: Whether to verify TLS certificates (default False for self-signed).
        use_ssl: Whether to use SSL (True for 8729, False for 8728).
    """
    
    DEFAULT_PORT = 8729
    DEFAULT_TIMEOUT = 10.0
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    
    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        verify_tls: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
        use_ssl: bool = None
    ):
        """Initialize the ROS client.
        
        Args:
            host: MikroTik router hostname or IP address.
            port: API-SSL port (default 8729) or API port (8728).
            verify_tls: Whether to verify TLS certificates.
            timeout: Socket timeout in seconds.
            use_ssl: Whether to use SSL. Auto-detected from port if None.
        """
        self.host = host
        self.port = port
        self.verify_tls = verify_tls
        self.timeout = timeout
        # Auto-detect SSL based on port if not specified
        self.use_ssl = use_ssl if use_ssl is not None else (port == 8729)
        self._socket = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected and self._socket is not None
    
    def connect(self) -> None:
        """Establish connection to the MikroTik router.
        
        Uses SSL for port 8729, plain socket for port 8728.
        Implements retry logic for transient failures.
        
        Raises:
            ROSConnectionError: If connection fails after all retries.
        """
        last_error: Optional[Exception] = None
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            raw_socket = None
            try:
                proto = "SSL" if self.use_ssl else "plain"
                logger.info(f"Connecting to {self.host}:{self.port} ({proto}, attempt {attempt}/{self.MAX_RETRIES})")
                
                # Create raw socket
                raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_socket.settimeout(self.timeout)
                
                if self.use_ssl:
                    # Create SSL context with relaxed settings for MikroTik compatibility
                    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                    context.minimum_version = ssl.TLSVersion.TLSv1
                    context.set_ciphers('DEFAULT:@SECLEVEL=1')
                    
                    if not self.verify_tls:
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                    
                    # Wrap socket with SSL and connect
                    self._socket = context.wrap_socket(raw_socket, server_hostname=self.host)
                    self._socket.connect((self.host, self.port))
                else:
                    # Plain socket (no SSL) - connect first, then assign
                    raw_socket.connect((self.host, self.port))
                    self._socket = raw_socket
                    raw_socket = None  # Don't close in finally, it's now self._socket
                
                self._connected = True
                logger.info(f"Connected to {self.host}:{self.port}")
                return
                
            except socket.timeout as e:
                last_error = e
                logger.warning(f"Connection timeout (attempt {attempt}): {e}")
            except socket.error as e:
                last_error = e
                logger.warning(f"Socket error (attempt {attempt}): {e}")
            except ssl.SSLError as e:
                last_error = e
                logger.warning(f"SSL error (attempt {attempt}): {e}")
            except Exception as e:
                last_error = e
                logger.warning(f"Unexpected error (attempt {attempt}): {e}")
            finally:
                # Clean up socket on failure
                if raw_socket is not None:
                    try:
                        raw_socket.close()
                    except:
                        pass
                if self._socket is not None and not self._connected:
                    try:
                        self._socket.close()
                    except:
                        pass
                    self._socket = None
            
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY * attempt)
        
        raise ROSConnectionError(
            f"Cannot connect to MikroTik at {self.host}:{self.port} after {self.MAX_RETRIES} attempts: {last_error}"
        )
    
    def disconnect(self) -> None:
        """Close the connection to the MikroTik router."""
        if self._socket:
            try:
                self._socket.close()
            except Exception as e:
                logger.warning(f"Error closing socket: {e}")
            finally:
                self._socket = None
                self._connected = False
                logger.info(f"Disconnected from {self.host}:{self.port}")

    def login(self, username: str, password: str) -> bool:
        """Authenticate with the MikroTik router.
        
        Uses the modern login method (RouterOS 6.43+).
        
        Args:
            username: MikroTik username.
            password: MikroTik password.
            
        Returns:
            True if authentication succeeded.
            
        Raises:
            ROSConnectionError: If not connected.
            ROSAuthenticationError: If authentication fails.
        """
        if not self.is_connected:
            raise ROSConnectionError("Not connected to router")
        
        logger.info(f"Authenticating as user: {username}")
        
        try:
            # Modern login (RouterOS 6.43+)
            response = self.execute("/login", {"name": username, "password": password})
            
            # Check for successful login
            if response and len(response) > 0:
                # Login successful if we get a response without error
                logger.info("Authentication successful")
                return True
            
            logger.info("Authentication successful")
            return True
            
        except ROSCommandError as e:
            error_msg = str(e)
            if "cannot log in" in error_msg.lower() or "invalid" in error_msg.lower():
                raise ROSAuthenticationError("Invalid username or password")
            raise ROSAuthenticationError(f"Authentication failed: {error_msg}")
    
    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute an API command on the MikroTik router.
        
        Args:
            command: API command path (e.g., "/interface/wireguard/print").
            params: Optional command parameters.
            
        Returns:
            List of response dictionaries.
            
        Raises:
            ROSConnectionError: If not connected.
            ROSCommandError: If command execution fails.
        """
        if not self.is_connected:
            raise ROSConnectionError("Not connected to router")
        
        logger.debug(f"Executing command: {command}")
        
        try:
            # Send command
            self._send_word(command)
            
            # Send parameters
            if params:
                for key, value in params.items():
                    if value is not None:
                        param_str = f"={key}={value}"
                        self._send_word(param_str)
            
            # Send empty word to end command
            self._send_word("")
            
            # Read response
            return self._read_response()
            
        except (socket.error, ssl.SSLError) as e:
            self._connected = False
            raise ROSConnectionError(f"Communication error: {e}")

    def _send_word(self, word: str) -> None:
        """Send a word using the MikroTik API protocol.
        
        Words are length-prefixed using a variable-length encoding.
        
        Args:
            word: The word to send.
        """
        if self._socket is None:
            raise ROSConnectionError("Socket not initialized")
        
        encoded = word.encode("utf-8")
        length = len(encoded)
        
        # Encode length using MikroTik's variable-length encoding
        if length < 0x80:
            self._socket.send(bytes([length]))
        elif length < 0x4000:
            length |= 0x8000
            self._socket.send(bytes([(length >> 8) & 0xFF, length & 0xFF]))
        elif length < 0x200000:
            length |= 0xC00000
            self._socket.send(bytes([
                (length >> 16) & 0xFF,
                (length >> 8) & 0xFF,
                length & 0xFF
            ]))
        elif length < 0x10000000:
            length |= 0xE0000000
            self._socket.send(bytes([
                (length >> 24) & 0xFF,
                (length >> 16) & 0xFF,
                (length >> 8) & 0xFF,
                length & 0xFF
            ]))
        else:
            self._socket.send(bytes([0xF0]))
            self._socket.send(bytes([
                (length >> 24) & 0xFF,
                (length >> 16) & 0xFF,
                (length >> 8) & 0xFF,
                length & 0xFF
            ]))
        
        if encoded:
            self._socket.send(encoded)
    
    def _read_word(self) -> str:
        """Read a word using the MikroTik API protocol.
        
        Returns:
            The decoded word string.
        """
        if self._socket is None:
            raise ROSConnectionError("Socket not initialized")
        
        # Read length byte(s)
        first_byte = self._recv_bytes(1)[0]
        
        if first_byte < 0x80:
            length = first_byte
        elif first_byte < 0xC0:
            second_byte = self._recv_bytes(1)[0]
            length = ((first_byte & 0x3F) << 8) | second_byte
        elif first_byte < 0xE0:
            rest = self._recv_bytes(2)
            length = ((first_byte & 0x1F) << 16) | (rest[0] << 8) | rest[1]
        elif first_byte < 0xF0:
            rest = self._recv_bytes(3)
            length = ((first_byte & 0x0F) << 24) | (rest[0] << 16) | (rest[1] << 8) | rest[2]
        else:
            rest = self._recv_bytes(4)
            length = (rest[0] << 24) | (rest[1] << 16) | (rest[2] << 8) | rest[3]
        
        if length == 0:
            return ""
        
        data = self._recv_bytes(length)
        return data.decode("utf-8")
    
    def _recv_bytes(self, count: int) -> bytes:
        """Receive exact number of bytes from socket.
        
        Args:
            count: Number of bytes to receive.
            
        Returns:
            Received bytes.
        """
        if self._socket is None:
            raise ROSConnectionError("Socket not initialized")
        
        data = b""
        while len(data) < count:
            chunk = self._socket.recv(count - len(data))
            if not chunk:
                raise ROSConnectionError("Connection closed by remote host")
            data += chunk
        return data

    def _read_response(self) -> List[Dict[str, Any]]:
        """Read a complete API response.
        
        Returns:
            List of response dictionaries.
            
        Raises:
            ROSCommandError: If the response indicates an error.
        """
        results: List[Dict[str, Any]] = []
        current: Dict[str, Any] = {}
        
        while True:
            word = self._read_word()
            
            if word == "":
                # Empty word marks end of sentence
                if current:
                    results.append(current)
                    current = {}
                continue
            
            if word == "!done":
                # Command completed successfully
                if current:
                    results.append(current)
                break
            
            if word == "!re":
                # New result entry
                if current:
                    results.append(current)
                current = {}
                continue
            
            if word == "!trap":
                # Error response
                error_data: Dict[str, str] = {}
                while True:
                    error_word = self._read_word()
                    if error_word == "" or error_word == "!done":
                        break
                    if error_word.startswith("="):
                        key, _, value = error_word[1:].partition("=")
                        error_data[key] = value
                
                error_msg = error_data.get("message", "Unknown error")
                raise ROSCommandError(f"MikroTik error: {error_msg}")
            
            if word == "!fatal":
                # Fatal error - connection will be closed
                self._connected = False
                raise ROSCommandError("Fatal error from MikroTik - connection closed")
            
            # Parse attribute
            if word.startswith("="):
                key, _, value = word[1:].partition("=")
                current[key] = value
        
        return results
    
    def __enter__(self) -> "ROSClient":
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()
