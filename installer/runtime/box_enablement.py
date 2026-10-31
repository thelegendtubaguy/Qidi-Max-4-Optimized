from __future__ import annotations

import json
import re
import shlex
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from . import klipper_cfg, messages, safety
from .errors import ActivePrintError, InstallerError, PrinterStateError
from .fs_atomic import atomic_delete, atomic_write_text
from .interaction import confirm_yes
from .models import RuntimePaths
from .process_restart import ProcessRestartError, read_printer_info
from .reporter import DetailGroup

VALUE_T_RE = re.compile(r"^value_t(?P<tool>\d+)$")
SAVED_VARIABLE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MAX_SAVED_VARIABLE_VALUE_LENGTH = 96
RUNTIME_STATE_FILE = "config/tltg_optimized_runtime_state.json"
SAVED_VARIABLE_VERIFY_MARKER = ".tltg_optimized_saved_variables_verify_pending"
UrlOpenFn = Callable[..., object]


class SavedVariablePersistenceError(InstallerError):
    """A live Klipper saved-variable operation could not be verified."""


def saved_variable_verify_marker_path(paths: RuntimePaths) -> Path:
    return paths.printer_data_root / SAVED_VARIABLE_VERIFY_MARKER


def write_saved_variable_verify_marker(paths: RuntimePaths, values: Mapping[str, str]) -> None:
    if not values:
        return
    _validate_saved_values(values)
    atomic_write_text(
        saved_variable_verify_marker_path(paths),
        json.dumps({"schema_version": 1, "values": dict(sorted(values.items()))}, sort_keys=True) + "\n",
        mode=0o600,
        force_mode=True,
    )


