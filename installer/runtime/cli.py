from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

from .auto_update import AutoUpdateError, disable_auto_updates, enable_auto_updates, run_auto_update_check
from .backup import BackupArchiveError
from .compatibility import CompatibilityValidationError, load_supported_upgrade_sources, validate_manifest_compatibility
from .demo import resolve_demo_tui_delay_seconds, run_demo
from .errors import InstallerError, OperationCancelled
from .locking import acquire
from .manifest import ManifestValidationError, load_manifest
from .models import RuntimePaths
from .reporter import create_reporter
from .restore_helper import RestoreHelperError, run_restore_helper
from .rollback import clear_recovery_sentinel
from .runner import run_install
from .safety import ensure_no_recovery_sentinel
from .state_file import StateValidationError
from .uninstall import run_uninstall

DEFAULT_PRINTER_DATA_ROOT = Path("/home/qidi/printer_data")
DEFAULT_FIRMWARE_MANIFEST = Path("/home/qidi/update/firmware_manifest.json")
DEFAULT_MOONRAKER_URL = "http://127.0.0.1:7125/printer/objects/query?print_stats"



def main(
    argv: list[str] | None = None,
    *,
    stream=None,
    input_stream=None,
    bundle_root: Path | None = None,
    environ: dict[str, str] | None = None,
) -> int:
    args = parse_args(argv)
    env = dict(os.environ if environ is None else environ)
    bundle_root = bundle_root or Path(__file__).resolve().parents[2]
    reporter = create_reporter(
        stream,
        prefer_plain=args.plain or args.mode == "restore-backup",
        bundle_root=bundle_root,
        environ=env,
        debug=args.debug,
    )
    input_stream = None if args.yes else (input_stream or sys.stdin)
    paths = resolve_runtime_paths(bundle_root=bundle_root, environ=env)
    reporter.debug(
        event="cli.start",
        mode=args.mode,
        dry_run=args.dry_run,
        demo_tui=args.demo_tui,
        printer_data_root=paths.printer_data_root,
        bundle_root=bundle_root,
    )

    try:
        if args.demo_tui:
            delay_seconds = resolve_demo_tui_delay_seconds(environ=env)
            reporter.debug(
                event="cli.demo_tui.start",
                mode=args.mode,
                delay_seconds=delay_seconds,
            )
            run_demo(args.mode, reporter, delay_seconds=delay_seconds)
            reporter.debug(
                event="cli.complete",
                mode=args.mode,
                return_code=0,
                action="demo-tui",
            )
            return 0

        if args.mode == "auto-update-check":
            result = run_auto_update_check(paths=paths, reporter=reporter, environ=env)
            reporter.debug(
                event="cli.complete",
                mode=args.mode,
                return_code=0,
                action=result.action,
            )
            return 0

        if args.mode == "enable-auto-updates":
            enable_auto_updates(paths=paths, reporter=reporter, environ=env)
            reporter.debug(event="cli.complete", mode=args.mode, return_code=0)
            return 0

        if args.mode == "disable-auto-updates":
            disable_auto_updates(paths=paths, reporter=reporter)
            reporter.debug(event="cli.complete", mode=args.mode, return_code=0)
            return 0

        if args.mode == "clear-recovery-sentinel":
            with acquire(paths.lock_path):
                reporter.debug(
                    event="cli.lock.acquired",
                    mode=args.mode,
                    lock_path=paths.lock_path,
                )
                removed = clear_recovery_sentinel(
                    paths.recovery_sentinel_path,
                    printer_data_root=paths.printer_data_root,
                )
                reporter.emit_clear_recovery_sentinel(removed)
                reporter.debug(
                    event="cli.complete",
                    mode=args.mode,
                    removed=removed,
                )
                return 0

        manifest = load_manifest(paths.installer_root / "package.yaml")
        reporter.debug(
            event="cli.manifest.loaded",
            package_version=manifest.package.version,
            install_label_prefix=manifest.backup.label_prefix,
        )

        if args.mode == "restore-backup":
            with acquire(paths.lock_path):
                reporter.debug(
                    event="cli.lock.acquired",
                    mode=args.mode,
                    lock_path=paths.lock_path,
                )
                rc = run_restore_helper(
                    paths,
                    manifest,
                    stream=reporter.stream,
                    input_stream=input_stream,
                    backup_path=args.backup,
                    debug=reporter.debug,
                )
                reporter.debug(event="cli.complete", mode=args.mode, return_code=rc)
                return rc

        compatibility = load_supported_upgrade_sources(
            paths.installer_root / "supported_upgrade_sources.yaml"
        )
        validate_manifest_compatibility(manifest, compatibility)
        reporter.debug(
            event="cli.compatibility.validated",
            known_versions=len(manifest.package.known_versions),
        )

        with acquire(paths.lock_path):
            reporter.debug(
                event="cli.lock.acquired",
                mode=args.mode,
                lock_path=paths.lock_path,
            )
            ensure_no_recovery_sentinel(paths.recovery_sentinel_path)
            reporter.debug(
                event="cli.recovery_sentinel.clear",
                sentinel_path=paths.recovery_sentinel_path,
            )
            if args.mode == "install":
                run_install(
                    paths,
                    manifest,
                    reporter,
                    dry_run=args.dry_run,
                    input_stream=input_stream,
                    environ=env,
                )
            else:
                run_uninstall(
                    paths,
                    manifest,
                    compatibility,
                    reporter,
                    dry_run=args.dry_run,
                    input_stream=input_stream,
                )
        reporter.debug(event="cli.complete", mode=args.mode, return_code=0)
        return 0
    except OperationCancelled as exc:
        reporter.debug(
            event="cli.complete",
            mode=args.mode,
            return_code=0,
            action="cancelled",
        )
        return 0
    except (
        ManifestValidationError,
        CompatibilityValidationError,
        StateValidationError,
        BackupArchiveError,
        RestoreHelperError,
        AutoUpdateError,
    ) as exc:
        reporter.debug(
            event="cli.failure",
            mode=args.mode,
            error_type=type(exc).__name__,
            message=getattr(exc, "message", str(exc)),
        )
        reporter.emit_error(exc)
        if args.debug:
            traceback.print_exc(file=reporter.stream)
        return 1
    except InstallerError as exc:
        reporter.debug(
            event="cli.failure",
            mode=args.mode,
            error_type=type(exc).__name__,
            message=getattr(exc, "message", str(exc)),
        )
        reporter.emit_error(exc)
        if args.debug:
            traceback.print_exc(file=reporter.stream)
        return 1
    except Exception as exc:  # pragma: no cover - defensive fallback
        reporter.debug(
            event="cli.failure",
            mode=args.mode,
            error_type=type(exc).__name__,
            message=str(exc),
        )
        reporter.emit_error(exc)
        if args.debug:
            traceback.print_exc(file=reporter.stream)
        return 1



