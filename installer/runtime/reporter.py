from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from . import messages
from .errors import PreflightTargetsError, RollbackFailedError
from .models import DriftRecord, InstallPlan, PatchResult, PreflightReport, UninstallPlan
from .patches import (
    INSTALL_APPLIED,
    INSTALL_NOOP_DESIRED,
    UNINSTALL_NOOP_EXPECTED,
    UNINSTALL_REVERTED,
    USER_MODIFIED,
)
from .vendor_imports import (
    VendoredImportError,
    default_vendor_root,
    import_optional_vendored_module,
    vendor_root_from_bundle_root,
)


STATUS_STAGE_INDEX = {
    messages.CHECKING_FIRMWARE_VERSION: 1,
    messages.CHECKING_PACKAGE_VERSION: 2,
    messages.CHECKING_INSTALLED_PACKAGE: 2,
    messages.PERFORMING_PREFLIGHT_CHECKS: 3,
    messages.PERFORMING_UNINSTALL_PREFLIGHT_CHECKS: 3,
    messages.CREATING_BACKUP: 4,
    messages.INSTALLING: 5,
    messages.UNINSTALLING: 5,
}
STAGE_COUNT = 5


@dataclass(frozen=True)
class DetailGroup:
    heading: str
    rows: tuple[str, ...]


@dataclass(frozen=True)
class RichModules:
    Console: type
    Group: object
    Live: type
    Panel: type
    ProgressBar: type
    Table: type
    Text: type
    box: object


@dataclass
class ReporterState:
    stage_index: int | None = None
    current_status: str | None = None
    preflight_counters: dict[str, tuple[int, int]] = field(default_factory=dict)
    operation_counter_label: str | None = None
    operation_counters: dict[str, tuple[int, int]] = field(default_factory=dict)


class PlainReporter:
    def __init__(self, stream: TextIO | None = None, *, debug_enabled: bool = False):
        self.stream = stream or sys.stdout
        self.debug_enabled = debug_enabled

    def status(self, message: str) -> None:
        for line in format_status_lines(message):
            self.line(line)

    def debug(self, *, event: str, **fields) -> None:
        if not self.debug_enabled:
            return
        self.line(format_debug_line(event, fields))

    def emit_install_preflight_counters(
        self,
        *,
        files: tuple[int, int],
        sections: tuple[int, int],
        lines: tuple[int, int],
        patch_targets: tuple[int, int],
    ) -> None:
        return

    def emit_install_counters(self, **counters: tuple[int, int]) -> None:
        return

    def emit_uninstall_counters(self, **counters: tuple[int, int]) -> None:
        return

    def line(self, message: str = "") -> None:
        self.stream.write(f"{message}\n")
        self.stream.flush()

    def prepare_for_prompt(self) -> None:
        return

    def emit_error(self, error: Exception) -> None:
        self.line(getattr(error, "message", str(error)))
        if isinstance(error, RollbackFailedError):
            for line in rollback_context_lines(error):
                self.line(line)
            self._emit_groups(rollback_failure_groups(error))
            self._emit_groups(rollback_recovery_groups(error))
        if isinstance(error, PreflightTargetsError):
            self._emit_groups(preflight_report_groups(error.report))

    def emit_install_success(
        self, *, patch_results: tuple[PatchResult, ...], managed_tree_drift: tuple[DriftRecord, ...]
    ) -> None:
        self.line(messages.INSTALLED)
        self._emit_groups(user_modified_patch_groups(patch_results))
        if managed_tree_drift:
            self._emit_groups(
                (
                    DetailGroup(
                        messages.MANAGED_TREE_DRIFT_OVERWRITTEN,
                        managed_tree_drift_rows(managed_tree_drift),
                    ),
                )
            )

    def emit_uninstall_success(
        self, *, patch_results: tuple[PatchResult, ...], managed_tree_drift: tuple[DriftRecord, ...]
    ) -> None:
        self.line(messages.UNINSTALLED)
        self._emit_groups(user_modified_patch_groups(patch_results))
        if managed_tree_drift:
            self._emit_groups(
                (
                    DetailGroup(
                        messages.MANAGED_TREE_DRIFT,
                        managed_tree_drift_rows(managed_tree_drift),
                    ),
                )
            )

    def emit_install_dry_run(self, *, plan: InstallPlan) -> None:
        self.line("Dry-run summary:")
        self.line(f"Backup label: {plan.backup_label}")
        self._emit_groups(install_dry_run_groups(plan))
        self.line("Dry-run complete. No changes made.")

    def emit_uninstall_dry_run(self, *, plan: UninstallPlan) -> None:
        self.line("Dry-run summary:")
        self.line(f"Backup label: {plan.backup_label}")
        self._emit_groups(uninstall_dry_run_groups(plan))
        self.line("Dry-run complete. No changes made.")

    def emit_nothing_to_uninstall(self) -> None:
        self.line(messages.NOTHING_TO_UNINSTALL)

    def emit_clear_recovery_sentinel(self, removed: bool) -> None:
        if removed:
            self.line("Recovery sentinel cleared.")
        else:
            self.line("Recovery sentinel was not present.")

    def _emit_groups(self, groups: tuple[DetailGroup, ...]) -> None:
        for group in groups:
            self.line(group.heading)
            for row in group.rows:
                self.line(f"  - {row}")


