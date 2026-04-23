from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml

from .models import (
    BackupSpec,
    EnsureLineSpec,
    FirmwareSpec,
    InstallSpec,
    LineSpec,
    ManagedTreeSpec,
    Manifest,
    PackageMeta,
    PatchSetSpec,
    PatchSpec,
    PatchVariantSpec,
    PostflightSpec,
    PreflightSpec,
    SectionSpec,
    StateSpec,
)


class ManifestValidationError(ValueError):
    pass


def load_manifest(path: Path) -> Manifest:
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
    except OSError as exc:
        raise ManifestValidationError(f"Could not read manifest: {path}") from exc
    except yaml.YAMLError as exc:
        raise ManifestValidationError(f"Could not parse manifest: {path}") from exc
    return parse_manifest(raw)


def parse_manifest(raw: Any) -> Manifest:
    if not isinstance(raw, dict):
        raise ManifestValidationError("Manifest root must be a mapping.")
    schema_version = _require_int(raw, "schema_version")
    if schema_version != 1:
        raise ManifestValidationError("Manifest schema_version must be 1.")

    package_raw = _require_mapping(raw, "package")
    package = PackageMeta(
        id=_require_str(package_raw, "id"),
        display_name=_require_str(package_raw, "display_name"),
        printer_model=_require_str(package_raw, "printer_model"),
        version=_require_str(package_raw, "version"),
        known_versions=_require_unique_str_list(package_raw, "known_versions", non_empty=True),
    )

    firmware_raw = _require_mapping(raw, "firmware")
    firmware = FirmwareSpec(
        supported=_require_unique_str_list(firmware_raw, "supported", non_empty=True)
    )

    backup_raw = _require_mapping(raw, "backup")
    backup = BackupSpec(
        source_directory=_validate_relative_path(
            _require_str(backup_raw, "source_directory"), allowed_roots=("config",)
        ),
        label_prefix=_require_str(backup_raw, "label_prefix"),
    )

    state_raw = _require_mapping(raw, "state")
    state = StateSpec(
        record_file=_validate_relative_path(
            _require_str(state_raw, "record_file"), allowed_roots=("config",)
        )
    )

    preflight_raw = _require_mapping(raw, "preflight")
    preflight = PreflightSpec(
        required_files=tuple(
            _validate_relative_path(item, allowed_roots=("config",))
            for item in _require_list_of_str(preflight_raw, "required_files")
        ),
        required_sections=tuple(
            SectionSpec(
                file=_validate_relative_path(
                    _require_str(item, "file"), allowed_roots=("config",)
                ),
                section=_require_str(item, "section"),
            )
            for item in _require_list_of_mapping(preflight_raw, "required_sections")
        ),
        required_lines=tuple(
            LineSpec(
                file=_validate_relative_path(
                    _require_str(item, "file"), allowed_roots=("config",)
                ),
                line=_require_str(item, "line"),
            )
            for item in _require_list_of_mapping(preflight_raw, "required_lines")
        ),
    )

    install_raw = _require_mapping(raw, "install")
    if "managed_trees" in install_raw:
        raise ManifestValidationError(
            "install.managed_trees is not supported; use install.managed_tree."
        )
    if "managed_files" in install_raw:
        raise ManifestValidationError("install.managed_files is not supported.")
    managed_tree_raw = _require_mapping(install_raw, "managed_tree")
    ensure_lines = tuple(
        EnsureLineSpec(
            id=_require_str(item, "id"),
            file=_validate_relative_path(
                _require_str(item, "file"), allowed_roots=("config",)
            ),
            line=_require_str(item, "line"),
            after=_require_str(item, "after"),
        )
        for item in _require_list_of_mapping(install_raw, "ensure_lines")
    )
    if len(ensure_lines) != 1:
        raise ManifestValidationError(
            "Manifest must define exactly one install.ensure_lines entry."
        )
    install = InstallSpec(
        ensure_directories=tuple(
            _validate_relative_path(item, allowed_roots=("config",))
            for item in _require_list_of_str(install_raw, "ensure_directories")
        ),
        managed_tree=ManagedTreeSpec(
            id=_require_str(managed_tree_raw, "id"),
            source=_validate_relative_path(
                _require_str(managed_tree_raw, "source"), allowed_roots=("klipper",)
            ),
            destination=_validate_relative_path(
                _require_str(managed_tree_raw, "destination"), allowed_roots=("config",)
            ),
            mode=_validate_managed_tree_mode(_require_str(managed_tree_raw, "mode")),
        ),
        ensure_lines=ensure_lines,
    )

    patches_raw = _require_mapping(raw, "patches")
    patch_specs: list[PatchSpec] = []
    seen_patch_ids: set[str] = set()
    seen_targets: set[tuple[str, str, str]] = set()
    for item in _require_list_of_mapping(patches_raw, "set_options"):
        patch_id = _require_str(item, "id")
        if patch_id in seen_patch_ids:
            raise ManifestValidationError(f"Duplicate patch id: {patch_id}")
        seen_patch_ids.add(patch_id)
        patch = PatchSpec(
            id=patch_id,
            file=_validate_relative_path(
                _require_str(item, "file"), allowed_roots=("config",)
            ),
            section=_require_str(item, "section"),
            option=_require_str(item, "option"),
            variants=tuple(
                PatchVariantSpec(
                    firmwares=_require_unique_str_list(variant, "firmwares", non_empty=True),
                    expected=_require_str(variant, "expected"),
                    desired=_require_str(variant, "desired"),
                )
                for variant in _require_list_of_mapping(item, "variants")
            ),
        )
        if patch.target_tuple in seen_targets:
            raise ManifestValidationError(
                "Duplicate patch target: " + " / ".join(patch.target_tuple)
            )
        seen_targets.add(patch.target_tuple)
        _validate_patch_variant_coverage(patch, firmware.supported)
        patch_specs.append(patch)
    patches = PatchSetSpec(set_options=tuple(patch_specs))

    postflight_raw = _require_mapping(raw, "postflight")
    if "verify_files" in postflight_raw:
        raise ManifestValidationError(
            "postflight.verify_files is not supported; install.managed_tree defines "
            "postflight file verification."
        )
    postflight = PostflightSpec(
        verify_lines=tuple(
            LineSpec(
                file=_validate_relative_path(
                    _require_str(item, "file"), allowed_roots=("config",)
                ),
                line=_require_str(item, "line"),
            )
            for item in _require_list_of_mapping(postflight_raw, "verify_lines")
        ),
    )

    return Manifest(
        schema_version=schema_version,
        package=package,
        firmware=firmware,
        backup=backup,
        state=state,
        preflight=preflight,
        install=install,
        patches=patches,
        postflight=postflight,
    )


