from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .manifest import ManifestValidationError, validate_relative_path
from .models import (
    AllowedPatchTarget,
    Manifest,
    UpgradeSourceExternalFile,
    UpgradeSourcePatch,
    UpgradeSources,
)


class CompatibilityValidationError(ValueError):
    pass


def load_supported_upgrade_sources(path: Path) -> UpgradeSources:
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
    except OSError as exc:
        raise CompatibilityValidationError(
            f"Could not read supported upgrade sources: {path}"
        ) from exc
    except yaml.YAMLError as exc:
        raise CompatibilityValidationError(
            f"Could not parse supported upgrade sources: {path}"
        ) from exc
    return parse_supported_upgrade_sources(raw)


def parse_supported_upgrade_sources(raw: Any) -> UpgradeSources:
    if not isinstance(raw, dict):
        raise CompatibilityValidationError(
            "Supported upgrade sources root must be a mapping."
        )
    if raw.get("schema_version") != 2:
        raise CompatibilityValidationError(
            "Supported upgrade sources schema_version must be 2."
        )
    allowed_raw = raw.get("allowed_patch_targets")
    if not isinstance(allowed_raw, list):
        raise CompatibilityValidationError("allowed_patch_targets must be a list.")

    allowed_targets: list[AllowedPatchTarget] = []
    seen_targets: set[tuple[str, str, str]] = set()
    for target in allowed_raw:
        if not isinstance(target, dict):
            raise CompatibilityValidationError(
                "allowed_patch_targets entries must be mappings."
            )
        item = AllowedPatchTarget(
            file=_validate_path(
                _require_str(target, "file"), allowed_roots=("config",)
            ),
            section=_require_str(target, "section"),
            option=_require_str(target, "option"),
        )
        if item.target_tuple in seen_targets:
            raise CompatibilityValidationError(
                f"Duplicate uninstall patch target: {item.target_tuple}"
            )
        seen_targets.add(item.target_tuple)
        allowed_targets.append(item)

    source_patches = _parse_source_patches(raw)
    return UpgradeSources(
        schema_version=2,
        allowed_patch_targets=tuple(allowed_targets),
        source_patches=source_patches,
        external_files=_parse_external_files(raw),
    )


def validate_manifest_compatibility(
    manifest: Manifest, upgrade_sources: UpgradeSources
) -> None:
    if manifest.package.version not in manifest.package.known_versions:
        raise CompatibilityValidationError(
            "Current package.version must occur in package.known_versions."
        )

    allowed_targets = {
        target.target_tuple for target in upgrade_sources.allowed_patch_targets
    }
    manifest_targets = {
        patch.target_tuple
        for patch in (*manifest.patches.set_options, *manifest.patches.delete_sections)
    }
    missing_targets = manifest_targets - allowed_targets
    if missing_targets:
        raise CompatibilityValidationError(
            "Current manifest patch targets are missing from the cumulative envelope."
        )

    allowed_sources = source_patch_provenance(upgrade_sources)
    manifest_sources = {
        (
            patch.id,
            patch.destination,
            variant.firmware,
            variant.expected_sha256,
            variant.desired_sha256,
        )
        for patch in manifest.install.source_patches
        for variant in patch.variants
    }
    missing_sources = manifest_sources - allowed_sources
    if missing_sources:
        raise CompatibilityValidationError(
            "Current manifest source-patch baselines are missing from the cumulative envelope."
        )

    allowed_external = {
        (item.id, item.destination, item.sha256)
        for item in upgrade_sources.external_files
    }
    manifest_external = {
        (item.id, item.destination, item.sha256)
        for item in manifest.install.external_files
    }
    if manifest_external - allowed_external:
        raise CompatibilityValidationError(
            "Current manifest external-file baselines are missing from the cumulative envelope."
        )


def validate_installed_state_identity(state, manifest: Manifest) -> None:
    if (
        state.package_id != manifest.package.id
        or state.package_version not in manifest.package.known_versions
    ):
        raise CompatibilityValidationError(
            "Installed package identity or version is not admitted by this manifest."
        )


def validate_patch_ledger(state, upgrade_sources: UpgradeSources) -> None:
    allowed_targets = {
        target.target_tuple for target in upgrade_sources.allowed_patch_targets
    }
    for entry in state.patch_ledger:
        if entry.target_tuple not in allowed_targets:
            raise CompatibilityValidationError(
                "Ledger patch target is not allowed by the cumulative envelope."
            )


