from __future__ import annotations

import os
import time

from . import messages

DEFAULT_DEMO_TUI_DELAY_SECONDS = 5.0
DEMO_TUI_DELAY_ENV = "TLTG_OPTIMIZED_DEMO_TUI_DELAY_SECONDS"

_DEMO_STATUS_SEQUENCES = {
    "install": (
        messages.CHECKING_FIRMWARE_VERSION,
        messages.CHECKING_PACKAGE_VERSION,
        messages.PERFORMING_PREFLIGHT_CHECKS,
        messages.CREATING_BACKUP,
        messages.INSTALLING,
    ),
    "uninstall": (
        messages.CHECKING_FIRMWARE_VERSION,
        messages.CHECKING_INSTALLED_PACKAGE,
        messages.PERFORMING_UNINSTALL_PREFLIGHT_CHECKS,
        messages.CREATING_BACKUP,
        messages.UNINSTALLING,
    ),
}


def resolve_demo_tui_delay_seconds(*, environ: dict[str, str] | None = None) -> float:
    env = os.environ if environ is None else environ
    raw_value = env.get(DEMO_TUI_DELAY_ENV)
    if raw_value in {None, ""}:
        return DEFAULT_DEMO_TUI_DELAY_SECONDS
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return DEFAULT_DEMO_TUI_DELAY_SECONDS


def run_demo(
    mode: str,
    reporter,
    *,
    delay_seconds: float = DEFAULT_DEMO_TUI_DELAY_SECONDS,
    sleep=None,
) -> None:
    sleep_fn = time.sleep if sleep is None else sleep
    try:
        statuses = _DEMO_STATUS_SEQUENCES[mode]
    except KeyError as exc:  # pragma: no cover - defensive fallback
        raise ValueError(f"Unsupported demo mode: {mode}") from exc

    for status in statuses:
        reporter.status(status)
        sleep_fn(delay_seconds)

    if mode == "install":
        reporter.emit_install_success(patch_results=(), managed_tree_drift=())
        return
    reporter.emit_uninstall_success(patch_results=(), managed_tree_drift=())
