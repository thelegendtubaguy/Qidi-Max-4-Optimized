from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import klipper_cfg, messages
from .fs_atomic import atomic_write_text
from .interaction import confirm_yes
from .models import RuntimePaths

VALUE_T_RE = re.compile(r"^value_t(?P<tool>\d+)$")


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
class ToolSlotAlignmentOpportunity:
    saved_variables_path: Path
    mismatches: tuple[ToolSlotMismatch, ...]


def maybe_prompt_enable_box(
    *,
    paths: RuntimePaths,
    reporter,
    input_stream,
    journal,
) -> bool:
    opportunity = detect_box_enablement_opportunity(paths)
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

    text = klipper_cfg.read_text(opportunity.saved_variables_path)
    new_text = set_saved_variable(text, "enable_box", "1")
    if new_text != text:
        journal.note_write()
        atomic_write_text(opportunity.saved_variables_path, new_text)
    reporter.line(messages.ENABLE_QIDI_BOX_ENABLED)
    return True


def maybe_prompt_align_tool_slots(
    *,
    paths: RuntimePaths,
    reporter,
    input_stream,
    journal,
) -> bool:
    opportunity = detect_tool_slot_alignment_opportunity(paths)
    if opportunity is None:
        reporter.debug(event="tool_slot_alignment.skipped")
        return False

    reporter.debug(
        event="tool_slot_alignment.detected",
        mismatches=len(opportunity.mismatches),
        saved_variables_path=opportunity.saved_variables_path,
    )
    if input_stream is not None:
        reporter.prepare_for_prompt()
        reporter.line(messages.TOOL_SLOT_MAPPING_MISMATCH_HEADER)
        for mismatch in opportunity.mismatches:
            reporter.line(
                f"  - {mismatch.variable}: {mismatch.current} -> {mismatch.expected}"
            )
    if not confirm_yes(
        reporter=reporter,
        input_stream=input_stream,
        question=messages.TOOL_SLOT_MAPPING_PROMPT,
        instruction=messages.TOOL_SLOT_MAPPING_PROMPT_INSTRUCTION,
        cancel_message=messages.TOOL_SLOT_MAPPING_DECLINED,
    ):
        return False

    text = klipper_cfg.read_text(opportunity.saved_variables_path)
    new_text = align_tool_slot_variables(text, opportunity.mismatches)
    if new_text != text:
        journal.note_write()
        atomic_write_text(opportunity.saved_variables_path, new_text)
    reporter.line(messages.TOOL_SLOT_MAPPING_CORRECTED)
    return True


def detect_box_enablement_opportunity(paths: RuntimePaths) -> BoxEnablementOpportunity | None:
    saved_variables_path = paths.config_root / "saved_variables.cfg"
    if not saved_variables_path.exists():
        return None
    if not _box_extras_configured(paths.config_root / "box.cfg"):
        return None

    try:
        text = klipper_cfg.read_text(saved_variables_path)
        box_count_value = _resolve_saved_int(text, "box_count", default=0)
        enable_box_value = _resolve_saved_int(text, "enable_box", default=0)
    except (OSError, klipper_cfg.TargetResolutionError, ValueError):
        return None

    if box_count_value <= 0 or enable_box_value != 0:
        return None
    return BoxEnablementOpportunity(
        saved_variables_path=saved_variables_path,
        box_count=box_count_value,
        enable_box=enable_box_value,
    )


def detect_tool_slot_alignment_opportunity(
    paths: RuntimePaths,
) -> ToolSlotAlignmentOpportunity | None:
    saved_variables_path = paths.config_root / "saved_variables.cfg"
    if not saved_variables_path.exists():
        return None
    try:
        text = klipper_cfg.read_text(saved_variables_path)
        mismatches = collect_tool_slot_mismatches(text)
    except (OSError, klipper_cfg.TargetResolutionError):
        return None
    if not mismatches:
        return None
    return ToolSlotAlignmentOpportunity(
        saved_variables_path=saved_variables_path,
        mismatches=mismatches,
    )


def collect_tool_slot_mismatches(text: str) -> tuple[ToolSlotMismatch, ...]:
    lines = text.splitlines(keepends=True)
    section = klipper_cfg.resolve_unique_section(text, "Variables")
    value_t_tools: dict[int, tuple[str, str]] = {}
    duplicate_tools: set[int] = set()
    for line_index in range(section.header_index + 1, section.end_index):
        parsed = klipper_cfg.parse_option_line(lines[line_index])
        if parsed is None:
            continue
        match = VALUE_T_RE.match(parsed.key)
        if match is None:
            continue
        tool = int(match.group("tool"))
        if tool in value_t_tools:
            duplicate_tools.add(tool)
            continue
        value_t_tools[tool] = (parsed.key, _normalize_saved_string(parsed.value))
    if duplicate_tools:
        return ()

    mismatches = []
    for tool, (variable, current) in sorted(value_t_tools.items()):
        expected = f"slot{tool}"
        if current != expected:
            mismatches.append(
                ToolSlotMismatch(
                    tool=tool,
                    variable=variable,
                    current=current,
                    expected=expected,
                )
            )
    return tuple(mismatches)


def align_tool_slot_variables(text: str, mismatches: tuple[ToolSlotMismatch, ...]) -> str:
    new_text = text
    for mismatch in mismatches:
        new_text = set_saved_variable(new_text, mismatch.variable, f"'{mismatch.expected}'")
    return new_text


def set_saved_variable(text: str, name: str, value: str) -> str:
    try:
        return klipper_cfg.set_option_value(text, "Variables", name, value)
    except klipper_cfg.TargetResolutionError as exc:
        if exc.reason != "missing":
            raise
    section = klipper_cfg.resolve_unique_section(text, "Variables")
    lines = text.splitlines(keepends=True)
    newline = _dominant_newline(lines)
    lines.insert(section.end_index, f"{name} = {value}{newline}")
    return "".join(lines)


def _box_extras_configured(path: Path) -> bool:
    try:
        return klipper_cfg.has_section(klipper_cfg.read_text(path), "box_extras")
    except OSError:
        return False


def _resolve_saved_int(text: str, name: str, *, default: int) -> int:
    try:
        raw = klipper_cfg.resolve_unique_option(text, "Variables", name).value
    except klipper_cfg.TargetResolutionError as exc:
        if exc.reason == "missing":
            return default
        raise
    return _coerce_saved_int(raw)


def _coerce_saved_int(value: str) -> int:
    normalized = _normalize_saved_string(value).lower()
    if normalized == "true":
        return 1
    if normalized in {"false", "none", ""}:
        return 0
    return int(normalized)


def _normalize_saved_string(value: str) -> str:
    return value.strip().strip("'\"")


def _dominant_newline(lines: list[str]) -> str:
    for line in lines:
        if line.endswith("\r\n"):
            return "\r\n"
    return "\n"
