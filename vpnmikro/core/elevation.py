"""Windows elevation utilities for UAC handling.

This module provides utilities for detecting admin privileges and
relaunching the application with elevated permissions via UAC.
"""

import ctypes
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

from vpnmikro.core.logger import get_logger

logger = get_logger(__name__)

SW_HIDE = 0
SW_SHOW = 5

# Job directory for IPC between normal and elevated processes
JOBS_DIR = Path("C:/ProgramData/VPNMikro/data/jobs")


def is_admin() -> bool:
    """Check if the current process has administrator privileges.
    
    Returns:
        True if running as admin, False otherwise.
    """
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_elevated(args: list[str], show_window: bool = False) -> None:
    """Relaunch current executable with UAC prompt.
    
    Args:
        args: List of command-line arguments to pass to elevated process.
        show_window: Whether to show the elevated process window.
        
    Raises:
        RuntimeError: If ShellExecuteW fails.
        PermissionError: If user cancelled UAC prompt.
    """
    params = " ".join([_quote(a) for a in args])
    sw_flag = SW_SHOW if show_window else SW_HIDE
    
    logger.info(f"Requesting elevation with args: {params[:100]}...")
    
    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, sw_flag
    )
    
    # ShellExecuteW returns > 32 on success
    if rc <= 32:
        if rc == 5:  # ERROR_ACCESS_DENIED - user cancelled UAC
            raise PermissionError("Administrator approval was cancelled.")
        raise RuntimeError(f"Failed to request elevation (error code: {rc})")
    
    logger.info("Elevated process launched successfully")


def _quote(s: str) -> str:
    """Quote a string for command line if needed."""
    if any(c in s for c in [' ', '\t', '"']):
        return '"' + s.replace('"', '\\"') + '"'
    return s


class ElevatedJob:
    """Manages an elevated job request/response via file-based IPC.
    
    The normal (non-admin) process creates a job request file,
    launches an elevated helper, and waits for the result file.
    """
    
    def __init__(self, action: str, **params):
        """Create a new elevated job.
        
        Args:
            action: The action to perform (e.g., "install_tunnel").
            **params: Action-specific parameters.
        """
        self.job_id = str(uuid.uuid4())
        self.action = action
        self.params = params
        self._ensure_jobs_dir()
    
    def _ensure_jobs_dir(self):
        """Ensure the jobs directory exists."""
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
    
    @property
    def request_path(self) -> Path:
        """Path to the job request file."""
        return JOBS_DIR / f"job_request_{self.job_id}.json"
    
    @property
    def result_path(self) -> Path:
        """Path to the job result file."""
        return JOBS_DIR / f"job_result_{self.job_id}.json"
    
    def write_request(self) -> None:
        """Write the job request file."""
        request = {
            "job_id": self.job_id,
            "action": self.action,
            "params": self.params
        }
        self.request_path.write_text(
            json.dumps(request, ensure_ascii=False),
            encoding="utf-8"
        )
        logger.debug(f"Wrote job request: {self.request_path}")
    
    def execute_elevated(self, timeout: float = 30.0) -> dict:
        """Execute the job in an elevated process and wait for result.
        
        Args:
            timeout: Maximum time to wait for result in seconds.
            
        Returns:
            Result dictionary with keys: ok, stdout, stderr, code
            
        Raises:
            RuntimeError: If elevation fails or times out.
            PermissionError: If user cancelled UAC.
        """
        # Write request file
        self.write_request()
        
        # Build elevated process arguments
        args = [
            "-m", "vpnmikro.elevated_main",
            "--job-id", self.job_id,
            "--data-dir", str(JOBS_DIR.parent)
        ]
        
        # Launch elevated process
        relaunch_elevated(args)
        
        # Wait for result
        result = self._wait_for_result(timeout)
        
        # Cleanup
        self._cleanup()
        
        return result
    
    def _wait_for_result(self, timeout: float) -> dict:
        """Poll for the result file.
        
        Args:
            timeout: Maximum time to wait in seconds.
            
        Returns:
            Result dictionary.
            
        Raises:
            RuntimeError: If timeout exceeded.
        """
        poll_interval = 0.2
        elapsed = 0.0
        
        while elapsed < timeout:
            if self.result_path.exists():
                try:
                    result = json.loads(self.result_path.read_text(encoding="utf-8"))
                    logger.debug(f"Got job result: {result}")
                    return result
                except json.JSONDecodeError:
                    pass  # File might be partially written
            
            time.sleep(poll_interval)
            elapsed += poll_interval
        
        raise RuntimeError(f"Elevated job timed out after {timeout}s")
    
    def _cleanup(self):
        """Remove job files."""
        try:
            if self.request_path.exists():
                self.request_path.unlink()
            if self.result_path.exists():
                self.result_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to cleanup job files: {e}")


def run_elevated_action(action: str, timeout: float = 30.0, **params) -> dict:
    """Run an action with elevation if needed.
    
    If already running as admin, executes directly.
    Otherwise, launches an elevated helper process.
    
    Args:
        action: The action to perform.
        timeout: Timeout for elevated execution.
        **params: Action-specific parameters.
        
    Returns:
        Result dictionary with keys: ok, stdout, stderr, code
    """
    if is_admin():
        # Already admin, execute directly
        from vpnmikro.elevated_main import execute_action
        return execute_action(action, params)
    
    # Need elevation
    job = ElevatedJob(action, **params)
    return job.execute_elevated(timeout)
