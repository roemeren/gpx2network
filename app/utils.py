# core/data_utils.py
from pathlib import Path
import subprocess
from datetime import datetime

DATA_VERSION_FILE = Path("data/processed/DATA_VERSION.txt")

def get_data_version():
    """Return dataset version from DATA_VERSION.txt as DD-MMM-YYYY, or 'unknown'."""
    if DATA_VERSION_FILE.exists():
        raw = DATA_VERSION_FILE.read_text().strip()
        try:
            # Parse YYMMDD
            dt = datetime.strptime(raw, "%y%m%d")
            return dt.strftime("%d-%b-%Y")  # e.g., 22-Sep-2025
        except Exception:
            return raw
    return "unknown"

def get_app_version():
    """Return the app version: prefer VERSION file (deployed), fallback to git tag (dev)."""
    version_file = Path("VERSION")
    if version_file.exists():
        return version_file.read_text().strip()
    try:
        # Only works in a git repo locally
        return subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"], text=True
        ).strip()
    except Exception:
        return "unknown"