def select_patch_variant(patch: PatchSpec, firmware_version: str) -> PatchVariantSpec:
    matches = [
        variant
        for variant in patch.variants
        if firmware_version in variant.firmwares
    ]
    if len(matches) != 1:
        raise ManifestValidationError(
            f"Patch {patch.id} does not have exactly one variant for firmware {firmware_version}."
        )
    return matches[0]


def validate_relative_path(path: str, *, allowed_roots: Iterable[str]) -> str:
    return _validate_relative_path(path, allowed_roots=tuple(allowed_roots))


def _validate_patch_variant_coverage(
    patch: PatchSpec, supported_firmwares: tuple[str, ...]
) -> None:
    for firmware_version in supported_firmwares:
        matches = [
            variant
            for variant in patch.variants
            if firmware_version in variant.firmwares
        ]
        if len(matches) != 1:
            raise ManifestValidationError(
                f"Patch {patch.id} must define exactly one variant for firmware {firmware_version}."
            )


def _validate_relative_path(path: str, *, allowed_roots: tuple[str, ...]) -> str:
    if not isinstance(path, str) or not path:
        raise ManifestValidationError("Path values must be non-empty strings.")
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part == ".." for part in pure.parts):
        raise ManifestValidationError(f"Path is not allowed: {path}")
    if not pure.parts or pure.parts[0] not in allowed_roots:
        allowed = ", ".join(allowed_roots)
        raise ManifestValidationError(f"Path must start with one of {allowed}: {path}")
    return pure.as_posix()


def _validate_managed_tree_mode(mode: str) -> str:
    if mode != "mirror":
        raise ManifestValidationError(f"Unsupported managed tree mode: {mode}")
    return mode


def _require_mapping(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise ManifestValidationError(f"Expected mapping at {key}.")
    return value


def _require_str(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ManifestValidationError(f"Expected non-empty string at {key}.")
    return value


def _require_int(mapping: dict[str, Any], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int):
        raise ManifestValidationError(f"Expected integer at {key}.")
    return value


def _require_list_of_mapping(mapping: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise ManifestValidationError(f"Expected list at {key}.")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ManifestValidationError(f"Expected mapping entries at {key}.")
        result.append(item)
    return result


def _require_list_of_str(mapping: dict[str, Any], key: str) -> list[str]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise ManifestValidationError(f"Expected list at {key}.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ManifestValidationError(f"Expected string entries at {key}.")
        result.append(item)
    return result


def _require_unique_str_list(
    mapping: dict[str, Any], key: str, *, non_empty: bool = False
) -> tuple[str, ...]:
    values = _require_list_of_str(mapping, key)
    if non_empty and not values:
        raise ManifestValidationError(f"Expected non-empty list at {key}.")
    if len(values) != len(set(values)):
        raise ManifestValidationError(f"Duplicate values are not allowed at {key}.")
    return tuple(values)
