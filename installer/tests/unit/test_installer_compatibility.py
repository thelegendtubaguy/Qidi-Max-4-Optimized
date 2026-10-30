from __future__ import annotations

import copy
import hashlib
import io
import importlib.util
import json
import shutil
import tempfile
import unittest
from unittest import mock
from dataclasses import replace
from pathlib import Path

from installer.runtime.backup import requires_external_backup_manifest
from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.compatibility import (
    CompatibilityValidationError,
    load_supported_upgrade_sources,
    parse_supported_upgrade_sources,
    validate_installed_state_identity,
    validate_manifest_compatibility,
    validate_patch_ledger,
)
from installer.runtime.manifest import load_manifest
from installer.runtime.models import (
    InstalledState,
    ManagedTreeState,
    PatchLedgerEntry,
    SourcePatchState,
)
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.runtime.source_patches import SourcePatchError, validate_source_state
from installer.runtime.state_file import load_installed_state, write_installed_state
from installer.runtime.uninstall import run_uninstall
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, moonraker_urlopen


class InstallerCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        self.envelope = load_supported_upgrade_sources(
            REPO_ROOT / "installer/supported_upgrade_sources.yaml"
        )

    def test_cumulative_envelope_matches_captured_old_profile_union(self) -> None:
        canonical = {
            "allowed_patch_targets": [item.__dict__ for item in self.envelope.allowed_patch_targets],
            "source_patches": [item.__dict__ for item in self.envelope.source_patches],
        }
        digest = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(self.envelope.schema_version, 2)
        self.assertIn(self.manifest.package.version, self.manifest.package.known_versions)
        self.assertEqual(len(self.envelope.allowed_patch_targets), 31)
        self.assertEqual(len(self.envelope.source_patches), 5)
        self.assertEqual(
            digest,
            "a152636ed174058a9890712fb678fd022bf21f4df0aa5cfd5a34e33155c19829",
        )

    def test_parser_rejects_malformed_duplicate_and_unsafe_envelope_entries(self) -> None:
        raw = {
            "schema_version": 2,
            "allowed_patch_targets": [
                {"file": "config/printer.cfg", "section": "stepper_x", "option": "homing_speed"}
            ],
            "source_patches": [
                {
                    "id": "homing",
                    "destination": "klippy/extras/homing.py",
                    "firmware": "01.01.06.03",
                    "original_sha256": "a" * 64,
                    "desired_sha256": "b" * 64,
                }
            ],
        }
        invalid_documents = []
        duplicate_target = copy.deepcopy(raw)
        duplicate_target["allowed_patch_targets"].append(
            duplicate_target["allowed_patch_targets"][0]
        )
        invalid_documents.append(duplicate_target)
        duplicate_source = copy.deepcopy(raw)
        duplicate_source["source_patches"].append(duplicate_source["source_patches"][0])
        invalid_documents.append(duplicate_source)
        bad_hash = copy.deepcopy(raw)
        bad_hash["source_patches"][0]["desired_sha256"] = "not-a-hash"
        invalid_documents.append(bad_hash)
        escaped_path = copy.deepcopy(raw)
        escaped_path["source_patches"][0]["destination"] = "klippy/../secrets.py"
        invalid_documents.append(escaped_path)
        unsupported_root = copy.deepcopy(raw)
        unsupported_root["allowed_patch_targets"][0]["file"] = "outside/printer.cfg"
        invalid_documents.append(unsupported_root)

        for document in invalid_documents:
            with self.subTest(document=document):
                with self.assertRaises(CompatibilityValidationError):
                    parse_supported_upgrade_sources(document)

    def test_current_manifest_requires_known_version_and_envelope_coverage(self) -> None:
        missing_version = replace(
            self.manifest,
            package=replace(
                self.manifest.package,
                known_versions=tuple(
                    version
                    for version in self.manifest.package.known_versions
                    if version != self.manifest.package.version
                ),
            ),
        )
        with self.assertRaises(CompatibilityValidationError):
            validate_manifest_compatibility(missing_version, self.envelope)

        missing_target = replace(
            self.envelope,
            allowed_patch_targets=self.envelope.allowed_patch_targets[1:],
        )
        with self.assertRaises(CompatibilityValidationError):
            validate_manifest_compatibility(self.manifest, missing_target)

        missing_source = replace(
            self.envelope, source_patches=self.envelope.source_patches[1:]
        )
        with self.assertRaises(CompatibilityValidationError):
            validate_manifest_compatibility(self.manifest, missing_source)

    def test_installed_identity_and_patch_ledger_are_admitted_independently(self) -> None:
        allowed = self.envelope.allowed_patch_targets[0]
        state = _state(
            package_id=self.manifest.package.id,
            package_version="26.04.21.1",
            patch_ledger=(
                PatchLedgerEntry(
                    "historical",
                    allowed.file,
                    allowed.section,
                    allowed.option,
                    "old",
                    "new",
                    "applied",
                ),
            ),
        )
        validate_installed_state_identity(state, self.manifest)
        validate_patch_ledger(state, self.envelope)

        with self.assertRaises(CompatibilityValidationError):
            validate_installed_state_identity(
                replace(state, package_id="unrelated-package"), self.manifest
            )
        with self.assertRaises(CompatibilityValidationError):
            validate_installed_state_identity(
                replace(state, package_version="26.99.99.1"), self.manifest
            )
        with self.assertRaises(CompatibilityValidationError):
            validate_patch_ledger(
                replace(
                    state,
                    patch_ledger=(
                        replace(state.patch_ledger[0], file="config/unknown.cfg"),
                    ),
                ),
                self.envelope,
            )

    def test_external_backup_manifest_boundary_requires_admitted_numeric_versions(self) -> None:
        known = self.manifest.package.known_versions
        cases = (
            ("26.07.13.2", False, False),
            ("26.07.26.1", False, True),
            ("26.99.99.1", False, True),
            ("not-a-version", False, True),
            (None, False, True),
            ("26.04.21.1", True, True),
        )
        for package_version, declares_source, expected in cases:
            with self.subTest(package_version=package_version, declares_source=declares_source):
                self.assertEqual(
                    requires_external_backup_manifest(
                        package_version=package_version,
                        known_package_versions=known,
                        state_declares_source_patches=declares_source,
                    ),
                    expected,
                )

    def test_prior_state_identity_rejection_precedes_backup(self) -> None:
        for package_id, package_version in (
            ("unrelated-package", "26.04.21.1"),
            (self.manifest.package.id, "26.99.99.1"),
        ):
            with self.subTest(package_id=package_id, package_version=package_version):
                printer_root, paths = _runtime_paths()
                write_installed_state(
                    printer_root / self.manifest.state_file,
                    _state(
                        package_id=package_id,
                        package_version=package_version,
                        patch_ledger=(),
                    ),
                )
                with mock.patch(
                    "installer.runtime.runner.create_config_backup"
                ) as backup:
                    with self.assertRaises(Exception) as raised:
                        run_install(
                            paths,
                            self.manifest,
                            PlainReporter(io.StringIO()),
                            urlopen=moonraker_urlopen(),
                        )
                self.assertEqual(type(raised.exception).__name__, "PreviousPackageValidationError")
                backup.assert_not_called()

    def test_direct_historical_update_and_uninstall_need_no_migration_chain(self) -> None:
        for version in (
            "26.04.21.1",
            "26.07.13.2",
            "26.07.26.1",
            self.manifest.package.version,
        ):
            with self.subTest(version=version):
                printer_root, paths = _runtime_paths()
                run_install(
                    paths,
                    self.manifest,
                    PlainReporter(io.StringIO()),
                    urlopen=moonraker_urlopen(
                        saved_variables_path=printer_root / "config/saved_variables.cfg"
                    ),
                )
                state_path = printer_root / self.manifest.state_file
                prior = load_installed_state(state_path)
                write_installed_state(state_path, replace(prior, package_version=version))

                run_install(
                    paths,
                    self.manifest,
                    PlainReporter(io.StringIO()),
                    urlopen=moonraker_urlopen(
                        saved_variables_path=printer_root / "config/saved_variables.cfg"
                    ),
                )
                self.assertEqual(
                    load_installed_state(state_path).package_version,
                    self.manifest.package.version,
                )

                write_installed_state(
                    state_path,
                    replace(load_installed_state(state_path), package_version=version),
                )
                run_uninstall(
                    paths,
                    self.manifest,
                    self.envelope,
                    PlainReporter(io.StringIO()),
                    input_stream=io.StringIO("Y\nN\n"),
                    urlopen=moonraker_urlopen(),
                )
                self.assertFalse(state_path.exists())

    def test_source_ledger_requires_cumulative_provenance(self) -> None:
        patch = self.manifest.install.source_patches[0]
        variant = patch.variants[0]
        entry = SourcePatchState(
            patch.id,
            patch.destination,
            variant.firmware,
            variant.expected_sha256,
            variant.desired_sha256,
            0o644,
            b"source preimage",
            "applied",
        )
        state = _state(
            package_id=self.manifest.package.id,
            package_version="26.07.26.1",
            patch_ledger=(),
            source_patches=(entry,),
        )
        validate_source_state(
            state,
            self.manifest.install.source_patches,
            upgrade_sources=self.envelope,
            expected_firmware=variant.firmware,
        )
        for changed_entry in (
            replace(entry, destination="klippy/extras/unknown.py"),
            replace(entry, firmware="01.99.99.99"),
            replace(entry, desired_sha256="f" * 64),
        ):
            with self.subTest(entry=changed_entry):
                with self.assertRaises(SourcePatchError):
                    validate_source_state(
                        replace(state, source_patches=(changed_entry,)),
                        self.manifest.install.source_patches,
                        upgrade_sources=self.envelope,
                        expected_firmware=variant.firmware,
                    )
    def test_ordinary_version_bump_leaves_cumulative_envelope_unchanged(self) -> None:
        module = _load_version_bump_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            shutil.copytree(REPO_ROOT / "installer", root / "installer")
            envelope_path = root / "installer/supported_upgrade_sources.yaml"
            before = envelope_path.read_bytes()

            changed = module.bump_version(root, "99.01.01.1")

            self.assertEqual(
                changed,
                ["installer/package.yaml", "installer/klipper/tltg-optimized-macros/globals.cfg"],
            )
            self.assertEqual(envelope_path.read_bytes(), before)


def _state(
    *, package_id: str, package_version: str, patch_ledger, source_patches=()
) -> InstalledState:
    return InstalledState(
        schema_version=1,
        package_id=package_id,
        package_version=package_version,
        runtime_firmware="01.01.06.03",
        backup_label="test",
        installed_at="2026-01-01T00:00:00Z",
        managed_tree=ManagedTreeState("config/tltg-optimized-macros", ()),
        patch_ledger=patch_ledger,
        source_patches=source_patches,
    )


def _runtime_paths():
    printer_root = copy_base_runtime()
    (printer_root / "firmware_manifest.json").write_text(
        json.dumps({"SOC": {"version": "01.01.06.03"}}), encoding="utf-8"
    )
    paths = resolve_runtime_paths(
        bundle_root=REPO_ROOT,
        environ=build_env(
            printer_root,
            moonraker_url="http://moonraker.invalid/printer/objects/query?print_stats",
        ),
    )
    return printer_root, paths


def _load_version_bump_module():
    path = REPO_ROOT / "scripts/bump_installer_version.py"
    spec = importlib.util.spec_from_file_location("version_bump", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
