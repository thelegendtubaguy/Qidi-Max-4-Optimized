from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import messages
from .backup import create_config_backup, format_backup_timestamp, utc_now
from .errors import InstallerError, OperationCancelled
from .fs_atomic import atomic_write_bytes
from .interaction import confirm_yes
from .mirror import mirror_tree, remove_tree, validate_managed_tree_source
from .models import Manifest, RuntimePaths
from .path_safety import ensure_runtime_path_has_no_symlink_components, ensure_runtime_tree_has_no_symlinks
from .rollback import RollbackJournal
from .sudo import SudoError, authenticate_sudo, run_sudo_or_raise

LEGACY_RESET_FIRMWARE_TOKEN = "legacy-manual-reset"
QIDICLIENT_SERVICE = "qidi-client.service"
STOCK_CONFIG_SOURCE = Path("stock/qidi-max4-defaults/config")
LEGACY_MARKERS = (
    ("config/printer.cfg", "[include tltg-optimized-macros/*.cfg]"),
    ("config/klipper-macros-qd/filament.cfg", "[gcode_macro OPTIMIZED_CUT_FILAMENT]"),
    ("config/klipper-macros-qd/filament.cfg", "[gcode_macro OPTIMIZED_START_PRINT_FILAMENT_PREP]"),
    ("config/klipper-macros-qd/start_end.cfg", "[gcode_macro OPTIMIZED_PRINT_START_HOME]"),
    ("config/klipper-macros-qd/kinematics.cfg", "[gcode_macro _move_to_z_home_point]"),
    ("config/klipper-macros-qd/globals.cfg", "variable_z_home_randomize_radius"),
)
PRESERVED_CONFIG_PATHS = (
    "config/MCU_ID.cfg",
    "config/box.cfg",
    "config/fluidd.cfg",
    "config/saved_variables.cfg",
)
REMOVED_LEGACY_PATHS = ("config/tltg-optimized-macros",)


class LegacyManualInstallError(InstallerError):
    pass


@dataclass(frozen=True)
class LegacyManualMarker:
    path: str
    needle: str


@dataclass(frozen=True)
class LegacyManualInstallReport:
    markers: tuple[LegacyManualMarker, ...]
    legacy_paths: tuple[str, ...]

    @property
    def detected_paths(self) -> tuple[str, ...]:
        return tuple(sorted({marker.path for marker in self.markers} | set(self.legacy_paths)))


def maybe_reset_legacy_manual_install(
    *,
    paths: RuntimePaths,
    manifest: Manifest,
    reporter,
    input_stream,
    environ: dict[str, str],
    detected_firmware: str,
    dry_run: bool = False,
    run=None,
) -> LegacyManualInstallReport | None:
    run = subprocess.run if run is None else run
    report = detect_legacy_manual_install(paths=paths, manifest=manifest)
    if report is None:
        return None

    reporter.debug(
        event="install.legacy_manual.detected",
        paths=", ".join(report.detected_paths),
        dry_run=dry_run,
    )
    if dry_run:
        reporter.line(messages.LEGACY_MANUAL_INSTALL_DRY_RUN)
        return report

    if not confirm_yes(
        reporter=reporter,
        input_stream=input_stream,
        question=messages.LEGACY_MANUAL_INSTALL_PROMPT,
        instruction=messages.LEGACY_MANUAL_INSTALL_PROMPT_INSTRUCTION,
        cancel_message=messages.LEGACY_MANUAL_INSTALL_CANCELLED,
    ):
        raise OperationCancelled(messages.LEGACY_MANUAL_INSTALL_CANCELLED)

    backup_path = _backup_legacy_config(
        paths=paths,
        manifest=manifest,
        detected_firmware=detected_firmware,
    )
    reporter.line(f"{messages.LEGACY_MANUAL_INSTALL_BACKUP_CREATED} {backup_path}")
    _restore_stock_config(paths=paths, manifest=manifest, reporter=reporter, backup_path=backup_path)
    _restart_qidiclient(reporter=reporter, input_stream=input_stream, environ=environ, run=run)
    reporter.line(messages.LEGACY_MANUAL_INSTALL_RESET_COMPLETE)
    reporter.debug(
        event="install.legacy_manual.reset_complete",
        backup_zip_path=backup_path,
    )
    return report