class RichReporter:
    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        bundle_root: Path | None = None,
        debug_enabled: bool = False,
    ):
        self.stream = stream or sys.stdout
        self.debug_enabled = debug_enabled
        self.rich = load_rich_modules(bundle_root=bundle_root)
        self.console = self.rich.Console(file=self.stream, highlight=False)
        self.state = ReporterState()
        self._live = None

    def line(self, message: str = "") -> None:
        self._print_line(message)

    def status(self, message: str) -> None:
        self.state.current_status = message
        self.state.stage_index = STATUS_STAGE_INDEX.get(message)
        self._refresh_live()

    def debug(self, *, event: str, **fields) -> None:
        if not self.debug_enabled:
            return
        self._print_line(format_debug_line(event, fields))

    def emit_install_preflight_counters(
        self,
        *,
        files: tuple[int, int],
        sections: tuple[int, int],
        lines: tuple[int, int],
        patch_targets: tuple[int, int],
    ) -> None:
        return

    def emit_install_counters(self, **counters: tuple[int, int]) -> None:
        return

    def emit_uninstall_counters(self, **counters: tuple[int, int]) -> None:
        return

    def emit_error(self, error: Exception) -> None:
        self._stop_live()
        self._print_line(getattr(error, "message", str(error)))
        if isinstance(error, RollbackFailedError):
            self._print_lines(rollback_context_lines(error))
            self._print_groups(rollback_failure_groups(error))
            self._print_groups(rollback_recovery_groups(error))
        if isinstance(error, PreflightTargetsError):
            self._print_groups(preflight_report_groups(error.report))

    def emit_install_success(
        self, *, patch_results: tuple[PatchResult, ...], managed_tree_drift: tuple[DriftRecord, ...]
    ) -> None:
        self._stop_live()
        self._print_line(messages.INSTALLED)
        self._print_groups(user_modified_patch_groups(patch_results))
        if managed_tree_drift:
            self._print_groups(
                (
                    DetailGroup(
                        messages.MANAGED_TREE_DRIFT_OVERWRITTEN,
                        managed_tree_drift_rows(managed_tree_drift),
                    ),
                )
            )

    def emit_uninstall_success(
        self, *, patch_results: tuple[PatchResult, ...], managed_tree_drift: tuple[DriftRecord, ...]
    ) -> None:
        self._stop_live()
        self._print_line(messages.UNINSTALLED)
        self._print_groups(user_modified_patch_groups(patch_results))
        if managed_tree_drift:
            self._print_groups(
                (
                    DetailGroup(
                        messages.MANAGED_TREE_DRIFT,
                        managed_tree_drift_rows(managed_tree_drift),
                    ),
                )
            )

    def emit_install_dry_run(self, *, plan: InstallPlan) -> None:
        self._stop_live()
        self._print_line("Dry-run summary:")
        self._print_line(f"Backup label: {plan.backup_label}")
        self._print_groups(install_dry_run_groups(plan))
        self._print_line("Dry-run complete. No changes made.")

    def emit_uninstall_dry_run(self, *, plan: UninstallPlan) -> None:
        self._stop_live()
        self._print_line("Dry-run summary:")
        self._print_line(f"Backup label: {plan.backup_label}")
        self._print_groups(uninstall_dry_run_groups(plan))
        self._print_line("Dry-run complete. No changes made.")

    def emit_nothing_to_uninstall(self) -> None:
        self._stop_live()
        self._print_line(messages.NOTHING_TO_UNINSTALL)

    def emit_clear_recovery_sentinel(self, removed: bool) -> None:
        self._stop_live()
        if removed:
            self._print_line("Recovery sentinel cleared.")
        else:
            self._print_line("Recovery sentinel was not present.")

    def _refresh_live(self) -> None:
        if self._live is None:
            self._live = self.rich.Live(
                self._render_live(),
                console=self.console,
                auto_refresh=False,
                refresh_per_second=8,
                transient=False,
            )
            self._live.start()
            return
        self._live.update(self._render_live(), refresh=True)

    def _stop_live(self) -> None:
        if self._live is None:
            return
        self._live.stop()
        self._live = None

    def _print_lines(self, lines: tuple[str, ...]) -> None:
        for line in lines:
            self._print_line(line)

    def _print_line(self, message: str = "") -> None:
        self.console.print(message, markup=False, highlight=False, soft_wrap=True)

    def _print_groups(self, groups: tuple[DetailGroup, ...]) -> None:
        for group in groups:
            self._print_line(group.heading)
            bullet_table = self.rich.Table.grid(padding=(0, 1))
            bullet_table.expand = False
            for row in group.rows:
                bullet_table.add_row("•", row)
            self.console.print(bullet_table, markup=False, highlight=False)

    def prepare_for_prompt(self) -> None:
        self._stop_live()

    def _render_live(self):
        return self.rich.Group(self._render_status_panel())

    def _render_status_panel(self):
        table = self.rich.Table.grid(padding=(0, 1))
        table.expand = True
        stage_index = self.state.stage_index or 0
        stage_label = f"stage {stage_index}/{STAGE_COUNT}"
        table.add_row(self.rich.Text(stage_label, style="bold cyan"))
        table.add_row(self.rich.ProgressBar(total=STAGE_COUNT, completed=stage_index))
        if self.state.current_status is not None:
            table.add_row(self.rich.Text(self.state.current_status, style="bold"))
        return self.rich.Panel(
            table,
            title="QIDI Max 4 Optimized installer",
            border_style="cyan",
        )



