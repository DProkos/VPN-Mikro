"""Elevated helper entrypoint for VPN Mikro.

This module runs in an elevated (admin) process to perform
privileged operations like installing/uninstalling WireGuard tunnels.

Usage:
    python -m vpnmikro.elevated_main --job-id <uuid> --data-dir <path>
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

# Don't import logger here to avoid UI dependencies in elevated mode


def get_wireguard_exe_path() -> Path:
    """Get the path to wireguard.exe.
    
    Searches in order:
    1. wintun/ folder (bundled)
    2. bin/ folder (legacy)
    3. System PATH
    
    Returns:
        Path to wireguard.exe
        
    Raises:
        FileNotFoundError: If wireguard.exe not found.
    """
    # Get the base directory (where vpnmikro package is)
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        base_dir = Path(sys.executable).parent
    else:
        # Running as script
        base_dir = Path(__file__).parent.parent
    
    # Check wintun folder first (new location)
    wintun_path = base_dir / "wintun" / "wireguard.exe"
    if wintun_path.exists():
        return wintun_path
    
    # Check bin folder (legacy location)
    bin_path = base_dir / "bin" / "wireguard.exe"
    if bin_path.exists():
        return bin_path
    
    # Check system PATH
    import shutil
    system_wg = shutil.which("wireguard")
    if system_wg:
        return Path(system_wg)
    
    raise FileNotFoundError(
        f"wireguard.exe not found. Searched:\n"
        f"  - {wintun_path}\n"
        f"  - {bin_path}\n"
        f"  - System PATH\n"
        "Please ensure WireGuard is bundled with the application."
    )


def execute_action(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an elevated action.
    
    Args:
        action: Action name (install_tunnel, uninstall_tunnel, etc.)
        params: Action parameters
        
    Returns:
        Result dict with keys: ok, stdout, stderr, code
    """
    try:
        wg = get_wireguard_exe_path()
        
        if action == "install_tunnel":
            config_path = params.get("config")
            if not config_path:
                return _result(False, "", "Missing config parameter", 1)
            
            cp = subprocess.run(
                [str(wg), "/installtunnelservice", config_path],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return _result(cp.returncode == 0, cp.stdout, cp.stderr, cp.returncode)
        
        elif action == "uninstall_tunnel":
            tunnel_name = params.get("tunnel")
            if not tunnel_name:
                return _result(False, "", "Missing tunnel parameter", 1)
            
            cp = subprocess.run(
                [str(wg), "/uninstalltunnelservice", tunnel_name],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return _result(cp.returncode == 0, cp.stdout, cp.stderr, cp.returncode)
        
        elif action == "probe_status":
            # Just check if wireguard.exe exists and is accessible
            return _result(True, str(wg), "", 0)
        
        else:
            return _result(False, "", f"Unknown action: {action}", 2)
    
    except FileNotFoundError as e:
        return _result(False, "", str(e), 1)
    except Exception as e:
        return _result(False, "", f"Error: {e}", 1)


def _result(ok: bool, stdout: str, stderr: str, code: int) -> Dict[str, Any]:
    """Create a result dictionary."""
    return {
        "ok": ok,
        "stdout": stdout,
        "stderr": stderr,
        "code": code
    }


def main():
    """Main entrypoint for elevated helper."""
    args = sys.argv[1:]
    
    # Parse arguments
    job_id = _get_arg(args, "--job-id")
    data_dir = Path(_get_arg(args, "--data-dir"))
    
    # Paths
    request_path = data_dir / "jobs" / f"job_request_{job_id}.json"
    result_path = data_dir / "jobs" / f"job_result_{job_id}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Read job request
        if not request_path.exists():
            _write_result(result_path, False, "", f"Job request not found: {request_path}", 1)
            return
        
        request = json.loads(request_path.read_text(encoding="utf-8"))
        action = request.get("action", "")
        params = request.get("params", {})
        
        # Execute action
        result = execute_action(action, params)
        
        # Write result
        _write_result(result_path, result["ok"], result["stdout"], result["stderr"], result["code"])
    
    except Exception as e:
        _write_result(result_path, False, "", str(e), 1)


def _get_arg(args: list, key: str) -> str:
    """Get argument value by key."""
    try:
        i = args.index(key)
        return args[i + 1]
    except (ValueError, IndexError):
        raise ValueError(f"Missing required argument: {key}")


def _write_result(path: Path, ok: bool, stdout: str, stderr: str, code: int):
    """Write result to file."""
    result = {
        "ok": ok,
        "stdout": stdout,
        "stderr": stderr,
        "code": code
    }
    path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
