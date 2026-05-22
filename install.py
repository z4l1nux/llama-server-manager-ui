#!/usr/bin/env python3
import sys
import os
import shutil
import subprocess
from pathlib import Path

IS_WINDOWS = sys.platform == 'win32'

def install_linux():
    print("Installing Llama Server Manager on Linux...")
    
    # Define paths
    home = Path.home()
    install_dir = home / '.local' / 'share' / 'llama-manager'
    bin_dest = install_dir / 'llama_manager.py'
    icon_dest = home / '.local' / 'share' / 'icons' / 'llama-manager.png'
    desktop_dest = home / '.local' / 'share' / 'applications' / 'llama-manager.desktop'
    
    # 1. Locate source files
    src_dir = Path(__file__).parent.resolve()
    script_src = src_dir / 'llama_manager.py'
    if not script_src.exists():
        print(f"Error: Could not find llama_manager.py in {src_dir}")
        sys.exit(1)
        
    icon_src = src_dir / 'llama-manager.png'
    if not icon_src.exists():
        # Fallback to existing system icon if found
        potential_icon = home / '.local' / 'share' / 'icons' / 'llama-manager.png'
        if potential_icon.exists():
            icon_src = potential_icon

    # 2. Create directories
    install_dir.mkdir(parents=True, exist_ok=True)
    icon_dest.parent.mkdir(parents=True, exist_ok=True)
    desktop_dest.parent.mkdir(parents=True, exist_ok=True)
    
    # 3. Copy files
    if script_src.resolve() != bin_dest.resolve():
        print(f"Copying script to {bin_dest}")
        shutil.copy2(script_src, bin_dest)
    else:
        print("Script is already in the correct destination.")
    bin_dest.chmod(0o755) # Make executable
    
    if icon_src.exists():
        if icon_src.resolve() != icon_dest.resolve():
            print(f"Copying icon to {icon_dest}")
            shutil.copy2(icon_src, icon_dest)
        else:
            print("Icon is already in the correct destination.")
    else:
        print("Warning: Icon not found, skipping icon installation.")

    # 4. Create Desktop Entry
    print(f"Creating desktop entry at {desktop_dest}")
    desktop_content = f"""[Desktop Entry]
Name=Llama Server Manager
Comment=GUI to manage llama.cpp server
Exec=python3 "{bin_dest}"
Icon=llama-manager
Type=Application
Categories=Development;Utility;
Terminal=false
StartupWMClass=llama-manager
"""
    with open(desktop_dest, 'w') as f:
        f.write(desktop_content)
    desktop_dest.chmod(0o755)
    
    print("\nLlama Server Manager installed successfully on Linux!")
    print("You can launch it from your desktop applications menu.")

def install_windows():
    print("Installing Llama Server Manager on Windows...")
    
    # Define paths
    home = Path.home()
    appdata = Path(os.environ.get('APPDATA', str(home / 'AppData' / 'Roaming')))
    install_dir = appdata / 'llama-manager'
    bin_dest = install_dir / 'llama_manager.py'
    icon_dest = install_dir / 'icon.png'
    
    # 1. Locate source files
    src_dir = Path(__file__).parent.resolve()
    script_src = src_dir / 'llama_manager.py'
    if not script_src.exists():
        print(f"Error: Could not find llama_manager.py in {src_dir}")
        sys.exit(1)
        
    icon_src = src_dir / 'llama-manager.png'
    if not icon_src.exists():
        # Fallback to existing system icon if found (e.g., from Linux home translation if run in WSL/shared env)
        potential_icon = home / '.local' / 'share' / 'icons' / 'llama-manager.png'
        if potential_icon.exists():
            icon_src = potential_icon

    # 2. Create directories
    install_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. Copy files
    if script_src.resolve() != bin_dest.resolve():
        print(f"Copying script to {bin_dest}")
        shutil.copy2(script_src, bin_dest)
    else:
        print("Script is already in the correct destination.")
    
    icon_path_str = ""
    if icon_src.exists():
        if icon_src.resolve() != icon_dest.resolve():
            print(f"Copying icon to {icon_dest}")
            shutil.copy2(icon_src, icon_dest)
        else:
            print("Icon is already in the correct destination.")
        icon_path_str = str(icon_dest)
    else:
        print("Warning: Icon not found, shortcut will use default icon.")

    # 4. Create Desktop and Start Menu Shortcuts via PowerShell
    shortcuts = [
        home / 'Desktop' / 'Llama Server Manager.lnk',
        appdata / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Llama Server Manager.lnk'
    ]
    
    for shortcut_path in shortcuts:
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Creating shortcut at {shortcut_path}")
        
        # PowerShell command to create the shortcut
        # pythonw.exe is used to run the python script without opening a console window
        ps_command = (
            f'$WshShell = New-Object -ComObject WScript.Shell; '
            f'$Shortcut = $WshShell.CreateShortcut("{shortcut_path}"); '
            f'$Shortcut.TargetPath = "pythonw.exe"; '
            f'$Shortcut.Arguments = "`"{bin_dest}`""; '
            f'$Shortcut.WorkingDirectory = "{install_dir}"; '
        )
        if icon_path_str:
            ps_command += f'$Shortcut.IconLocation = "{icon_path_str}"; '
        ps_command += '$Shortcut.Save()'
        
        try:
            subprocess.run(['powershell', '-NoProfile', '-Command', ps_command], check=True, capture_output=True)
        except Exception as e:
            print(f"Error creating shortcut {shortcut_path}: {e}")

    print("\nLlama Server Manager installed successfully on Windows!")
    print("You can launch it from your Desktop or Start Menu.")

