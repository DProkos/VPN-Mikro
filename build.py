#!/usr/bin/env python3
"""
VPN Mikro Build Script
======================
Creates:
1. Nuitka onedir build (standalone folder with exe)
2. NSIS installer (.exe setup file)

Requirements:
- Python 3.11+
- Nuitka: pip install nuitka
- NSIS: https://nsis.sourceforge.io/Download (add to PATH)

Usage:
    python build.py          # Build both onedir and installer
    python build.py onedir   # Build only onedir
    python build.py nsis     # Build only NSIS installer (requires onedir first)
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Build configuration
APP_NAME = "VPNMikro"
APP_VERSION = "0.0.5"
APP_PUBLISHER = "Dionisis Prokos"
APP_DESCRIPTION = "WireGuard VPN Manager for MikroTik"
APP_ICON_EXE = "logo/logo-main.ico"      # Icon for the .exe file
APP_ICON_TRAY = "logo/logo_no_BG.ico"    # Icon for system tray
MAIN_SCRIPT = "vpnmikro.py"
OUTPUT_DIR = Path("dist")
BUILD_DIR = Path("build")
NSIS_SCRIPT = BUILD_DIR / "installer.nsi"


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 50)
    print(f"  {text}")
    print("=" * 50)


def print_step(step: int, total: int, text: str):
    """Print a step indicator."""
    print(f"\n[{step}/{total}] {text}")


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"  Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: {description} failed with code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"  ERROR: Command not found: {cmd[0]}")
        return False


def check_requirements() -> bool:
    """Check if all required tools are installed."""
    print_step(1, 5, "Checking requirements...")
    
    # Check Nuitka
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True, text=True
        )
        print(f"  ✓ Nuitka: {result.stdout.strip().split()[0] if result.stdout else 'installed'}")
    except Exception:
        print("  ✗ Nuitka not found. Install with: pip install nuitka")
        return False
    
    # Check NSIS - also check common install locations
    global NSIS_PATH
    NSIS_PATH = shutil.which("makensis")
    
    if not NSIS_PATH:
        # Check common NSIS install locations
        nsis_locations = [
            r"C:\Program Files (x86)\NSIS\makensis.exe",
            r"C:\Program Files\NSIS\makensis.exe",
            Path.home() / "AppData" / "Local" / "Programs" / "NSIS" / "makensis.exe",
        ]
        for loc in nsis_locations:
            if Path(loc).exists():
                NSIS_PATH = str(loc)
                break
    
    if NSIS_PATH:
        print(f"  ✓ NSIS: {NSIS_PATH}")
    else:
        print("  ⚠ NSIS not found in PATH. Installer creation will be skipped.")
        print("    Download from: https://nsis.sourceforge.io/Download")
    
    # Check icon files
    if Path(APP_ICON_EXE).exists():
        print(f"  ✓ EXE Icon: {APP_ICON_EXE}")
    else:
        print(f"  ⚠ EXE Icon not found: {APP_ICON_EXE}")
    
    if Path(APP_ICON_TRAY).exists():
        print(f"  ✓ Tray Icon: {APP_ICON_TRAY}")
    else:
        print(f"  ⚠ Tray Icon not found: {APP_ICON_TRAY}")
    
    return True

# Global variable for NSIS path
NSIS_PATH = None


def clean_build():
    """Clean previous build artifacts."""
    print_step(2, 5, "Cleaning previous builds...")
    
    dirs_to_clean = [
        OUTPUT_DIR,
        BUILD_DIR,
        Path("vpnmikro.build"),
        Path("vpnmikro.dist"),
        Path("vpnmikro.onefile-build"),
    ]
    
    for dir_path in dirs_to_clean:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  Removed: {dir_path}")
    
    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    print("  Created: dist/, build/")


def build_nuitka_onedir() -> bool:
    """Build the application with Nuitka in onedir mode."""
    print_step(3, 5, "Building with Nuitka (onedir mode)...")
    print("  This may take several minutes...")
    
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--windows-console-mode=disable",
        "--enable-plugin=pyqt6",
        "--include-data-dir=assets=assets",
        "--include-data-dir=wintun=wintun",
        "--include-data-dir=logo=logo",
        "--include-data-dir=licenses=licenses",
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={APP_NAME}.exe",
        f"--company-name={APP_PUBLISHER}",
        f"--product-name={APP_NAME}",
        f"--file-version={APP_VERSION}.0",
        f"--product-version={APP_VERSION}.0",
        f"--file-description={APP_DESCRIPTION}",
        "--windows-uac-admin",  # Request admin privileges
        # Code protection options
        "--lto=yes",  # Link Time Optimization - makes reverse engineering harder
        "--remove-output",  # Remove build artifacts
    ]
    
    # Add icon if exists (use logo-main.ico for exe)
    if Path(APP_ICON_EXE).exists():
        cmd.append(f"--windows-icon-from-ico={APP_ICON_EXE}")
    
    cmd.append(MAIN_SCRIPT)
    
    if not run_command(cmd, "Nuitka build"):
        return False
    
    # Rename output folder
    nuitka_output = OUTPUT_DIR / "vpnmikro.dist"
    final_output = OUTPUT_DIR / APP_NAME
    
    if nuitka_output.exists():
        if final_output.exists():
            shutil.rmtree(final_output)
        nuitka_output.rename(final_output)
        print(f"  ✓ Output: {final_output}")
    
    return True


def create_nsis_script():
    """Generate the NSIS installer script."""
    # Use absolute paths for icons and license
    icon_path = Path(APP_ICON_EXE).absolute()
    license_path = Path("licenses/LICENSE-vpnmikro.txt").absolute()
    header_img = Path("logo/logo-main.png").absolute()
    
    script = f'''!include "MUI2.nsh"
!include "FileFunc.nsh"

; Application info
!define APP_NAME "{APP_NAME}"
!define APP_VERSION "{APP_VERSION}"
!define APP_PUBLISHER "{APP_PUBLISHER}"
!define APP_DESCRIPTION "{APP_DESCRIPTION}"
!define APP_EXE "{APP_NAME}.exe"
!define APP_ICON "$INSTDIR\\logo\\logo-main.ico"
!define INSTALL_DIR "$PROGRAMFILES\\${{APP_NAME}}"

; Installer attributes
Name "${{APP_NAME}} ${{APP_VERSION}}"
OutFile "..\\dist\\{APP_NAME}-Setup-${{APP_VERSION}}.exe"
InstallDir "${{INSTALL_DIR}}"
InstallDirRegKey HKLM "Software\\${{APP_NAME}}" "InstallDir"
RequestExecutionLevel admin
BrandingText "${{APP_NAME}} ${{APP_VERSION}} - ${{APP_PUBLISHER}}"

; Set installer/uninstaller icons
!define MUI_ICON "{icon_path}"
!define MUI_UNICON "{icon_path}"

; Header image (logo on top right of installer)
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_HEADERIMAGE_BITMAP_NOSTRETCH

; Welcome/Finish page image (logo on left side)
!define MUI_WELCOMEFINISHPAGE_BITMAP_NOSTRETCH

; Modern UI settings
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Welcome to ${{APP_NAME}} Setup"
!define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through the installation of ${{APP_NAME}} ${{APP_VERSION}}.$\\r$\\n$\\r$\\n${{APP_DESCRIPTION}}$\\r$\\n$\\r$\\nClick Next to continue."
!define MUI_FINISHPAGE_TITLE "Installation Complete"
!define MUI_FINISHPAGE_TEXT "${{APP_NAME}} has been installed on your computer.$\\r$\\n$\\r$\\nClick Finish to close this wizard."
!define MUI_FINISHPAGE_RUN "$INSTDIR\\${{APP_EXE}}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${{APP_NAME}}"
!define MUI_FINISHPAGE_LINK "Visit VPN Mikro Website"
!define MUI_FINISHPAGE_LINK_LOCATION "https://github.com/vpnmikro"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "{license_path}"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Language
!insertmacro MUI_LANGUAGE "English"

; Version info for installer exe
VIProductVersion "{APP_VERSION}.0"
VIAddVersionKey "ProductName" "${{APP_NAME}}"
VIAddVersionKey "CompanyName" "${{APP_PUBLISHER}}"
VIAddVersionKey "LegalCopyright" "Copyright (c) 2024 ${{APP_PUBLISHER}}"
VIAddVersionKey "FileDescription" "${{APP_NAME}} Installer"
VIAddVersionKey "FileVersion" "{APP_VERSION}"
VIAddVersionKey "ProductVersion" "{APP_VERSION}"

; Installer section
Section "Install"
    SetOutPath "$INSTDIR"
    
    ; Copy all files from the onedir build (dist/VPNMikro folder)
    File /r "..\\dist\\{APP_NAME}\\*.*"
    
    ; Create uninstaller
    WriteUninstaller "$INSTDIR\\Uninstall.exe"
    
    ; Create Start Menu shortcuts with icon
    CreateDirectory "$SMPROGRAMS\\${{APP_NAME}}"
    CreateShortcut "$SMPROGRAMS\\${{APP_NAME}}\\${{APP_NAME}}.lnk" "$INSTDIR\\${{APP_EXE}}" "" "$INSTDIR\\logo\\logo-main.ico" 0
    CreateShortcut "$SMPROGRAMS\\${{APP_NAME}}\\Uninstall ${{APP_NAME}}.lnk" "$INSTDIR\\Uninstall.exe" "" "$INSTDIR\\Uninstall.exe" 0
    
    ; Create Desktop shortcut with icon
    CreateShortcut "$DESKTOP\\${{APP_NAME}}.lnk" "$INSTDIR\\${{APP_EXE}}" "" "$INSTDIR\\logo\\logo-main.ico" 0
    
    ; Write registry keys for Add/Remove Programs
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APP_NAME}}" "DisplayName" "${{APP_NAME}}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APP_NAME}}" "DisplayVersion" "${{APP_VERSION}}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APP_NAME}}" "Publisher" "${{APP_PUBLISHER}}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APP_NAME}}" "UninstallString" '"$INSTDIR\\Uninstall.exe"'
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APP_NAME}}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APP_NAME}}" "DisplayIcon" "$INSTDIR\\logo\\logo-main.ico"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APP_NAME}}" "URLInfoAbout" "https://github.com/vpnmikro"
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APP_NAME}}" "NoModify" 1
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APP_NAME}}" "NoRepair" 1
    
    ; Calculate and write install size
    ${{GetSize}} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APP_NAME}}" "EstimatedSize" "$0"
    
    ; Save install directory
    WriteRegStr HKLM "Software\\${{APP_NAME}}" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\\${{APP_NAME}}" "Version" "${{APP_VERSION}}"
SectionEnd

; Uninstaller section
Section "Uninstall"
    ; Remove application data (optional - ask user)
    MessageBox MB_YESNO "Do you want to remove application data (profiles, configs)?" IDNO skip_data
    RMDir /r "$LOCALAPPDATA\\${{APP_NAME}}"
    RMDir /r "$APPDATA\\${{APP_NAME}}"
    RMDir /r "C:\\ProgramData\\VPNMikro"
    skip_data:
    
    ; Remove files
    RMDir /r "$INSTDIR"
    
    ; Remove Start Menu shortcuts
    RMDir /r "$SMPROGRAMS\\${{APP_NAME}}"
    
    ; Remove Desktop shortcut
    Delete "$DESKTOP\\${{APP_NAME}}.lnk"
    
    ; Remove registry keys
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{APP_NAME}}"
    DeleteRegKey HKLM "Software\\${{APP_NAME}}"
SectionEnd
'''
    
    NSIS_SCRIPT.write_text(script, encoding='utf-8')
    print(f"  Created: {NSIS_SCRIPT}")


def build_nsis_installer() -> bool:
    """Build the NSIS installer."""
    print_step(4, 5, "Creating NSIS installer...")
    
    # Check if NSIS is available
    if not NSIS_PATH:
        print("  ⚠ NSIS not found, skipping installer creation")
        return True
    
    # Check if onedir build exists
    onedir_path = OUTPUT_DIR / APP_NAME
    if not onedir_path.exists():
        print(f"  ERROR: Onedir build not found at {onedir_path}")
        print("  Run 'python build.py onedir' first")
        return False
    
    # Create NSIS script
    create_nsis_script()
    
    # Run NSIS
    cmd = [NSIS_PATH, str(NSIS_SCRIPT)]
    if not run_command(cmd, "NSIS installer"):
        return False
    
    installer_path = OUTPUT_DIR / f"{APP_NAME}-Setup-{APP_VERSION}.exe"
    if installer_path.exists():
        size_mb = installer_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ Installer: {installer_path} ({size_mb:.1f} MB)")
    
    return True


def print_summary():
    """Print build summary."""
    print_step(5, 5, "Build complete!")
    
    print("\n" + "=" * 50)
    print("  BUILD SUMMARY")
    print("=" * 50)
    
    onedir_path = OUTPUT_DIR / APP_NAME
    installer_path = OUTPUT_DIR / f"{APP_NAME}-Setup-{APP_VERSION}.exe"
    
    if onedir_path.exists():
        exe_path = onedir_path / f"{APP_NAME}.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\n  Portable (onedir):")
            print(f"    Location: {onedir_path}")
            print(f"    Executable: {exe_path.name} ({size_mb:.1f} MB)")
    
    if installer_path.exists():
        size_mb = installer_path.stat().st_size / (1024 * 1024)
        print(f"\n  Installer:")
        print(f"    Location: {installer_path}")
        print(f"    Size: {size_mb:.1f} MB")
    
    print("\n  Note: The application requires Administrator")
    print("  privileges and will prompt for elevation on launch.")
    print()


def main():
    """Main build function."""
    print_header(f"{APP_NAME} Build Script v{APP_VERSION}")
    
    # Parse arguments
    args = sys.argv[1:]
    build_onedir = not args or "onedir" in args or "all" in args
    build_installer = not args or "nsis" in args or "installer" in args or "all" in args
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Clean if building onedir
    if build_onedir:
        clean_build()
    
    # Build onedir
    if build_onedir:
        if not build_nuitka_onedir():
            print("\n  ✗ Nuitka build failed!")
            sys.exit(1)
    
    # Build installer
    if build_installer:
        if not build_nsis_installer():
            print("\n  ✗ NSIS installer failed!")
            sys.exit(1)
    
    # Summary
    print_summary()


if __name__ == "__main__":
    main()