def detect_legacy_manual_install(
    *,
    paths: RuntimePaths,
    manifest: Manifest,
) -> LegacyManualInstallReport | None:
    if (paths.printer_data_root / manifest.state_file).exists():
        return None

    markers = []
    for rel_path, needle in LEGACY_MARKERS:
        path = paths.printer_data_root / rel_path
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if needle in text:
            markers.append(LegacyManualMarker(path=rel_path, needle=needle))

    legacy_paths = tuple(
        rel_path
        for rel_path in REMOVED_LEGACY_PATHS
        if (paths.printer_data_root / rel_path).exists()
    )
    if not markers and not legacy_paths:
        return None
    return LegacyManualInstallReport(markers=tuple(markers), legacy_paths=legacy_paths)


def _backup_legacy_config(*, paths: RuntimePaths, manifest: Manifest, detected_firmware: str) -> Path:
    moment = utc_now()
    label = (
        f"{manifest.backup.label_prefix}-{LEGACY_RESET_FIRMWARE_TOKEN}-"
        f"{detected_firmware}-{manifest.package.version}-{format_backup_timestamp(moment)}"
    )
    return create_config_backup(
        printer_data_root=paths.printer_data_root,
        source_directory=manifest.backup.source_directory,
        backup_label=label,
    )


def _restore_stock_config(*, paths: RuntimePaths, manifest: Manifest, reporter, backup_path: Path) -> None:
    source_root = paths.installer_root / STOCK_CONFIG_SOURCE
    if not source_root.exists():
        raise LegacyManualInstallError(f"Bundled stock config snapshot is missing: {source_root}")
    validate_managed_tree_source(source_root)
    journal = RollbackJournal(
        paths.recovery_sentinel_path,
        printer_data_root=paths.printer_data_root,
        source_directory=manifest.backup.source_directory,
    )
    try:
        _restore_stock_files(source_root=source_root, paths=paths, journal=journal)
    except Exception as exc:
        if journal.write_started:
            journal.rollback_or_raise(
                exc,
                backup_label=backup_path.stem,
                backup_zip_path=backup_path,
            )
        raise


def _restore_stock_files(*, source_root: Path, paths: RuntimePaths, journal: RollbackJournal) -> None:
    config_root = paths.printer_data_root / "config"
    for legacy_path in REMOVED_LEGACY_PATHS:
        target = paths.printer_data_root / legacy_path
        ensure_runtime_path_has_no_symlink_components(
            printer_data_root=paths.printer_data_root,
            target=target,
        )
        remove_tree(target, journal)

    for item in sorted(source_root.iterdir()):
        relative = item.relative_to(source_root)
        target = config_root / relative
        runtime_relative = target.relative_to(paths.printer_data_root).as_posix()
        if runtime_relative in PRESERVED_CONFIG_PATHS:
            continue
        ensure_runtime_path_has_no_symlink_components(
            printer_data_root=paths.printer_data_root,
            target=target,
        )
        if item.is_dir():
            ensure_runtime_tree_has_no_symlinks(target)
            mirror_tree(source_root=item, destination_root=target, journal=journal)
        elif item.is_file():
            journal.track_file(target)
            data = item.read_bytes()
            if target.exists() and target.is_file() and target.read_bytes() == data:
                continue
            journal.note_write()
            atomic_write_bytes(target, data, mode=0o644)


def _restart_qidiclient(*, reporter, input_stream, environ: dict[str, str], run) -> None:
    if shutil.which("systemctl") is None:
        raise LegacyManualInstallError(messages.LEGACY_MANUAL_QIDICLIENT_RESTART_FAILED)
    if shutil.which("sudo") is None:
        raise LegacyManualInstallError(messages.AUTO_UPDATE_SUDO_MISSING)
    try:
        sudo_password = authenticate_sudo(
            run=run,
            environ=environ,
            reporter=reporter,
            input_stream=input_stream,
        )
        run_sudo_or_raise(
            ["systemctl", "restart", QIDICLIENT_SERVICE],
            messages.LEGACY_MANUAL_QIDICLIENT_RESTART_FAILED,
            run=run,
            password=sudo_password,
        )
    except SudoError as exc:
        raise LegacyManualInstallError(exc.message) from exc
    reporter.line(messages.LEGACY_MANUAL_QIDICLIENT_RESTARTED)