def install_mac():
    print("Installing Llama Server Manager on macOS...")

    # Define paths
    home         = Path.home()
    install_dir  = home / 'Library' / 'Application Support' / 'llama-manager'
    bin_dest     = install_dir / 'llama_manager.py'
    app_dir      = home / 'Applications' / 'Llama Server Manager.app'
    contents_dir = app_dir / 'Contents'
    macos_dir    = contents_dir / 'MacOS'
    launcher     = macos_dir / 'Llama Server Manager'

    # 1. Locate source files
    src_dir    = Path(__file__).parent.resolve()
    script_src = src_dir / 'llama_manager.py'
    if not script_src.exists():
        print(f"Error: Could not find llama_manager.py in {src_dir}")
        sys.exit(1)

    icon_src = src_dir / 'llama-manager.png'
    if not icon_src.exists():
        potential_icon = home / '.local' / 'share' / 'icons' / 'llama-manager.png'
        if potential_icon.exists():
            icon_src = potential_icon

    # 2. Create directories
    install_dir.mkdir(parents=True, exist_ok=True)
    macos_dir.mkdir(parents=True, exist_ok=True)

    # 3. Copy files
    if script_src.resolve() != bin_dest.resolve():
        print(f"Copying script to {bin_dest}")
        shutil.copy2(script_src, bin_dest)
    else:
        print("Script is already in the correct destination.")
    bin_dest.chmod(0o755)

    if icon_src.exists():
        icon_dest = install_dir / 'icon.png'
        if icon_src.resolve() != icon_dest.resolve():
            print(f"Copying icon to {icon_dest}")
            shutil.copy2(icon_src, icon_dest)

    # 4. Info.plist — required for Spotlight, Launchpad, and Gatekeeper
    plist_path = contents_dir / 'Info.plist'
    print(f"Creating Info.plist at {plist_path}")
    plist_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
        ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        '<dict>\n'
        '    <key>CFBundleExecutable</key>\n'
        '    <string>Llama Server Manager</string>\n'
        '    <key>CFBundleIdentifier</key>\n'
        '    <string>com.llama-manager.app</string>\n'
        '    <key>CFBundleName</key>\n'
        '    <string>Llama Server Manager</string>\n'
        '    <key>CFBundleVersion</key>\n'
        '    <string>1.0</string>\n'
        '    <key>CFBundlePackageType</key>\n'
        '    <string>APPL</string>\n'
        '    <key>LSMinimumSystemVersion</key>\n'
        '    <string>10.14</string>\n'
        '    <key>NSHighResolutionCapable</key>\n'
        '    <true/>\n'
        '    <key>NSRequiresAquaSystemAppearance</key>\n'
        '    <false/>\n'
        '</dict>\n'
        '</plist>\n'
    )
    with open(plist_path, 'w') as f:
        f.write(plist_content)

    # 5. Launcher with absolute Python path — avoids PATH lookup failure from Finder
    python_exec = sys.executable
    print(f"Creating macOS application bundle at {app_dir}")
    print(f"Python interpreter: {python_exec}")
    launcher_content = f'#!/bin/bash\nexec "{python_exec}" "{bin_dest}" "$@"\n'
    with open(launcher, 'w') as f:
        f.write(launcher_content)
    launcher.chmod(0o755)

    print("\nLlama Server Manager installed successfully on macOS!")
    print(f"Launch: ~/Applications/Llama Server Manager.app")
    print(f"Or run: {python_exec} {bin_dest}")

def main():
    if IS_WINDOWS:
        install_windows()
    elif sys.platform == 'darwin':
        install_mac()
    else:
        install_linux()

if __name__ == '__main__':
    main()
