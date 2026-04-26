from __future__ import annotations

import random
import shutil
import urllib.request

from . import klipper_cfg, messages, patches
from .auto_update import maybe_prompt_enable_auto_updates
from .box_enablement import maybe_prompt_align_tool_slots, maybe_prompt_enable_box
from .backup import (
    INSTALL_BACKUP_HISTORY_MESSAGES,
    build_install_backup_label,
    create_config_backup,
    format_installed_at,
    list_installer_backups,
    prune_installer_backups,
    utc_now,
)
from .ensure_lines import ensure_line_after
from .errors import OperationCancelled, PreviousPackageValidationError, UnsupportedFirmwareError
from .firmware import detect_firmware_version
from .interaction import confirm_yes, maybe_restart_klipper
from .fs_atomic import atomic_write_text
from .mirror import (
    collect_source_hashes,
    detect_install_managed_tree_drift,
    mirror_tree,
)
from .models import (
    IncludeLineIntent,
    InstallPlan,
    InstalledState,
    InstallResult,
    ManagedTreeFileRecord,
    ManagedTreeIntent,
    ManagedTreeState,
    Manifest,
    PatchLedgerEntry,
    RuntimePaths,
    StateFileIntent,
)
from .postflight import verify_install_postflight
from .preflight import run_install_preflight
from .rollback import RollbackJournal
from .state_file import StateValidationError, load_installed_state, write_installed_state



def run_install(
    paths: RuntimePaths,
    manifest: Manifest,
    reporter,
    *,
    dry_run: bool = False,
    input_stream=None,
    urlopen=urllib.request.urlopen,
    disk_usage=shutil.disk_usage,
    backup_history_chooser=random.choice,
    environ: dict[str, str] | None = None,
) -> InstallResult:
    reporter.debug(
        event="install.start",
        dry_run=dry_run,
        package_version=manifest.package.version,
    )

    reporter.status(messages.CHECKING_FIRMWARE_VERSION)
    detected_firmware = detect_firmware_version(paths.firmware_manifest_path)
    reporter.debug(
        event="install.firmware.detected",
        firmware_version=detected_firmware,
        manifest_path=paths.firmware_manifest_path,
    )
    if detected_firmware not in manifest.firmware.supported:
        raise UnsupportedFirmwareError()

    reporter.status(messages.CHECKING_PACKAGE_VERSION)
    state_path = paths.printer_data_root / manifest.state_file
    prior_state = None
    if state_path.exists():
        try:
            prior_state = load_installed_state(state_path)
        except StateValidationError as exc:
            raise PreviousPackageValidationError() from exc
        if prior_state.package_version not in manifest.package.known_versions:
            raise PreviousPackageValidationError()
        reporter.debug(
            event="install.prior_state.loaded",
            state_path=state_path,
            package_version=prior_state.package_version,
        )
    else:
        reporter.debug(event="install.prior_state.missing", state_path=state_path)

    reporter.status(messages.PERFORMING_PREFLIGHT_CHECKS)
    run_install_preflight(
        paths=paths,
        manifest=manifest,
        reporter=reporter,
        urlopen=urlopen,
        disk_usage=disk_usage,
        detected_firmware=detected_firmware,
        prior_state=prior_state,
    )

    if not dry_run and not confirm_yes(
        reporter=reporter,
        input_stream=input_stream,
        question=messages.INSTALL_CONFIRMATION_PROMPT,
        instruction=messages.INSTALL_CONFIRMATION_INSTRUCTION,
        cancel_message=messages.INSTALL_CANCELLED,
    ):
        reporter.debug(event="install.cancelled", dry_run=False)
        raise OperationCancelled(messages.INSTALL_CANCELLED)

    reporter.status(messages.CREATING_BACKUP)
    started_at = utc_now()
    backup_label = build_install_backup_label(
        label_prefix=manifest.backup.label_prefix,
        firmware_version=detected_firmware,
        package_version=manifest.package.version,
        moment=started_at,
    )
    backup_zip_path = None
    if not dry_run:
        existing_backups = list_installer_backups(
            paths.printer_data_root,
            install_label_prefix=manifest.backup.label_prefix,
        )
        reporter.debug(
            event="install.backups.detected",
            existing_backups=len(existing_backups),
            backup_root=paths.backup_root,
        )
        backup_zip_path = create_config_backup(
            printer_data_root=paths.printer_data_root,
            source_directory=manifest.backup.source_directory,
            backup_label=backup_label,
        )
        pruned_backups = prune_installer_backups(
            paths.printer_data_root,
            install_label_prefix=manifest.backup.label_prefix,
            keep_path=backup_zip_path,
        )
        reporter.debug(
            event="install.backup.created",
            backup_label=backup_label,
            backup_zip_path=backup_zip_path,
            pruned_backups=len(pruned_backups),
        )
        if pruned_backups:
            reporter.debug(
                event="install.backup.retention.pruned",
                removed=", ".join(str(path) for path in pruned_backups),
            )
        if existing_backups:
            reporter.line(backup_history_chooser(INSTALL_BACKUP_HISTORY_MESSAGES))

    reporter.status(messages.INSTALLING)
    plan = build_install_plan(
        paths=paths,
        manifest=manifest,
        detected_firmware=detected_firmware,
        prior_state=prior_state,
        backup_label=backup_label,
    )
    reporter.debug(
        event="install.plan.built",
        patches=len(plan.patch_results),
        managed_tree_drift=len(plan.managed_tree_drift),
        managed_tree_files=len(plan.managed_tree_files),
    )
    if dry_run:
        _emit_install_dry_run_counters(reporter, manifest)
        result = InstallResult(
            patch_results=plan.patch_results,
            managed_tree_drift=plan.managed_tree_drift,
            backup_label=plan.backup_label,
            backup_zip_path=None,
            dry_run=True,
        )
        reporter.emit_install_dry_run(plan=plan)
        reporter.debug(event="install.complete", dry_run=True, backup_label=plan.backup_label)
        return result

    return _execute_install(
        paths=paths,
        manifest=manifest,
        reporter=reporter,
        detected_firmware=detected_firmware,
        prior_state=prior_state,
        started_at=started_at,
        plan=plan,
        backup_zip_path=backup_zip_path,
        input_stream=input_stream,
        urlopen=urlopen,
        environ=environ,
    )



