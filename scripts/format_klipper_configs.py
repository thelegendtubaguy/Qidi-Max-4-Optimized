#!/usr/bin/env python3

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path


SECTION_RE = re.compile(r"^\[[^\]]+\]\s*(?:#.*)?$")
ASSIGN_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_\-. ]*?)\s*([:=])\s*(.*?)\s*$")
SAVE_CONFIG_MARKER = "#*# <---------------------- SAVE_CONFIG ---------------------->"
DEFAULT_EXCLUDES = {"fluidd.cfg", "saved_variables.cfg"}
FORMAT_DIR = Path("installer") / "klipper" / "tltg-optimized-macros"


def normalize_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    prev_blank = False

    for raw in lines:
        line = raw.rstrip(" \t").replace("\t", "  ")
        stripped = line.strip()

        if stripped == "":
            if out and not prev_blank:
                out.append("")
            prev_blank = True
            continue

        unindented = line == stripped

        if unindented and SECTION_RE.match(line):
            if out and out[-1] != "":
                out.append("")
            out.append(line)
            prev_blank = False
            continue

        if unindented and not stripped.startswith("#"):
            match = ASSIGN_RE.match(line)
            if match:
                key, sep, value = match.groups()
                key = key.strip()
                value = value.strip()
                if sep == ":":
                    line = f"{key}: {value}" if value else f"{key}:"
                else:
                    line = f"{key} = {value}" if value else f"{key} ="

        out.append(line)
        prev_blank = False

    while out and out[-1] == "":
        out.pop()

    return out


def format_text(text: str) -> str:
    lines = text.splitlines()
    save_index = next(
        (i for i, line in enumerate(lines) if line.startswith(SAVE_CONFIG_MARKER)), None
    )

    main_lines = lines if save_index is None else lines[:save_index]
    save_lines = [] if save_index is None else lines[save_index:]

    formatted = normalize_lines(main_lines)
    if save_lines:
        if formatted and formatted[-1] != "":
            formatted.append("")
        formatted.extend(line.rstrip("\r") for line in save_lines)

    return "\n".join(formatted) + "\n"


def iter_cfg_files(root: Path) -> list[Path]:
    config_dir = root / FORMAT_DIR
    return sorted(
        path for path in config_dir.rglob("*.cfg") if path.name not in DEFAULT_EXCLUDES
    )


def diff_text(path: Path, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Format TLTG optimized Klipper config files in this repo."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional config files or directories to format. Defaults to installer/klipper/tltg-optimized-macros/**/*.cfg.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report files that would change without writing them.",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Print unified diffs for files that would change.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    format_root = (repo_root / FORMAT_DIR).resolve()

    if args.paths:
        candidates: list[Path] = []
        for raw_path in args.paths:
            path = (
                (Path.cwd() / raw_path).resolve()
                if not raw_path.is_absolute()
                else raw_path.resolve()
            )
            if path.is_dir():
                candidates.extend(sorted(path.rglob("*.cfg")))
            elif path.suffix == ".cfg":
                candidates.append(path)
        files = sorted(
            {
                path
                for path in candidates
                if path.name not in DEFAULT_EXCLUDES
                and (path == format_root or format_root in path.parents)
            }
        )
    else:
        files = iter_cfg_files(repo_root)

    changed: list[Path] = []

    for path in files:
        before = path.read_text()
        after = format_text(before)
        if before == after:
            continue
        changed.append(path)
        if args.diff:
            sys.stdout.write(diff_text(path, before, after))
        if not args.check:
            path.write_text(after)

    if args.check:
        for path in changed:
            print(path)
        return 1 if changed else 0

    if changed:
        for path in changed:
            print(path)
    else:
        print("No formatting changes needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
