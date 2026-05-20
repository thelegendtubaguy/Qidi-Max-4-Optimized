from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TextIO

from .backup import (
    format_backup_display_timestamp,
    list_installer_backups,
    parse_installer_backup_archive,
    restore_backup_snapshot,
    snapshot_runtime_tree,
    describe_snapshot_difference,
)
from .models import Manifest, RuntimePaths


CONFIRMATION_TOKEN = "RESTORE"
DebugFn = Callable[..., None]


@dataclass(frozen=True)
class BackupSelection:
    path: Path
    label: str
    display_created_at: str


class RestoreHelperError(ValueError):
    pass


def run_restore_helper(
    paths: RuntimePaths,
    manifest: Manifest,
    *,
    stream: TextIO | None = None,
    input_stream: TextIO,
    backup_path: str | None = None,
    debug: DebugFn | None = None,
    reporter=None,
) -> int:
    if reporter is None:
        from .reporter import PlainReporter

        reporter = PlainReporter(stream)
    debug = debug or getattr(reporter, "debug", _noop_debug)
    selection = _resolve_backup_selection(
        printer_data_root=paths.printer_data_root,
        install_label_prefix=manifest.backup.label_prefix,
        backup_path=backup_path,
        reporter=reporter,
        input_stream=input_stream,
        debug=debug,
    )
    if selection is None:
        return 0

    reporter.emit_restore_selection(label=selection.label, path=str(selection.path))
    reporter.emit_restore_warning(
        config_path=str(paths.printer_data_root / manifest.backup.source_directory)
    )
    reporter.line(f"Type {CONFIRMATION_TOKEN} to continue:")
    confirmation = input_stream.readline().strip()
    if confirmation != CONFIRMATION_TOKEN:
        reporter.line()
        reporter.line("Restore cancelled.")
        return 0
    reporter.line()

    debug(
        event="restore.selection.confirmed",
        backup_path=selection.path,
        source_directory=manifest.backup.source_directory,
    )
    backup_snapshot = restore_backup_snapshot(
        backup_zip_path=selection.path,
        printer_data_root=paths.printer_data_root,
        source_directory=manifest.backup.source_directory,
    )
    runtime_snapshot = snapshot_runtime_tree(
        printer_data_root=paths.printer_data_root,
        source_directory=manifest.backup.source_directory,
    )
    if runtime_snapshot != backup_snapshot:
        raise RestoreHelperError(
            "Restore verification failed. "
            + describe_snapshot_difference(runtime_snapshot, backup_snapshot)
        )

    debug(
        event="restore.completed",
        backup_path=selection.path,
        restored_files=len(backup_snapshot),
    )
    reporter.emit_restore_complete(
        verified_path=str(paths.printer_data_root / manifest.backup.source_directory)
    )
    return 0


def _resolve_backup_selection(
    *,
    printer_data_root: Path,
    install_label_prefix: str,
    backup_path: str | None,
    reporter,
    input_stream: TextIO,
    debug: DebugFn,
) -> BackupSelection | None:
    if backup_path is not None:
        resolved_path = _resolve_backup_path(backup_path)
        if not resolved_path.exists() or not resolved_path.is_file():
            raise RestoreHelperError(f"Backup zip was not found: {resolved_path}")
        selection = _selection_from_path(
            resolved_path,
            install_label_prefix=install_label_prefix,
        )
        debug(event="restore.selection.direct", backup_path=selection.path)
        return selection

    backups = list_installer_backups(
        printer_data_root,
        install_label_prefix=install_label_prefix,
    )
    if not backups:
        reporter.line(f"No installer backups were found under {printer_data_root}.")
        return None

    ordered_backups = tuple(reversed(backups))
    reporter.emit_backup_choices(
        tuple(
            (index, archive.display_created_at, archive.label, str(archive.path))
            for index, archive in enumerate(ordered_backups, start=1)
        )
    )

    while True:
        reporter.line("Select a backup number to restore, or q to cancel:")
        raw_choice = input_stream.readline().strip()
        if not raw_choice:
            reporter.line()
            continue
        if raw_choice.lower() in {"q", "quit"}:
            reporter.line()
            reporter.line("Restore cancelled.")
            return None
        try:
            selection_index = int(raw_choice)
        except ValueError:
            reporter.line()
            reporter.line("Enter a listed backup number or q.")
            continue
        if 1 <= selection_index <= len(ordered_backups):
            reporter.line()
            archive = ordered_backups[selection_index - 1]
            selection = BackupSelection(
                path=archive.path,
                label=archive.label,
                display_created_at=archive.display_created_at,
            )
            debug(event="restore.selection.menu", backup_path=selection.path)
            return selection
        reporter.line()
        reporter.line("Enter a listed backup number or q.")


def _selection_from_path(path: Path, *, install_label_prefix: str) -> BackupSelection:
    parsed = parse_installer_backup_archive(path, install_label_prefix=install_label_prefix)
    if parsed is not None:
        return BackupSelection(
            path=path,
            label=parsed.label,
            display_created_at=parsed.display_created_at,
        )
    created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return BackupSelection(
        path=path,
        label=path.stem,
        display_created_at=format_backup_display_timestamp(created_at),
    )


def _resolve_backup_path(raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve()


def _noop_debug(**kwargs) -> None:
    return