def source_patch_provenance(
    upgrade_sources: UpgradeSources,
) -> set[tuple[str, str, str, str, str]]:
    return {
        (
            item.id,
            item.destination,
            item.firmware,
            item.original_sha256,
            item.desired_sha256,
        )
        for item in upgrade_sources.source_patches
    }


def _parse_source_patches(raw: dict[str, Any]) -> tuple[UpgradeSourcePatch, ...]:
    source_raw = raw.get("source_patches", [])
    if not isinstance(source_raw, list):
        raise CompatibilityValidationError("source_patches must be a list.")
    result: list[UpgradeSourcePatch] = []
    seen_ids: dict[str, str] = {}
    seen_destinations: dict[str, str] = {}
    seen_provenance: set[tuple[str, str, str, str, str]] = set()
    for item in source_raw:
        if not isinstance(item, dict):
            raise CompatibilityValidationError("source_patches entries must be mappings.")
        patch_id = _require_str(item, "id")
        destination = _validate_path(
            _require_str(item, "destination"), allowed_roots=("klippy",)
        )
        if not destination.startswith("klippy/extras/"):
            raise CompatibilityValidationError(
                "Source-patch destinations must stay under klippy/extras/."
            )
        firmware = _require_str(item, "firmware")
        original_sha = _require_sha256(item, "original_sha256")
        desired_sha = _require_sha256(item, "desired_sha256")
        if patch_id in seen_ids and seen_ids[patch_id] != destination:
            raise CompatibilityValidationError("Source-patch IDs must use one destination.")
        if destination in seen_destinations and seen_destinations[destination] != patch_id:
            raise CompatibilityValidationError(
                "Source-patch destinations must use one ID."
            )
        provenance = (patch_id, destination, firmware, original_sha, desired_sha)
        if provenance in seen_provenance:
            raise CompatibilityValidationError("Duplicate source-patch provenance.")
        seen_ids[patch_id] = destination
        seen_destinations[destination] = patch_id
        seen_provenance.add(provenance)
        result.append(
            UpgradeSourcePatch(
                patch_id, destination, firmware, original_sha, desired_sha
            )
        )
    return tuple(result)


def _parse_external_files(entry: dict[str, Any]) -> tuple[UpgradeSourceExternalFile, ...]:
    raw = entry.get("external_files", [])
    if not isinstance(raw, list):
        raise CompatibilityValidationError("external_files must be a list.")
    result: list[UpgradeSourceExternalFile] = []
    destinations_by_id: dict[str, str] = {}
    ids_by_destination: dict[str, str] = {}
    seen: set[tuple[str, str, str]] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise CompatibilityValidationError("external_files entries must be mappings.")
        file_id = _require_str(item, "id")
        destination = _validate_path(
            _require_str(item, "destination"), allowed_roots=("klippy",)
        )
        if not destination.startswith("klippy/extras/"):
            raise CompatibilityValidationError(
                "External-file destinations must stay under klippy/extras/."
            )
        sha256 = _require_sha256(item, "sha256")
        key = (file_id, destination, sha256)
        if key in seen:
            raise CompatibilityValidationError("Duplicate external-file baseline.")
        if file_id in destinations_by_id and destinations_by_id[file_id] != destination:
            raise CompatibilityValidationError("External-file IDs must use one destination.")
        if destination in ids_by_destination and ids_by_destination[destination] != file_id:
            raise CompatibilityValidationError("External-file destinations must use one ID.")
        destinations_by_id[file_id] = destination
        ids_by_destination[destination] = file_id
        seen.add(key)
        result.append(UpgradeSourceExternalFile(file_id, destination, sha256))
    return tuple(result)


def _validate_path(path: str, *, allowed_roots: tuple[str, ...]) -> str:
    try:
        return validate_relative_path(path, allowed_roots=allowed_roots)
    except ManifestValidationError as exc:
        raise CompatibilityValidationError(str(exc)) from exc


def _require_sha256(mapping: dict[str, Any], key: str) -> str:
    value = _require_str(mapping, key).lower()
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise CompatibilityValidationError(f"{key} must be SHA-256 hex.")
    return value


def _require_str(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise CompatibilityValidationError(f"Expected non-empty string at {key}.")
    return value