def create_reporter(
    stream: TextIO | None = None,
    *,
    prefer_plain: bool = False,
    bundle_root: Path | None = None,
    environ: dict[str, str] | None = None,
    debug: bool = False,
):
    target_stream = stream or sys.stdout
    env = os.environ if environ is None else environ
    if prefer_plain or not stream_supports_live_tui(target_stream, environ=env):
        return PlainReporter(target_stream, debug_enabled=debug)
    try:
        return RichReporter(target_stream, bundle_root=bundle_root, debug_enabled=debug)
    except (ImportError, VendoredImportError):
        return PlainReporter(target_stream, debug_enabled=debug)



def load_rich_modules(*, bundle_root: Path | None = None) -> RichModules:
    vendor_root = (
        vendor_root_from_bundle_root(bundle_root)
        if bundle_root is not None
        else default_vendor_root()
    )
    import_optional_vendored_module("rich", vendor_root)
    from rich import box as rich_box
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress_bar import ProgressBar
    from rich.table import Table
    from rich.text import Text

    return RichModules(
        Console=Console,
        Group=Group,
        Live=Live,
        Panel=Panel,
        ProgressBar=ProgressBar,
        Table=Table,
        Text=Text,
        box=rich_box,
    )



def stream_supports_live_tui(
    stream: TextIO,
    *,
    environ: dict[str, str] | None = None,
) -> bool:
    isatty = getattr(stream, "isatty", None)
    if isatty is None or not isatty():
        return False
    env = os.environ if environ is None else environ
    return env.get("TERM") != "dumb"



