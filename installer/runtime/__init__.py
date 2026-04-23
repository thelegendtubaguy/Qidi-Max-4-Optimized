from pathlib import Path
import sys

_VENDOR_ROOT = Path(__file__).resolve().parent / "vendor"
if _VENDOR_ROOT.exists():
    vendor_entry = str(_VENDOR_ROOT)
    if vendor_entry not in sys.path:
        sys.path.insert(0, vendor_entry)
