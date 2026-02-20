"""Manages bundled PICT extraction and execution."""
import os
import sys
import platform
import stat
import tempfile
import subprocess
from typing import Tuple

def get_platform_info() -> Tuple[str, str]:
    """Returns a tuple of (os_type, arch_type)."""
    return platform.system().lower(), platform.machine().lower()

def get_vendor_target() -> str:
    system, machine = get_platform_info()
    
    if system == "windows":
        return "win-x64"
    elif system == "linux":
        return "linux-x64"
    elif system == "darwin":
        if "arm" in machine or "aarch64" in machine:
            return "macos-arm64"
        else:
            return "macos-x64"
    else:
        raise RuntimeError(f"Unsupported system architecture: {system} {machine}")

def get_bundled_pict_path() -> str:
    """Returns the bundled source path for the platform's PICT executable."""
    target = get_vendor_target()
    filename = "pict.exe" if "win" in target else "pict"
    
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        # We are in pairwise_cli, so going up one level gets to project root
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
    return os.path.join(base_path, "vendor", "pict", target, filename)

def get_extracted_pict_path() -> str:
    """Returns the path where PICT should be extracted to, creating dirs if needed."""
    target = get_vendor_target()
    filename = "pict.exe" if "win" in target else "pict"
    app_version = "1.0.0" # Hardcoded for now
    
    system, _ = get_platform_info()
    if system == "windows":
        cache_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        base_dir = os.path.join(cache_dir, "pairwise-cli")
    elif system == "darwin":
        base_dir = os.path.expanduser("~/Library/Caches/pairwise-cli")
    else:
        base_dir = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        base_dir = os.path.join(base_dir, "pairwise-cli")
        
    extract_dir = os.path.join(base_dir, "pict", app_version, target)
    os.makedirs(extract_dir, exist_ok=True)
    return os.path.join(extract_dir, filename)

def extract_pict_if_needed() -> str:
    """Extracts PICT to a cache directory if it's not already there. Returns extracted path."""
    source_path = get_bundled_pict_path()
    dest_path = get_extracted_pict_path()
    
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Bundled PICT binary not found at {source_path}. Please build vendor binaries.")
        
    do_extract = True
    if os.path.exists(dest_path):
        src_size = os.path.getsize(source_path)
        dst_size = os.path.getsize(dest_path)
        if src_size == dst_size:
            do_extract = False
            
    if do_extract:
        with open(source_path, "rb") as f_src, open(dest_path, "wb") as f_dst:
            f_dst.write(f_src.read())
            
        system, _ = get_platform_info()
        if system != "windows":
            st = os.stat(dest_path)
            os.chmod(dest_path, st.st_mode | stat.S_IEXEC)
            
    return dest_path

def run_pict(model_content: str, strength: int = 2, seed: int = None) -> str:
    """
    Runs PICT with the given model content.
    Returns standard output.
    """
    pict_exe = extract_pict_if_needed()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pict', delete=False, encoding='utf-8') as f:
        f.write(model_content)
        temp_model_path = f.name
        
    try:
        cmd = [pict_exe, temp_model_path]
        if strength != 2:
            cmd.append(f"/o:{strength}")
        if seed is not None:
            cmd.append(f"/r:{seed}")
            
            
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"PICT failed (code {result.returncode}):\n{result.stderr}")
            
        return result.stdout
    finally:
        if os.path.exists(temp_model_path):
            os.remove(temp_model_path)