def format_status_lines(message: str) -> tuple[str, ...]:
    stage_index = STATUS_STAGE_INDEX.get(message)
    if stage_index is None:
        return (message,)
    return (f"stage {stage_index}/{STAGE_COUNT}", message)



def format_counter_line(label: str, counters: dict[str, tuple[int, int]]) -> str:
    return (
        f"{label}: "
        + ", ".join(
            format_counter(name, value)
            for name, value in counters.items()
        )
    )



def format_counter(label: str, value: tuple[int, int]) -> str:
    return f"{label} {value[0]}/{value[1]}"



def format_debug_line(event: str, fields: dict[str, object]) -> str:
    parts = [f"debug | event={event}"]
    for key, value in sorted(fields.items()):
        parts.append(f"{key}={_format_debug_value(value)}")
    return " | ".join(parts)



def preflight_report_groups(report: PreflightReport) -> tuple[DetailGroup, ...]:
    groups = []
    if report.missing_files:
        groups.append(DetailGroup("Files:", tuple(report.missing_files)))
    if report.missing_sections:
        groups.append(
            DetailGroup(
                "Sections:",
                tuple(f"{item.file} :: [{item.section}]" for item in report.missing_sections),
            )
        )
    if report.missing_lines:
        groups.append(
            DetailGroup(
                "Lines:",
                tuple(f"{item.file} :: {item.line}" for item in report.missing_lines),
            )
        )
    if report.patch_target_issues:
        groups.append(
            DetailGroup(
                "Patch targets:",
                tuple(
                    f"{item.reason}: {item.file} :: [{item.section}] :: {item.option} ({item.id})"
                    for item in report.patch_target_issues
                ),
            )
        )
    return tuple(groups)



def user_modified_patch_groups(patch_results: tuple[PatchResult, ...]) -> tuple[DetailGroup, ...]:
    rows = tuple(
        f"{item.id} | {item.file} | [{item.section}] | {item.option} | {item.current}"
        for item in patch_results
        if item.classification == USER_MODIFIED
    )
    if not rows:
        return ()
    return (DetailGroup(messages.USER_MODIFIED_PATCH_TARGETS, rows),)



def managed_tree_drift_rows(managed_tree_drift: tuple[DriftRecord, ...]) -> tuple[str, ...]:
    return tuple(f"{drift.path} | {drift.sha256_before_remove}" for drift in managed_tree_drift)



def rollback_context_lines(error: RollbackFailedError) -> tuple[str, ...]:
    details = error.details
    lines = []
    if details.backup_label:
        lines.append(f"Backup label: {details.backup_label}")
    if details.backup_zip_path:
        lines.append(f"Backup zip: {details.backup_zip_path}")
    if details.restore_target_path:
        lines.append(f"Restore target: {details.restore_target_path}")
    if details.recovery_sentinel_path:
        lines.append(f"Recovery sentinel: {details.recovery_sentinel_path}")
    return tuple(lines)



def rollback_failure_groups(error: RollbackFailedError) -> tuple[DetailGroup, ...]:
    details = error.details
    if not details.failed_paths:
        return ()
    return (DetailGroup("Rollback failures:", details.failed_paths),)



def rollback_recovery_groups(error: RollbackFailedError) -> tuple[DetailGroup, ...]:
    details = error.details
    rows = []
    if details.backup_zip_path and details.restore_target_path:
        rows.append(
            f"Restore the full archived snapshot from {details.backup_zip_path} into {details.restore_target_path}."
        )
        rows.append(
            f"Verify {details.restore_target_path} matches the archive before clearing the recovery sentinel."
        )
    elif details.backup_zip_path:
        rows.append(f"Restore the full archived snapshot from {details.backup_zip_path}.")
    if details.recovery_sentinel_path:
        rows.append(f"Recovery sentinel remains at {details.recovery_sentinel_path}.")
    rows.append(f"Clear the recovery sentinel with: {details.clear_command}")
    return (DetailGroup("Recovery actions:", tuple(rows)),)



