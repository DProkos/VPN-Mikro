"""Logging with sensitive data redaction."""

import logging
import os
import re
from pathlib import Path
from typing import Optional


class RedactedFormatter(logging.Formatter):
    """Formatter that redacts sensitive information from log messages."""

    REDACT_PATTERNS = [
        # Password patterns (various formats)
        (re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), r'password=***REDACTED***'),
        (re.compile(r'pwd["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), r'pwd=***REDACTED***'),
        
        # WireGuard PrivateKey in config format
        (re.compile(r'PrivateKey\s*=\s*(\S+)', re.IGNORECASE), r'PrivateKey = ***REDACTED***'),
        
        # Base64 encoded keys (44 chars with = padding, typical for WG keys)
        (re.compile(r'\b([A-Za-z0-9+/]{43}=)\b'), r'***KEY_REDACTED***'),
        
        # Base64 encoded keys (43 chars without padding)
        (re.compile(r'\b([A-Za-z0-9+/]{42,44})\b(?=[\s,}\]"\']|$)'), r'***KEY_REDACTED***'),
        
        # API credentials in URL format
        (re.compile(r'://([^:]+):([^@]+)@'), r'://***:***@'),
    ]

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with sensitive data redacted."""
        message = super().format(record)
        return self._redact(message)

    def _redact(self, message: str) -> str:
        """Apply all redaction patterns to the message."""
        result = message
        for pattern, replacement in self.REDACT_PATTERNS:
            result = pattern.sub(replacement, result)
        return result


class RedactedLogger:
    """Logger that automatically redacts sensitive information.
    
    Logs are written to %ProgramData%\\VPNMikro\\logs\\ on Windows.
    """

    LOG_DIR_NAME = "VPNMikro"
    LOG_FILE_NAME = "vpnmikro.log"
    DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, name: str = "vpnmikro", level: int = logging.INFO):
        """Initialize the redacted logger.
        
        Args:
            name: Logger name
            level: Logging level (default INFO)
        """
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._log_dir: Optional[Path] = None
        self._setup_handlers()

    def _get_log_directory(self) -> Path:
        """Get the log directory path.
        
        Returns %ProgramData%\\VPNMikro\\logs\\ on Windows,
        falls back to ~/.vpnmikro/logs/ on other platforms.
        """
        if self._log_dir is not None:
            return self._log_dir

        program_data = os.environ.get("ProgramData")
        if program_data:
            base_dir = Path(program_data) / self.LOG_DIR_NAME / "logs"
        else:
            # Fallback for non-Windows or missing ProgramData
            base_dir = Path.home() / ".vpnmikro" / "logs"

        self._log_dir = base_dir
        return base_dir

    def _setup_handlers(self) -> None:
        """Set up file and console handlers with redaction."""
        # Avoid duplicate handlers
        if self._logger.handlers:
            return

        formatter = RedactedFormatter(
            fmt=self.DEFAULT_FORMAT,
            datefmt=self.DEFAULT_DATE_FORMAT
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

        # File handler (create directory if needed)
        try:
            log_dir = self._get_log_directory()
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / self.LOG_FILE_NAME

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            # Log to console only if file logging fails
            self._logger.warning(f"Could not set up file logging: {e}")

    def debug(self, message: str, *args, **kwargs) -> None:
        """Log a debug message."""
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        """Log an info message."""
        self._logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """Log a warning message."""
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """Log an error message."""
        self._logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        """Log a critical message."""
        self._logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        """Log an exception with traceback."""
        self._logger.exception(message, *args, **kwargs)

    def set_level(self, level: int) -> None:
        """Set the logging level."""
        self._logger.setLevel(level)

    @property
    def log_file_path(self) -> Optional[Path]:
        """Get the path to the log file, if file logging is enabled."""
        log_dir = self._get_log_directory()
        log_file = log_dir / self.LOG_FILE_NAME
        if log_file.exists():
            return log_file
        return None


# Module-level logger instance
_default_logger: Optional[RedactedLogger] = None


def get_logger(name: str = "vpnmikro") -> RedactedLogger:
    """Get or create a RedactedLogger instance.
    
    Args:
        name: Logger name
        
    Returns:
        RedactedLogger instance
    """
    global _default_logger
    if _default_logger is None or name != "vpnmikro":
        _default_logger = RedactedLogger(name)
    return _default_logger