def build_install_plan(
    *,
    paths: RuntimePaths,
    manifest: Manifest,
    detected_firmware: str,
    prior_state: InstalledState | None,
    backup_label: str,
) -> InstallPlan:
    source_hashes = _source_hashes(paths=paths, manifest=manifest)
    managed_tree_root = paths.printer_data_root / manifest.managed_tree.destination
    managed_tree_drift = detect_install_managed_tree_drift(
        destination_root=managed_tree_root,
        printer_data_root=paths.printer_data_root,
        prior_state=prior_state,
        source_hashes=source_hashes,
    )
    patch_results = _collect_install_patch_results(
        paths=paths,
        manifest=manifest,
        detected_firmware=detected_firmware,
        prior_state=prior_state,
    )
    include_line_intents = _collect_install_include_line_intents(paths=paths, manifest=manifest)
    managed_tree_intent = ManagedTreeIntent(
        id=manifest.managed_tree.id,
        source=manifest.managed_tree.source,
        destination=manifest.managed_tree.destination,
        action="mirror",
    )
    managed_tree_files = tuple(
        ManagedTreeFileRecord(path=path, sha256=sha)
        for path, sha in sorted(source_hashes.items())
    )
    return InstallPlan(
        backup_label=backup_label,
        managed_tree_intent=managed_tree_intent,
        include_line_intents=include_line_intents,
        patch_results=patch_results,
        managed_tree_drift=managed_tree_drift,
        managed_tree_files=managed_tree_files,
        state_file_intent=StateFileIntent(path=manifest.state_file, action="write"),
    )



