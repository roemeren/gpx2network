from pathlib import Path
from datetime import datetime

DATA_VERSION_FILE = Path("data/processed/DATA_VERSION.txt")
VERSION_FILE = Path("VERSION")

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
    """Return the app version from VERSION file"""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "unknown"