def verify_pending_saved_variable_expectations(
    paths: RuntimePaths,
    *,
    clear: bool = True,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> bool:
    path = saved_variable_verify_marker_path(paths)
    if not path.exists():
        return False
    if paths.restart_marker_path.exists():
        return False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        values = raw["values"] if isinstance(raw, dict) and raw.get("schema_version") == 1 else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SavedVariablePersistenceError("Saved-variable verification marker is invalid.") from exc
    if not isinstance(values, dict) or not values or any(
        not isinstance(name, str) or not isinstance(value, str)
        for name, value in values.items()
    ):
        raise SavedVariablePersistenceError("Saved-variable verification marker is invalid.")
    _validate_saved_values(values)
    _verify_saved_values(paths, values, urlopen=urlopen)
    if clear:
        atomic_delete(path)
    return True


@dataclass(frozen=True)
class BoxEnablementOpportunity:
    saved_variables_path: Path
    box_count: int
    enable_box: int


@dataclass(frozen=True)
class ToolSlotMismatch:
    tool: int
    variable: str
    current: str
    expected: str


@dataclass(frozen=True)
class RequiredToolSlotGap:
    tool: int
    variable: str
    current: str
    expected: str


@dataclass(frozen=True)
class RequiredToolSlotOpportunity:
    saved_variables_path: Path
    box_count: int
    gaps: tuple[RequiredToolSlotGap, ...]


@dataclass(frozen=True)
class ToolSlotAlignmentOpportunity:
    saved_variables_path: Path
    mismatches: tuple[ToolSlotMismatch, ...]


def maybe_initialize_filament_retention(
    *,
    paths: RuntimePaths,
    reporter,
    journal=None,
    written: dict[str, str] | None = None,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> bool:
    variables = read_live_saved_variables(paths, urlopen=urlopen)
    if "tltg_keep_loaded_between_prints" in variables:
        reporter.debug(event="filament_retention_default.preserved")
        return False
    saved = save_live_variables(
        paths,
        {"tltg_keep_loaded_between_prints": "1"},
        missing_only=frozenset({"tltg_keep_loaded_between_prints"}),
        urlopen=urlopen,
    )
    if written is not None:
        written.update(saved)
    if not saved:
        reporter.debug(event="filament_retention_default.preserved")
        return False
    reporter.line(messages.FILAMENT_RETENTION_DEFAULT_ENABLED)
    return True


# Release defaults for tltg_box_feed_motion, saved as a set only when no motion
# setting exists. A setting saved as None (QIDI's value) counts as present.
BOX_MOTION_DEFAULTS = {
    "tltg_box_load_fast_length": "950",
    "tltg_box_load_fast_speed_1": "85",
    "tltg_box_load_fast_speed_2": "65",
    "tltg_box_load_approach_speed": "15",
    "tltg_box_unload_speed_1": "65",
    "tltg_box_unload_speed_2": "85",
    "tltg_box_unload_extruder_length": "50",
}
# Speed pairs earlier releases saved as defaults. Update lowers a pair the
# operator left at those values to the current defaults; a pair with either
# speed changed is the operator's.
PREVIOUS_BOX_MOTION_SPEED_DEFAULTS = (
    {"tltg_box_load_fast_speed_1": "120", "tltg_box_load_fast_speed_2": "100"},
    {"tltg_box_unload_speed_1": "115", "tltg_box_unload_speed_2": "120"},
)
BOX_MOTION_SETTINGS = frozenset(BOX_MOTION_DEFAULTS) | {
    "tltg_box_load_accel",
    "tltg_box_unload_accel",
}


def maybe_initialize_box_motion(
    *,
    paths: RuntimePaths,
    reporter,
    journal=None,
    written: dict[str, str] | None = None,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> bool:
    if read_live_saved_variable_names(paths, urlopen=urlopen) & BOX_MOTION_SETTINGS:
        return _lower_previous_box_motion_speeds(
            paths=paths, reporter=reporter, written=written, urlopen=urlopen
        )
    saved = save_live_variables(
        paths,
        BOX_MOTION_DEFAULTS,
        missing_only=frozenset(BOX_MOTION_DEFAULTS),
        urlopen=urlopen,
    )
    if written is not None:
        written.update(saved)
    if not saved:
        reporter.debug(event="box_motion_defaults.preserved")
        return False
    reporter.line(messages.BOX_MOTION_DEFAULTS_SAVED)
    return True


def _lower_previous_box_motion_speeds(*, paths, reporter, written, urlopen) -> bool:
    variables = read_live_saved_variables(paths, urlopen=urlopen)
    lowered = {
        name: BOX_MOTION_DEFAULTS[name]
        for pair in PREVIOUS_BOX_MOTION_SPEED_DEFAULTS
        if all(variables.get(name) == value for name, value in pair.items())
        for name in pair
    }
    saved = save_live_variables(paths, lowered, urlopen=urlopen)
    if written is not None:
        written.update(saved)
    if not saved:
        reporter.debug(event="box_motion_defaults.preserved")
        return False
    reporter.line(messages.BOX_MOTION_SPEEDS_LOWERED)
    return True


def maybe_prompt_enable_box(
    *,
    paths: RuntimePaths,
    reporter,
    input_stream,
    journal=None,
    written: dict[str, str] | None = None,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> bool:
    opportunity = detect_box_enablement_opportunity(paths, urlopen=urlopen)
    if opportunity is None:
        reporter.debug(event="box_enablement.skipped")
        return False
    reporter.debug(
        event="box_enablement.detected",
        box_count=opportunity.box_count,
        enable_box=opportunity.enable_box,
        saved_variables_path=opportunity.saved_variables_path,
    )
    if not confirm_yes(
        reporter=reporter,
        input_stream=input_stream,
        question=messages.ENABLE_QIDI_BOX_PROMPT.format(box_count=opportunity.box_count),
        instruction=messages.ENABLE_QIDI_BOX_PROMPT_INSTRUCTION,
        cancel_message=messages.ENABLE_QIDI_BOX_DECLINED,
    ):
        return False
    saved = save_live_variables(paths, {"enable_box": "1"}, urlopen=urlopen)
    if written is not None:
        written.update(saved)
    reporter.line(messages.ENABLE_QIDI_BOX_ENABLED)
    return True


def maybe_write_required_tool_slot_variables(
    *,
    paths: RuntimePaths,
    reporter,
    journal=None,
    written: dict[str, str] | None = None,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> bool:
    opportunity = detect_required_tool_slot_opportunity(paths, urlopen=urlopen)
    if opportunity is None:
        reporter.debug(event="required_tool_slots.skipped")
        return False
    reporter.debug(
        event="required_tool_slots.detected",
        box_count=opportunity.box_count,
        gaps=len(opportunity.gaps),
        saved_variables_path=opportunity.saved_variables_path,
    )
    saved = save_live_variables(
        paths,
        {gap.variable: _quote_saved_string(gap.expected) for gap in opportunity.gaps},
        missing_or_empty=frozenset(gap.variable for gap in opportunity.gaps),
        urlopen=urlopen,
    )
    if written is not None:
        written.update(saved)
    if not saved:
        reporter.debug(event="required_tool_slots.preserved_after_live_recheck")
        return False
    reporter.line(
        messages.REQUIRED_TOOL_SLOT_MAPPINGS_WRITTEN.format(count=len(saved))
    )
    return True


def maybe_repair_saved_variables(
    *,
    paths: RuntimePaths,
    reporter,
    written: dict[str, str] | None = None,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> bool:
    """Repair unattended defaults only after the caller has confirmed idleness."""
    changed = maybe_initialize_filament_retention(
        paths=paths, reporter=reporter, written=written, urlopen=urlopen
    )
    changed = maybe_initialize_box_motion(
        paths=paths, reporter=reporter, written=written, urlopen=urlopen
    ) or changed
    return maybe_write_required_tool_slot_variables(
        paths=paths, reporter=reporter, written=written, urlopen=urlopen
    ) or changed


def maybe_reconcile_tool_slots_after_box_count_change(
    *,
    paths: RuntimePaths,
    reporter,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> bool:
    try:
        safety.ensure_printer_idle(paths.moonraker_url, urlopen=urlopen)
        variables = read_live_saved_variables(paths, urlopen=urlopen)
    except ActivePrintError:
        reporter.line(messages.REQUIRED_TOOL_SLOT_RECONCILE_SKIPPED_ACTIVE_PRINT)
        return False
    except (PrinterStateError, SavedVariablePersistenceError):
        reporter.line(messages.REQUIRED_TOOL_SLOT_RECONCILE_SKIPPED_UNKNOWN_STATE)
        return False

    if not _box_stack_available(paths, urlopen=urlopen):
        reporter.debug(event="required_tool_slots.reconcile_skipped", reason="not_configured")
        return False
    box_count = _resolve_live_int(variables, "box_count", default=0)
    gaps = collect_required_tool_slot_gaps_from_variables(variables)
    # A matching count is only an observation, never proof that an older release
    # initialized every required mapping.
    state = _read_runtime_state(paths)
    observed_count = _coerce_optional_int(state.get("last_observed_box_count"))
    if not gaps and observed_count == box_count:
        reporter.debug(event="required_tool_slots.reconcile_observed", box_count=box_count, gaps=0)
        return False
    if gaps:
        saved = save_live_variables(
            paths,
            {gap.variable: _quote_saved_string(gap.expected) for gap in gaps},
            missing_or_empty=frozenset(gap.variable for gap in gaps),
            urlopen=urlopen,
        )
        if not saved:
            reporter.debug(event="required_tool_slots.reconcile_preserved_after_live_recheck")
            return False
        reporter.line(
            messages.REQUIRED_TOOL_SLOT_RECONCILED.format(box_count=box_count, count=len(saved))
        )
    else:
        reporter.debug(event="required_tool_slots.reconcile_observed", box_count=box_count, gaps=0)
    _write_runtime_state(paths, {**state, "last_observed_box_count": box_count})
    return bool(gaps)


def maybe_prompt_align_tool_slots(
    *,
    paths: RuntimePaths,
    reporter,
    input_stream,
    journal=None,
    written: dict[str, str] | None = None,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> bool:
    if input_stream is None:
        reporter.debug(event="tool_slot_alignment.skipped", reason="noninteractive")
        return False
    opportunity = detect_tool_slot_alignment_opportunity(paths, urlopen=urlopen)
    if opportunity is None:
        reporter.debug(event="tool_slot_alignment.skipped")
        return False
    reporter.debug(
        event="tool_slot_alignment.detected",
        mismatches=len(opportunity.mismatches),
        saved_variables_path=opportunity.saved_variables_path,
    )
    rows = tuple(
        f"{mismatch.variable}: {mismatch.current} -> {mismatch.expected}"
        for mismatch in opportunity.mismatches
    )
    if hasattr(reporter, "emit_detail_groups"):
        reporter.emit_detail_groups(
            (DetailGroup(messages.TOOL_SLOT_MAPPING_MISMATCH_HEADER, rows),)
        )
    else:
        reporter.prepare_for_prompt()
        reporter.line(messages.TOOL_SLOT_MAPPING_MISMATCH_HEADER)
        for row in rows:
            reporter.line(f"  - {row}")
    if not confirm_yes(
        reporter=reporter,
        input_stream=input_stream,
        question=messages.TOOL_SLOT_MAPPING_PROMPT,
        instruction=messages.TOOL_SLOT_MAPPING_PROMPT_INSTRUCTION,
        cancel_message=messages.TOOL_SLOT_MAPPING_DECLINED,
    ):
        return False
    saved = save_live_variables(
        paths,
        {mismatch.variable: _quote_saved_string(mismatch.expected) for mismatch in opportunity.mismatches},
        urlopen=urlopen,
    )
    if written is not None:
        written.update(saved)
    reporter.line(messages.TOOL_SLOT_MAPPING_CORRECTED)
    return True


def detect_box_enablement_opportunity(
    paths: RuntimePaths, *, urlopen: UrlOpenFn = urllib.request.urlopen
) -> BoxEnablementOpportunity | None:
    if not _box_stack_available(paths, urlopen=urlopen):
        return None
    variables = read_live_saved_variables(paths, urlopen=urlopen)
    box_count_value = _resolve_live_int(variables, "box_count", default=0)
    enable_box_value = _resolve_live_int(variables, "enable_box", default=0)
    if box_count_value <= 0 or enable_box_value != 0:
        return None
    return BoxEnablementOpportunity(
        saved_variables_path=paths.config_root / "saved_variables.cfg",
        box_count=box_count_value,
        enable_box=enable_box_value,
    )


def detect_required_tool_slot_opportunity(
    paths: RuntimePaths, *, urlopen: UrlOpenFn = urllib.request.urlopen
) -> RequiredToolSlotOpportunity | None:
    if not _box_stack_available(paths, urlopen=urlopen):
        return None
    variables = read_live_saved_variables(paths, urlopen=urlopen)
    box_count = _resolve_live_int(variables, "box_count", default=0)
    gaps = collect_required_tool_slot_gaps_from_variables(variables)
    if not gaps:
        return None
    return RequiredToolSlotOpportunity(
        saved_variables_path=paths.config_root / "saved_variables.cfg",
        box_count=box_count,
        gaps=gaps,
    )


def detect_tool_slot_alignment_opportunity(
    paths: RuntimePaths, *, urlopen: UrlOpenFn = urllib.request.urlopen
) -> ToolSlotAlignmentOpportunity | None:
    variables = read_live_saved_variables(paths, urlopen=urlopen)
    mismatches = collect_tool_slot_mismatches_from_variables(variables)
    if not mismatches:
        return None
    return ToolSlotAlignmentOpportunity(
        saved_variables_path=paths.config_root / "saved_variables.cfg",
        mismatches=mismatches,
    )


def read_live_saved_variables(
    paths: RuntimePaths, *, urlopen: UrlOpenFn = urllib.request.urlopen
) -> dict[str, str]:
    variables: dict[str, str] = {}
    for name, value in _read_live_saved_variables_raw(paths, urlopen=urlopen).items():
        if isinstance(name, str) and isinstance(value, (str, int, float, bool)):
            variables[name] = str(value)
    return variables


def read_live_saved_variable_names(
    paths: RuntimePaths, *, urlopen: UrlOpenFn = urllib.request.urlopen
) -> frozenset[str]:
    """Return every saved variable name, including those saved as None."""
    return frozenset(
        name for name in _read_live_saved_variables_raw(paths, urlopen=urlopen)
        if isinstance(name, str)
    )


def _read_live_saved_variables_raw(
    paths: RuntimePaths, *, urlopen: UrlOpenFn
) -> Mapping:
    try:
        _, state = read_printer_info(paths.moonraker_url, urlopen=urlopen)
    except ProcessRestartError as exc:
        raise SavedVariablePersistenceError("Klipper saved-variable runtime is unavailable.") from exc
    if state != "ready":
        raise SavedVariablePersistenceError("Klipper saved-variable runtime is not ready.")
    request_url = _moonraker_objects_url(paths.moonraker_url, "save_variables")
    try:
        with urlopen(request_url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        raw = payload["result"]["status"]["save_variables"]["variables"]
    except (OSError, urllib.error.URLError, KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SavedVariablePersistenceError("Could not read Klipper saved variables.") from exc
    if not isinstance(raw, Mapping):
        raise SavedVariablePersistenceError("Moonraker returned invalid saved variables.")
    return raw


def save_live_variables(
    paths: RuntimePaths,
    values: Mapping[str, str],
    *,
    missing_only: frozenset[str] = frozenset(),
    missing_or_empty: frozenset[str] = frozenset(),
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> dict[str, str]:
    if not values:
        return {}
    if missing_only & missing_or_empty or not (missing_only | missing_or_empty) <= values.keys():
        raise ValueError("Saved-variable eligibility is invalid.")
    _validate_saved_values(values)
    # Read immediately before writing so values are sourced from Klipper memory,
    # not a potentially stale saved_variables.cfg snapshot.
    live = read_live_saved_variables(paths, urlopen=urlopen)
    pending = {}
    for name, value in values.items():
        current = live.get(name)
        if name in missing_only:
            if current is not None:
                continue
        elif name in missing_or_empty:
            if _normalize_saved_string(current or ""):
                continue
        elif _normalize_saved_string(current or "") == _normalize_saved_string(value):
            continue
        pending[name] = value
    for name, value in pending.items():
        _post_save_variable(paths, name, value, urlopen=urlopen)
    if pending:
        _verify_saved_values(paths, pending, urlopen=urlopen)
    return pending


def _post_save_variable(paths: RuntimePaths, name: str, value: str, *, urlopen: UrlOpenFn) -> None:
    request = urllib.request.Request(
        _moonraker_gcode_url(paths.moonraker_url),
        # Preserve the Python literal through Klipper's shell-style argument parser.
        data=json.dumps({"script": f"SAVE_VARIABLE VARIABLE={name} VALUE={shlex.quote(value)}"}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            response.read()
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise SavedVariablePersistenceError(f"Could not save Klipper variable {name}.") from exc


def _verify_saved_values(paths: RuntimePaths, values: Mapping[str, str], *, urlopen: UrlOpenFn) -> None:
    live = read_live_saved_variables(paths, urlopen=urlopen)
    if any(
        _normalize_saved_string(live.get(name, "")) != _normalize_saved_string(value)
        for name, value in values.items()
    ):
        raise SavedVariablePersistenceError("Klipper did not retain saved-variable updates.")
    # `SAVE_VARIABLE` is Klipper's persistence operation. A subsequent live
    # query confirms the command completed; a verified replacement process
    # confirms the same values survive the source-patch restart path.


def _validate_saved_values(values: Mapping[str, str]) -> None:
    for name, value in values.items():
        if not SAVED_VARIABLE_NAME_RE.fullmatch(name):
            raise SavedVariablePersistenceError("Saved-variable name is invalid.")
        if not isinstance(value, str) or not value or len(value) > MAX_SAVED_VARIABLE_VALUE_LENGTH:
            raise SavedVariablePersistenceError("Saved-variable value is invalid.")
        # 0/1 flags, quoted slot names, and whole-number Box motion settings.
        if (
            value not in {"0", "1"}
            and not re.fullmatch(r"'(?:slot(?:[0-9]|1[0-5]))'", value)
            and not re.fullmatch(r"[1-9][0-9]{0,3}", value)
        ):
            raise SavedVariablePersistenceError("Saved-variable value is not authorized.")


def _moonraker_objects_url(moonraker_url: str, object_name: str) -> str:
    parts = urllib.parse.urlsplit(moonraker_url)
    prefix = parts.path.removesuffix("/printer/objects/query")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, f"{prefix}/printer/objects/query", object_name, ""))


def _moonraker_gcode_url(moonraker_url: str) -> str:
    parts = urllib.parse.urlsplit(moonraker_url)
    prefix = parts.path.removesuffix("/printer/objects/query")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, f"{prefix}/printer/gcode/script", "", ""))


def collect_required_tool_slot_gaps_from_variables(
    variables: Mapping[str, str],
) -> tuple[RequiredToolSlotGap, ...]:
    box_count = _resolve_live_int(variables, "box_count", default=0)
    gaps = []
    for tool in range(_required_tool_count(box_count)):
        variable = f"value_t{tool}"
        current = _normalize_saved_string(variables.get(variable, ""))
        if not current:
            gaps.append(RequiredToolSlotGap(tool, variable, "<missing>" if variable not in variables else "<empty>", f"slot{tool}"))
    return tuple(gaps)


def collect_tool_slot_mismatches_from_variables(
    variables: Mapping[str, str],
) -> tuple[ToolSlotMismatch, ...]:
    mismatches = []
    for variable, value in variables.items():
        match = VALUE_T_RE.match(variable)
        if match is None:
            continue
        tool = int(match.group("tool"))
        current = _normalize_saved_string(value)
        expected = f"slot{tool}"
        if current != expected:
            mismatches.append(ToolSlotMismatch(tool, variable, current or "<empty>", expected))
    return tuple(sorted(mismatches, key=lambda mismatch: mismatch.tool))


# Text helpers remain for offline configuration analysis and legacy tests; live
# installer paths intentionally use the Moonraker helpers above.
def collect_required_tool_slot_gaps(text: str) -> tuple[RequiredToolSlotGap, ...]:
    variables = _variables_from_text(text)
    return collect_required_tool_slot_gaps_from_variables(variables)


def collect_tool_slot_mismatches(text: str) -> tuple[ToolSlotMismatch, ...]:
    return collect_tool_slot_mismatches_from_variables(_variables_from_text(text))


def _variables_from_text(text: str) -> dict[str, str]:
    section = klipper_cfg.resolve_unique_section(text, "Variables")
    values = {}
    for line in text.splitlines(keepends=True)[section.header_index + 1 : section.end_index]:
        parsed = klipper_cfg.parse_option_line(line)
        if parsed is not None:
            values[parsed.key] = parsed.value
    return values


def _required_tool_count(box_count: int) -> int:
    return max(0, min(16, box_count * 4))


def _box_extras_configured(path: Path) -> bool:
    try:
        return klipper_cfg.has_section(klipper_cfg.read_text(path), "box_extras")
    except OSError:
        return False


def _box_stack_available(paths: RuntimePaths, *, urlopen: UrlOpenFn) -> bool:
    # Legacy USB Boxes are configured in box.cfg. The flow controller that
    # registers T_MANAGER always loads its Box objects, so only a live Box count
    # proves an attached Box there; this also covers RS-485 Boxes without box.cfg.
    if _box_extras_configured(paths.config_root / "box.cfg"):
        return True
    request_url = _moonraker_objects_url(
        paths.moonraker_url, "gcode=commands&multi_color_controller=box_count&box485=box_count"
    )
    try:
        with urlopen(request_url, timeout=10) as response:
            status = json.loads(response.read().decode("utf-8"))["result"]["status"]
        if "T_MANAGER" not in status["gcode"]["commands"]:
            return False
        counts = (
            status.get(name, {}).get("box_count", 0) for name in ("multi_color_controller", "box485")
        )
        return any((_coerce_optional_int(count) or 0) > 0 for count in counts)
    except (OSError, urllib.error.URLError, KeyError, TypeError, ValueError, AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return False


def _read_runtime_state(paths: RuntimePaths) -> dict[str, object]:
    path = paths.printer_data_root / RUNTIME_STATE_FILE
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_runtime_state(paths: RuntimePaths, state: dict[str, object]) -> None:
    from .fs_atomic import atomic_write_text

    path = paths.printer_data_root / RUNTIME_STATE_FILE
    atomic_write_text(path, json.dumps(state, sort_keys=True, indent=2) + "\n", mode=0o644)


def _resolve_live_int(variables: Mapping[str, str], name: str, *, default: int) -> int:
    if name not in variables:
        return default
    return _coerce_saved_int(variables[name])


def _coerce_optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _coerce_saved_int(value: str) -> int:
    normalized = _normalize_saved_string(value).lower()
    if normalized == "true":
        return 1
    if normalized in {"false", "none", ""}:
        return 0
    return int(normalized)


def _normalize_saved_string(value: str) -> str:
    return value.strip().strip("'\"")


def _quote_saved_string(value: str) -> str:
    return f"'{value}'"