def _execute_install(
    *,
    paths: RuntimePaths,
    manifest: Manifest,
    reporter,
    detected_firmware: str,
    prior_state: InstalledState | None,
    started_at,
    plan: InstallPlan,
    backup_zip_path,
    input_stream,
    urlopen,
    environ: dict[str, str] | None,
) -> InstallResult:
    state_path = paths.printer_data_root / manifest.state_file
    journal = RollbackJournal(
        paths.recovery_sentinel_path,
        printer_data_root=paths.printer_data_root,
        source_directory=manifest.backup.source_directory,
    )
    patch_results = []
    install_counters = _install_counters_template(manifest)
    try:
        touched_files = {state_path, paths.config_root / "saved_variables.cfg"}
        touched_files.update(paths.printer_data_root / spec.file for spec in manifest.install.ensure_lines)
        touched_files.update(paths.printer_data_root / patch.file for patch in manifest.patches.set_options)
        touched_files.update(paths.printer_data_root / patch.file for patch in manifest.patches.delete_sections)
        for touched in touched_files:
            journal.track_file(touched)
        journal.track_tree(paths.printer_data_root / manifest.managed_tree.destination)
        reporter.debug(
            event="install.rollback.tracking",
            tracked_files=len(touched_files),
            tracked_trees=1,
        )

        maybe_prompt_enable_box(
            paths=paths,
            reporter=reporter,
            input_stream=input_stream,
            journal=journal,
        )
        maybe_prompt_align_tool_slots(
            paths=paths,
            reporter=reporter,
            input_stream=input_stream,
            journal=journal,
        )

        for directory in manifest.install.ensure_directories:
            target = paths.printer_data_root / directory
            if not target.exists():
                journal.note_write()
                target.mkdir(parents=True, exist_ok=True)
            install_counters["ensure_directories"][0] += 1
        reporter.emit_install_counters(**_freeze_counters(install_counters))

        mirror_tree(
            source_root=paths.installer_root / manifest.managed_tree.source,
            destination_root=paths.printer_data_root / manifest.managed_tree.destination,
            journal=journal,
        )
        install_counters["managed_trees"][0] = 1
        reporter.emit_install_counters(**_freeze_counters(install_counters))

        for ensure_line in manifest.install.ensure_lines:
            path = paths.printer_data_root / ensure_line.file
            text = klipper_cfg.read_text(path)
            new_text = ensure_line_after(text, ensure_line.line, ensure_line.after)
            if new_text != text:
                journal.note_write()
                atomic_write_text(path, new_text)
            install_counters["ensure_lines"][0] += 1
        reporter.emit_install_counters(**_freeze_counters(install_counters))

        for patch in manifest.patches.set_options:
            path = paths.printer_data_root / patch.file
            text = klipper_cfg.read_text(path)
            resolved = klipper_cfg.resolve_unique_option(text, patch.section, patch.option)
            result = patches.classify_install_patch(resolved.value, patch, detected_firmware)
            patch_results.append(result)
            if result.classification == patches.INSTALL_APPLIED:
                new_text = klipper_cfg.set_option_value(
                    text, patch.section, patch.option, result.desired
                )
                journal.note_write()
                atomic_write_text(path, new_text)
            install_counters["patches"][0] += 1

        for patch in manifest.patches.delete_sections:
            path = paths.printer_data_root / patch.file
            text = klipper_cfg.read_text(path)
            current_section = _resolve_section_text_or_none(text, patch.section)
            result = patches.classify_install_section_delete(
                current_section, patch, detected_firmware
            )
            result = _preserve_prior_section_expected(result, prior_state)
            patch_results.append(result)
            if result.classification == patches.INSTALL_APPLIED:
                new_text = klipper_cfg.delete_section(text, patch.section)
                journal.note_write()
                atomic_write_text(path, new_text)
            install_counters["patches"][0] += 1
        reporter.emit_install_counters(**_freeze_counters(install_counters))

        verify_install_postflight(
            paths=paths, manifest=manifest, patch_results=tuple(patch_results)
        )
        install_counters["postflight"][0] = 1
        reporter.emit_install_counters(**_freeze_counters(install_counters))

        state = InstalledState(
            schema_version=1,
            package_id=manifest.package.id,
            package_version=manifest.package.version,
            runtime_firmware=detected_firmware,
            backup_label=plan.backup_label,
            installed_at=format_installed_at(started_at),
            managed_tree=ManagedTreeState(
                root=manifest.managed_tree.destination,
                files=plan.managed_tree_files,
            ),
            patch_ledger=tuple(
                PatchLedgerEntry(
                    id=result.id,
                    file=result.file,
                    section=result.section,
                    option=result.option,
                    expected=result.expected,
                    desired=result.desired,
                    install_result=result.classification,
                )
                for result in patch_results
            ),
        )
        journal.note_write()
        write_installed_state(state_path, state)
        install_counters["state_write"][0] = 1
        reporter.emit_install_counters(**_freeze_counters(install_counters))
    except Exception as exc:
        reporter.debug(
            event="install.failure",
            backup_label=plan.backup_label,
            error_type=type(exc).__name__,
            message=getattr(exc, "message", str(exc)),
            rollback_started=journal.write_started,
        )
        if journal.write_started:
            journal.rollback_or_raise(
                exc, backup_label=plan.backup_label, backup_zip_path=backup_zip_path
            )
        raise

    result = InstallResult(
        patch_results=tuple(patch_results),
        managed_tree_drift=plan.managed_tree_drift,
        backup_label=plan.backup_label,
        backup_zip_path=backup_zip_path,
    )
    reporter.emit_install_success(
        patch_results=result.patch_results,
        managed_tree_drift=result.managed_tree_drift,
    )
    maybe_prompt_enable_auto_updates(
        paths=paths,
        reporter=reporter,
        input_stream=input_stream,
        environ=environ,
        urlopen=urlopen,
    )
    maybe_restart_klipper(
        reporter=reporter,
        input_stream=input_stream,
        moonraker_query_url=paths.moonraker_url,
        urlopen=urlopen,
    )
    reporter.debug(
        event="install.complete",
        dry_run=False,
        backup_label=plan.backup_label,
        backup_zip_path=backup_zip_path,
        managed_tree_drift=len(result.managed_tree_drift),
        user_modified_patches=len(
            [item for item in result.patch_results if item.classification == patches.USER_MODIFIED]
        ),
    )
    return result



