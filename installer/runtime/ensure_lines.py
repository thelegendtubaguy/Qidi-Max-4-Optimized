from __future__ import annotations

from typing import Iterable


COMMENT_PREFIXES = ("#", ";")


def has_active_line(text: str, wanted_line: str) -> bool:
    wanted = wanted_line.strip()
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(COMMENT_PREFIXES):
            continue
        if stripped == wanted:
            return True
    return False


def ensure_line_after(text: str, line: str, after: str) -> str:
    lines = text.splitlines(keepends=True)
    newline = _detect_newline(lines)
    normalized_target = line.strip()
    normalized_after = after.strip()

    target_lines = [
        index for index, raw in enumerate(lines) if _is_active_line(raw, normalized_target)
    ]
    anchor_lines = [
        index for index, raw in enumerate(lines) if _is_active_line(raw, normalized_after)
    ]
    if not anchor_lines:
        raise ValueError(f"Anchor line not found: {after}")

    for index in reversed(target_lines):
        del lines[index]

    anchor_index = None
    for index, raw in enumerate(lines):
        if _is_active_line(raw, normalized_after):
            anchor_index = index
            break
    if anchor_index is None:
        raise ValueError(f"Anchor line not found after reconciliation: {after}")

    insert_at = anchor_index + 1
    lines.insert(insert_at, line.rstrip("\r\n") + newline)
    return "".join(lines)


def remove_active_line(text: str, line: str) -> str:
    normalized_target = line.strip()
    lines = [
        raw for raw in text.splitlines(keepends=True) if not _is_active_line(raw, normalized_target)
    ]
    return "".join(lines)


def _is_active_line(raw_line: str, normalized_target: str) -> bool:
    stripped = raw_line.strip()
    return bool(stripped) and not stripped.startswith(COMMENT_PREFIXES) and stripped == normalized_target


def _detect_newline(lines: Iterable[str]) -> str:
    for line in lines:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
    return "\n"
