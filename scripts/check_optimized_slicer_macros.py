#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "config"
OPTIMIZED_SLICER_DIRS = [
    REPO_ROOT / "orcaslicer_gcode",
    REPO_ROOT / "qidistudio_gcode",
]

GCODE_MACRO_RE = re.compile(r"^\[gcode_macro\s+([^\]]+)\]\s*$", re.IGNORECASE)
COMMAND_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)(?=$|[\s\[])")
CONTROL_BLOCK_RE = re.compile(r"\{(?:if|else|elsif|endif)\b[^}]*\}", re.IGNORECASE)
NUMERIC_SUFFIX_RE = re.compile(r"^(.*?)(\d+)$")

ALLOWED_NON_MACRO_COMMANDS = {
    "DISABLE_BOX_HEATER",
    "G0",
    "G1",
    "G2",
    "G4",
    "G90",
    "G92",
    "M82",
    "M83",
    "M106",
    "M107",
    "M204",
    "M220",
    "M221",
    "M400",
    "SET_INPUT_SHAPER",
    "SET_PRINT_MAIN_STATUS",
    "TOOL_CHANGE_END",
    "TOOL_CHANGE_START",
}


def iter_macro_names() -> set[str]:
    macros: set[str] = set()
    for path in sorted(CONFIG_DIR.rglob("*.cfg")):
        for line in path.read_text().splitlines():
            match = GCODE_MACRO_RE.match(line.strip())
            if match:
                macros.add(match.group(1).strip().upper())
    return macros


def build_dynamic_prefixes(macros: set[str]) -> set[str]:
    prefixes: set[str] = set()
    for macro in macros:
        match = NUMERIC_SUFFIX_RE.match(macro)
        if match and match.group(1):
            prefixes.add(match.group(1))
    return prefixes


def iter_slicer_files() -> list[Path]:
    files: list[Path] = []
    for directory in OPTIMIZED_SLICER_DIRS:
        files.extend(sorted(directory.glob("*.gcode")))
    return files


def iter_commands(path: Path):
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.split(";", 1)[0]
        if not line.strip():
            continue
        for segment in CONTROL_BLOCK_RE.split(line):
            segment = segment.strip()
            if not segment:
                continue
            match = COMMAND_RE.match(segment)
            if match:
                yield line_number, match.group(1).upper(), segment, match.end(1)


def is_dynamic_macro_call(
    command: str, segment: str, command_end: int, dynamic_prefixes: set[str]
) -> bool:
    return command in dynamic_prefixes and segment[command_end:].lstrip().startswith(
        "["
    )


def main() -> int:
    macros = iter_macro_names()
    dynamic_prefixes = build_dynamic_prefixes(macros)
    failures: list[str] = []
    checked_files = iter_slicer_files()

    for path in checked_files:
        for line_number, command, segment, command_end in iter_commands(path):
            if command in macros:
                continue
            if is_dynamic_macro_call(command, segment, command_end, dynamic_prefixes):
                continue
            if command in ALLOWED_NON_MACRO_COMMANDS:
                continue
            failures.append(
                f"{path.relative_to(REPO_ROOT)}:{line_number}: unknown command '{command}' in '{segment}'"
            )

    if failures:
        print("Optimized slicer G-code references unknown commands:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print(
        f"Validated {len(checked_files)} optimized slicer G-code files against {len(macros)} repo macros."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