def _collect_install_patch_results(
    *,
    paths: RuntimePaths,
    manifest: Manifest,
    detected_firmware: str,
    prior_state: InstalledState | None,
) -> tuple:
    results = []
    for patch in manifest.patches.set_options:
        path = paths.printer_data_root / patch.file
        text = klipper_cfg.read_text(path)
        resolved = klipper_cfg.resolve_unique_option(text, patch.section, patch.option)
        results.append(patches.classify_install_patch(resolved.value, patch, detected_firmware))
    for patch in manifest.patches.delete_sections:
        path = paths.printer_data_root / patch.file
        text = klipper_cfg.read_text(path)
        current_section = _resolve_section_text_or_none(text, patch.section)
        result = patches.classify_install_section_delete(current_section, patch, detected_firmware)
        results.append(_preserve_prior_section_expected(result, prior_state))
    return tuple(results)



def _resolve_section_text_or_none(text: str, section: str) -> str | None:
    try:
        return klipper_cfg.resolve_unique_section(text, section).text
    except klipper_cfg.TargetResolutionError as exc:
        if exc.reason == "missing":
            return None
        raise



def _preserve_prior_section_expected(result, prior_state: InstalledState | None):
    if result.option != "__section__" or result.classification != patches.INSTALL_NOOP_DESIRED:
        return result
    if prior_state is None:
        return result
    for entry in prior_state.patch_ledger:
        if entry.target_tuple == (result.file, result.section, result.option):
            return type(result)(
                id=result.id,
                file=result.file,
                section=result.section,
                option=result.option,
                current=result.current,
                expected=entry.expected,
                desired=result.desired,
                classification=result.classification,
            )
    return result



def _collect_install_include_line_intents(
    *,
    paths: RuntimePaths,
    manifest: Manifest,
) -> tuple[IncludeLineIntent, ...]:
    intents = []
    for ensure_line in manifest.install.ensure_lines:
        path = paths.printer_data_root / ensure_line.file
        text = klipper_cfg.read_text(path)
        new_text = ensure_line_after(text, ensure_line.line, ensure_line.after)
        intents.append(
            IncludeLineIntent(
                id=ensure_line.id,
                file=ensure_line.file,
                line=ensure_line.line,
                after=ensure_line.after,
                action="already_present" if new_text == text else "ensure",
            )
        )
    return tuple(intents)



def _source_hashes(paths: RuntimePaths, manifest: Manifest) -> dict[str, str]:
    return collect_source_hashes(
        paths.installer_root / manifest.managed_tree.source,
        destination_root=paths.printer_data_root / manifest.managed_tree.destination,
        relative_to=paths.printer_data_root,
    )



def _install_counters_template(manifest: Manifest) -> dict[str, list[int]]:
    return {
        "ensure_directories": [0, len(manifest.install.ensure_directories)],
        "managed_trees": [0, 1],
        "ensure_lines": [0, len(manifest.install.ensure_lines)],
        "patches": [0, len(manifest.patches.set_options) + len(manifest.patches.delete_sections)],
        "postflight": [0, 1],
        "state_write": [0, 1],
    }



def _emit_install_dry_run_counters(reporter, manifest: Manifest) -> None:
    counters = _install_counters_template(manifest)
    for name in counters:
        counters[name][0] = counters[name][1]
        reporter.emit_install_counters(**_freeze_counters(counters))



def _freeze_counters(counters: dict[str, list[int]]) -> dict[str, tuple[int, int]]:
    return {name: (value[0], value[1]) for name, value in counters.items()}