def install_dry_run_groups(plan: InstallPlan) -> tuple[DetailGroup, ...]:
    return (
        DetailGroup("Managed-tree intent:", managed_tree_install_intent_rows(plan)),
        DetailGroup("Include-line intent:", install_include_intent_rows(plan)),
        DetailGroup("Guarded patch intent:", install_patch_intent_rows(plan.patch_results)),
        DetailGroup("Managed tree drift detection:", drift_report_rows(plan.managed_tree_drift)),
        DetailGroup("State-file intent:", (f"would write {plan.state_file_intent.path}",)),
    )



def uninstall_dry_run_groups(plan: UninstallPlan) -> tuple[DetailGroup, ...]:
    return (
        DetailGroup("Managed-tree intent:", managed_tree_uninstall_intent_rows(plan)),
        DetailGroup("Include-line intent:", uninstall_include_intent_rows(plan)),
        DetailGroup(
            "Guarded patch reversal intent:",
            uninstall_patch_intent_rows(plan.patch_results),
        ),
        DetailGroup("Managed tree drift detection:", drift_report_rows(plan.managed_tree_drift)),
        DetailGroup("State-file intent:", (f"would delete {plan.state_file_intent.path}",)),
    )



def install_patch_intent_rows(patch_results: tuple[PatchResult, ...]) -> tuple[str, ...]:
    rows = []
    for item in patch_results:
        if item.classification == INSTALL_APPLIED:
            rows.append(
                f"would apply {item.id} | {item.file} | [{item.section}] | {item.option} | {item.expected} -> {item.desired}"
            )
            continue
        if item.classification == INSTALL_NOOP_DESIRED:
            rows.append(
                f"already desired {item.id} | {item.file} | [{item.section}] | {item.option} | {item.current}"
            )
            continue
        rows.append(
            f"would preserve user-modified {item.id} | {item.file} | [{item.section}] | {item.option} | {item.current}"
        )
    return tuple(rows)



def uninstall_patch_intent_rows(patch_results: tuple[PatchResult, ...]) -> tuple[str, ...]:
    rows = []
    for item in patch_results:
        if item.classification == UNINSTALL_REVERTED:
            rows.append(
                f"would revert {item.id} | {item.file} | [{item.section}] | {item.option} | {item.desired} -> {item.expected}"
            )
            continue
        if item.classification == UNINSTALL_NOOP_EXPECTED:
            rows.append(
                f"already expected {item.id} | {item.file} | [{item.section}] | {item.option} | {item.current}"
            )
            continue
        rows.append(
            f"would preserve user-modified {item.id} | {item.file} | [{item.section}] | {item.option} | {item.current}"
        )
    return tuple(rows)



def drift_report_rows(managed_tree_drift: tuple[DriftRecord, ...]) -> tuple[str, ...]:
    if not managed_tree_drift:
        return ("none",)
    return managed_tree_drift_rows(managed_tree_drift)



def managed_tree_install_intent_rows(plan: InstallPlan) -> tuple[str, ...]:
    intent = plan.managed_tree_intent
    return (f"mirror {intent.source} -> {intent.destination}",)



def managed_tree_uninstall_intent_rows(plan: UninstallPlan) -> tuple[str, ...]:
    return (f"would remove {plan.managed_tree_intent.destination}",)



def install_include_intent_rows(plan: InstallPlan) -> tuple[str, ...]:
    rows = []
    for intent in plan.include_line_intents:
        if intent.action == "ensure":
            rows.append(f"would ensure {intent.file} :: {intent.line} after {intent.after}")
        else:
            rows.append(f"already present {intent.file} :: {intent.line}")
    return tuple(rows)



def uninstall_include_intent_rows(plan: UninstallPlan) -> tuple[str, ...]:
    rows = []
    for intent in plan.include_line_intents:
        if intent.action == "remove":
            rows.append(f"would remove {intent.file} :: {intent.line}")
        else:
            rows.append(f"already absent {intent.file} :: {intent.line}")
    return tuple(rows)



def _format_debug_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "none"
    if isinstance(value, Path):
        text = str(value)
    else:
        text = str(value)
    if not text:
        return "''"
    if any(char.isspace() or char in {"|", "="} for char in text):
        return repr(text)
    return text
