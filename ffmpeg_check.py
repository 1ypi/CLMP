import subprocess
import sys
import shutil
import os
def _find_ffmpeg():
    return shutil.which('ffmpeg') is not None
def _get_install_cmd():
    if sys.platform == 'win32':
        if shutil.which('winget'):
            return ['winget', 'install', 'Gyan.FFmpeg', '--accept-source-agreements', '--accept-package-agreements'], 'winget'
        if shutil.which('choco'):
            return ['choco', 'install', 'ffmpeg', '-y'], 'Chocolatey'
        return None, None
    elif sys.platform == 'darwin':
        if shutil.which('brew'):
            return ['brew', 'install', 'ffmpeg'], 'Homebrew'
        return None, None
    else:
        if shutil.which('apt-get'):
            return ['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], 'apt'
        if shutil.which('dnf'):
            return ['sudo', 'dnf', 'install', '-y', 'ffmpeg'], 'dnf'
        if shutil.which('pacman'):
            return ['sudo', 'pacman', '-S', '--noconfirm', 'ffmpeg'], 'pacman'
        return None, None
def _refresh_path_windows():
    try:
        import winreg
        parts = []
        for root, sub in [
            (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
            (winreg.HKEY_CURRENT_USER, r'Environment'),
        ]:
            try:
                with winreg.OpenKey(root, sub) as key:
                    parts.append(winreg.QueryValueEx(key, 'Path')[0])
            except OSError:
                pass
        if parts:
            os.environ['PATH'] = ';'.join(parts)
    except Exception:
        pass
def ensure_ffmpeg():
    if _find_ffmpeg():
        return True
    print("\n  [!] ffmpeg not found on PATH.")
    cmd, manager = _get_install_cmd()
    if cmd is None:
        if sys.platform == 'win32':
            print("  No supported package manager found (winget or choco).")
        elif sys.platform == 'darwin':
            print("  Homebrew not found. Install it: https://brew.sh")
        else:
            print("  No supported package manager found (apt, dnf, pacman).")
        print("  Please install ffmpeg manually: https://ffmpeg.org/download.html")
        return False
    answer = input(f"  Install ffmpeg via {manager}? [Y/n] ").strip().lower()
    if answer not in ('', 'y', 'yes'):
        print("  Skipping ffmpeg installation. Audio features will not work.")
        return False
    print(f"  Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print("  [ERROR] Installation failed. Install manually: https://ffmpeg.org/download.html")
            return False
    except FileNotFoundError:
        print(f"  [ERROR] {manager} not found.")
        return False
    if sys.platform == 'win32':
        _refresh_path_windows()
    if _find_ffmpeg():
        print("  ffmpeg installed and ready!")
        return True
    print("  ffmpeg installed but not yet on PATH in this session.")
    print("  Please restart your terminal and try again.")
    return False