def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=[
            "install",
            "uninstall",
            "clear-recovery-sentinel",
            "restore-backup",
            "auto-update-check",
            "enable-auto-updates",
            "disable-auto-updates",
        ],
    )
    parser.add_argument("--plain", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--demo-tui", action="store_true")
    parser.add_argument("--backup")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run and args.mode not in {"install", "uninstall"}:
        parser.error("--dry-run is only supported with install and uninstall.")
    if args.demo_tui and args.mode not in {"install", "uninstall"}:
        parser.error("--demo-tui is only supported with install and uninstall.")
    if args.demo_tui and args.dry_run:
        parser.error("--demo-tui cannot be combined with --dry-run.")
    if args.backup and args.mode != "restore-backup":
        parser.error("--backup is only supported with restore-backup.")
    if args.yes and args.mode not in {"install", "uninstall", "auto-update-check"}:
        parser.error("--yes is only supported with install, uninstall, and auto-update-check.")
    return args



def resolve_runtime_paths(*, bundle_root: Path, environ: dict[str, str]) -> RuntimePaths:
    printer_data_root = Path(
        environ.get("TLTG_OPTIMIZED_PRINTER_DATA_ROOT", DEFAULT_PRINTER_DATA_ROOT)
    )
    firmware_manifest_path = Path(
        environ.get("TLTG_OPTIMIZED_FIRMWARE_MANIFEST", DEFAULT_FIRMWARE_MANIFEST)
    )
    moonraker_url = environ.get("TLTG_OPTIMIZED_MOONRAKER_URL", DEFAULT_MOONRAKER_URL)
    return RuntimePaths(
        bundle_root=bundle_root,
        installer_root=bundle_root / "installer",
        printer_data_root=printer_data_root,
        config_root=printer_data_root / "config",
        firmware_manifest_path=firmware_manifest_path,
        moonraker_url=moonraker_url,
        lock_path=printer_data_root / ".tltg_optimized_installer.lock",
        recovery_sentinel_path=printer_data_root / ".tltg_optimized_recovery_required",
        backup_root=printer_data_root,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
