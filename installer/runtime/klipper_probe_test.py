import hashlib
from functools import lru_cache
from pathlib import Path

from .errors import InstallerError


OPERATION = "klipper_probe_signal_test"
FILE = "/home/qidi/klipper/klippy/extras/tltg_probe_test.py"
PAYLOAD = Path(__file__).resolve().parents[1] / "klipper/qidi/tltg_probe_test.py"
# Helpers from earlier pre-release builds; updates replace these unchanged copies.
PRIOR_HELPER_SHA256 = frozenset({
    "ae125c3a5f9e26980c44e7d4fb8c43b69bdd2ef3bea180145ad2864bc723375f",
})


@lru_cache(maxsize=1)
def helper_source() -> str:
    desired = PAYLOAD.read_text(encoding="utf-8")
    compile(desired, "tltg_probe_test.py", "exec")
    return desired


def patch_probe_test(current: str) -> str:
    desired = helper_source()
    if current in ("", desired) or hashlib.sha256(current.encode("utf-8")).hexdigest() in PRIOR_HELPER_SHA256:
        return desired
    raise InstallerError("Existing tltg_probe_test.py is unrecognized and was preserved.")
