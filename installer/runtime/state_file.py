from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .fs_atomic import atomic_delete, atomic_write_text
from .models import (
    InstalledState,
    ManagedTreeFileRecord,
    ManagedTreeState,
    PatchLedgerEntry,
)


class StateValidationError(ValueError):
    pass



def load_installed_state(path: Path) -> InstalledState:
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
    except OSError as exc:
        raise StateValidationError(f"Could not read state file: {path}") from exc
    except yaml.YAMLError as exc:
        raise StateValidationError(f"Could not parse state file: {path}") from exc
    return parse_installed_state(raw)



def parse_installed_state(raw: Any) -> InstalledState:
    if not isinstance(raw, dict):
        raise StateValidationError("State file root must be a mapping.")
    schema_version = raw.get("schema_version")
    if schema_version != 1:
        raise StateValidationError("State file schema_version must be 1.")

    package = _require_mapping(raw, "package")
    runtime = _require_mapping(raw, "runtime")
    backup = _require_mapping(raw, "backup")
    managed_tree = _require_mapping(raw, "managed_tree")

    files_raw = managed_tree.get("files")
    if not isinstance(files_raw, list):
        raise StateValidationError("managed_tree.files must be a list.")
    managed_tree_files = []
    for item in files_raw:
        if not isinstance(item, dict):
            raise StateValidationError("managed_tree.files entries must be mappings.")
        managed_tree_files.append(
            ManagedTreeFileRecord(
                path=_validate_config_path(_require_str(item, "path")),
                sha256=_require_str(item, "sha256"),
            )
        )

    ledger_raw = raw.get("patch_ledger")
    if not isinstance(ledger_raw, list):
        raise StateValidationError("patch_ledger must be a list.")
    patch_ledger = []
    for item in ledger_raw:
        if not isinstance(item, dict):
            raise StateValidationError("patch_ledger entries must be mappings.")
        install_result = _require_str(item, "install_result")
        if install_result not in {"applied", "noop_desired", "user_modified"}:
            raise StateValidationError("Unsupported patch install_result.")
        patch_ledger.append(
            PatchLedgerEntry(
                id=_require_str(item, "id"),
                file=_validate_config_path(_require_str(item, "file")),
                section=_require_str(item, "section"),
                option=_require_str(item, "option"),
                expected=_require_str(item, "expected"),
                desired=_require_str(item, "desired"),
                install_result=install_result,
            )
        )

    return InstalledState(
        schema_version=1,
        package_id=_require_str(package, "id"),
        package_version=_require_str(package, "version"),
        runtime_firmware=_require_str(runtime, "firmware"),
        backup_label=_require_str(backup, "label"),
        installed_at=_require_str(raw, "installed_at"),
        managed_tree=ManagedTreeState(
            root=_validate_config_path(_require_str(managed_tree, "root")),
            files=tuple(managed_tree_files),
        ),
        patch_ledger=tuple(patch_ledger),
    )



def write_installed_state(path: Path, state: InstalledState) -> None:
    document = {
        "schema_version": 1,
        "package": {"id": state.package_id, "version": state.package_version},
        "runtime": {"firmware": state.runtime_firmware},
        "backup": {"label": state.backup_label},
        "installed_at": state.installed_at,
        "managed_tree": {
            "root": state.managed_tree.root,
            "files": [
                {"path": item.path, "sha256": item.sha256}
                for item in state.managed_tree.files
            ],
        },
        "patch_ledger": [
            {
                "id": entry.id,
                "file": entry.file,
                "section": entry.section,
                "option": entry.option,
                "expected": entry.expected,
                "desired": entry.desired,
                "install_result": entry.install_result,
            }
            for entry in state.patch_ledger
        ],
    }
    text = yaml.safe_dump(document, sort_keys=False)
    atomic_write_text(path, text, mode=0o600, force_mode=True)



def delete_state_file(path: Path) -> None:
    atomic_delete(path)



def _require_mapping(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise StateValidationError(f"Expected mapping at {key}.")
    return value



def _require_str(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise StateValidationError(f"Expected non-empty string at {key}.")
    return value



def _validate_config_path(path: str) -> str:
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part == ".." for part in pure.parts):
        raise StateValidationError(f"Path is not allowed: {path}")
    if not pure.parts or pure.parts[0] != "config":
        raise StateValidationError(f"State paths must stay under config/: {path}")
    return pure.as_posix()
