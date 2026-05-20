from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .manifest import ManifestValidationError, validate_relative_path
from .models import AllowedPatchTarget, Manifest, UpgradeSource, UpgradeSources


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
    schema_version = raw.get("schema_version")
    if schema_version != 1:
        raise CompatibilityValidationError(
            "Supported upgrade sources schema_version must be 1."
        )
    versions_raw = raw.get("versions")
    if not isinstance(versions_raw, dict):
        raise CompatibilityValidationError("versions must be a mapping.")

    versions: dict[str, UpgradeSource] = {}
    for version, entry in versions_raw.items():
        if not isinstance(version, str) or not version:
            raise CompatibilityValidationError("Version keys must be non-empty strings.")
        if not isinstance(entry, dict):
            raise CompatibilityValidationError(
                f"Version entry for {version} must be a mapping."
            )
        allowed_raw = entry.get("allowed_patch_targets")
        if not isinstance(allowed_raw, list):
            raise CompatibilityValidationError(
                f"allowed_patch_targets for {version} must be a list."
            )
        allowed_targets: list[AllowedPatchTarget] = []
        seen: set[tuple[str, str, str]] = set()
        for target in allowed_raw:
            if not isinstance(target, dict):
                raise CompatibilityValidationError(
                    f"allowed_patch_targets entries for {version} must be mappings."
                )
            item = AllowedPatchTarget(
                file=validate_relative_path(
                    _require_str(target, "file"), allowed_roots=("config",)
                ),
                section=_require_str(target, "section"),
                option=_require_str(target, "option"),
            )
            if item.target_tuple in seen:
                raise CompatibilityValidationError(
                    f"Duplicate uninstall patch target for {version}: {item.target_tuple}"
                )
            seen.add(item.target_tuple)
            allowed_targets.append(item)
        versions[version] = UpgradeSource(
            version=version, allowed_patch_targets=tuple(allowed_targets)
        )

    return UpgradeSources(schema_version=1, versions=versions)


def validate_manifest_compatibility(
    manifest: Manifest, upgrade_sources: UpgradeSources
) -> None:
    manifest_versions = set(manifest.package.known_versions)
    supported_versions = set(upgrade_sources.versions.keys())
    if manifest_versions != supported_versions:
        raise CompatibilityValidationError(
            "package.known_versions must exactly match supported upgrade-source versions."
        )

    current_entry = upgrade_sources.versions.get(manifest.package.version)
    if current_entry is None:
        raise CompatibilityValidationError(
            "Current package.version must exist in supported upgrade sources."
        )

    manifest_targets = {
        patch.target_tuple
        for patch in (*manifest.patches.set_options, *manifest.patches.delete_sections)
    }
    current_targets = {target.target_tuple for target in current_entry.allowed_patch_targets}
    if manifest_targets != current_targets:
        raise CompatibilityValidationError(
            "Current package.version uninstall targets must exactly match manifest patches."
        )


def allowed_target_tuples_for_version(
    upgrade_sources: UpgradeSources, package_version: str
) -> set[tuple[str, str, str]]:
    source = upgrade_sources.versions.get(package_version)
    if source is None:
        raise CompatibilityValidationError(
            f"Unsupported installed package version: {package_version}"
        )
    return {target.target_tuple for target in source.allowed_patch_targets}


def _require_str(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise CompatibilityValidationError(f"Expected non-empty string at {key}.")
    return value
