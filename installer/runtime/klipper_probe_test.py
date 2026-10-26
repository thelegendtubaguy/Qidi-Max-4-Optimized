from functools import lru_cache
from pathlib import Path

from .errors import InstallerError


OPERATION = "klipper_probe_signal_test"
FILE = "/home/qidi/klipper/klippy/extras/tltg_probe_test.py"
PAYLOAD = Path(__file__).resolve().parents[1] / "klipper/qidi/tltg_probe_test.py"


@lru_cache(maxsize=1)
def helper_source() -> str:
    desired = PAYLOAD.read_text(encoding="utf-8")
    compile(desired, "tltg_probe_test.py", "exec")
    return desired


def patch_probe_test(current: str) -> str:
    desired = helper_source()
    if current not in ("", desired):
        raise InstallerError("Existing tltg_probe_test.py is unrecognized and was preserved.")
    return desired
