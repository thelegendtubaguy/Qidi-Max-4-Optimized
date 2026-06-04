from __future__ import annotations

import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from installer.runtime.auto_update import LOCK_HELD_ENV
from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.compatibility import load_supported_upgrade_sources
from installer.runtime.manifest import load_manifest
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.runtime.state_file import load_installed_state, write_installed_state
from installer.runtime.models import SystemOptimizationCliOptions
from installer.runtime.system_optimizations import (
    SYSTEM_ROOT_ENV,
    SystemOptimizationError,
    _apply_service,
    _restore_file_preimage,
    _restore_service,
    _service_state,
    _validate_archive_members,
    resolve_policy,
)
from installer.runtime.uninstall import run_uninstall
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, moonraker_urlopen


class SystemOptimizationTests(unittest.TestCase):
    def test_auto_update_without_prior_policy_skips_system_optimizations(self):
        policy = resolve_policy(
            prior_ledger=None,
            reporter=PlainReporter(io.StringIO()),
            input_stream=None,
            cli_options=SystemOptimizationCliOptions(),
            auto_update_child=True,
        )

        self.assertIsNone(policy)

    def test_manifest_parses_system_optimizations(self):
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        self.assertIsNotNone(manifest.system_optimizations)
        system = manifest.system_optimizations
        assert system is not None
        self.assertEqual(system.dns.fallback_nameservers, ("1.1.1.1", "8.8.8.8"))
        self.assertEqual(system.qidiclient_static_gifs.archive, "system/qidiclient-static-gifs.tar.gz")
        self.assertEqual(system.services.disable, ("xl2tpd", "bluetooth"))

    def test_state_file_round_trips_system_ledger(self):
        printer_root = copy_base_runtime()
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=io.StringIO("yes\nno\nno\n"),
            urlopen=moonraker_urlopen(),
            environ=env,
        )
        state_path = printer_root / manifest.state_file
        state = load_installed_state(state_path)
        ledger = {"policy": {"system_optimizations": "enabled", "ai_detection": "disable"}}
        write_installed_state(state_path, type(state)(**{**state.__dict__, "system_ledger": ledger}))
        self.assertEqual(load_installed_state(state_path).system_ledger, ledger)

    def test_install_applies_system_optimizations_to_fake_root(self):
        printer_root, system_root = _runtime_with_fake_system()
        env = _env(printer_root, system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        output = io.StringIO()
        run_install(
            paths,
            manifest,
            PlainReporter(output),
            input_stream=io.StringIO("yes\nyes\nyes\nno\nno\n"),
            urlopen=moonraker_urlopen(),
            environ=env,
        )

        self.assertTrue((system_root / "etc/resolv.conf").is_symlink())
        self.assertEqual((system_root / "etc/resolv.conf").readlink(), Path("/run/resolvconf/resolv.conf"))
        self.assertEqual(
            (system_root / "etc/resolvconf/resolv.conf.d/tail").read_text(encoding="utf-8"),
            "nameserver 1.1.1.1\nnameserver 8.8.8.8\n",
        )
        self.assertIn("deb http://deb.debian.org/debian bullseye", (system_root / "etc/apt/sources.list").read_text(encoding="utf-8"))
        installed_gif = system_root / "home/qidi/QIDI_Client/access/account/process.gif"
        self.assertTrue(installed_gif.stat().st_size > 10)
        self.assertEqual(installed_gif.stat().st_mode & 0o777, 0o600)
        backup_dirs = sorted((system_root / "home/qidi/QIDI_Client/access").glob(".gif-backup-*"))
        self.assertEqual(len(backup_dirs), 1)
        self.assertEqual((backup_dirs[0] / "account/process.gif").read_bytes(), b"old")
        self.assertIn("Spaghetti Detection", output.getvalue())
        state = load_installed_state(printer_root / manifest.state_file)
        self.assertEqual(state.system_ledger["policy"], {"system_optimizations": "enabled", "ai_detection": "disable"})
        self.assertIn("service_algo_app.service", state.system_ledger["restore_preimages"])
        gif_preimage = state.system_ledger["restore_preimages"]["qidiclient_static_gifs"]
        self.assertTrue(gif_preimage["backup_dir"].startswith(str(system_root / "home/qidi/QIDI_Client/access/.gif-backup-")))
        self.assertEqual(gif_preimage["files"]["account/process.gif"]["mode"], "0600")
        gif_actions = [action for action in state.system_ledger["actions"] if action["id"] == "qidiclient_static_gifs"]
        self.assertIn("installed_sha256", gif_actions[-1]["postflight"])

    def test_keep_ai_detection_records_service_state_without_disabling(self):
        printer_root, system_root = _runtime_with_fake_system()
        _write_fake_service(system_root, "algo_app.service", enabled="enabled", active="active")
        env = _env(printer_root, system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=io.StringIO("yes\nyes\nno\nno\nno\n"),
            urlopen=moonraker_urlopen(),
            environ=env,
        )

        state = load_installed_state(printer_root / manifest.state_file)
        ai_actions = [action for action in state.system_ledger["actions"] if action["id"] == "service_algo_app.service"]
        self.assertEqual(ai_actions[-1]["status"], "skipped_by_policy")
        self.assertEqual(ai_actions[-1]["preimage"]["enabled"], "enabled")
        self.assertEqual(ai_actions[-1]["preimage"]["active"], "active")
        self.assertNotIn("service_algo_app.service", state.system_ledger["restore_preimages"])
        self.assertEqual(json.loads((system_root / "systemd/algo_app.service.json").read_text(encoding="utf-8"))["enabled"], "enabled")

    def test_service_state_normalizes_sysv_is_enabled_notice(self):
        def run(command, **kwargs):
            if command == ["systemctl", "is-enabled", "xl2tpd"]:
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout=(
                        "xl2tpd.service is not a native service, redirecting to systemd-sysv-install.\n"
                        "Executing: /lib/systemd/systemd-sysv-install is-enabled xl2tpd\n"
                        "disabled\n"
                    ),
                )
            if command == ["systemctl", "is-active", "xl2tpd"]:
                return subprocess.CompletedProcess(command, 3, stdout="inactive\n")
            raise AssertionError(command)

        state = _service_state("xl2tpd", root=Path("/"), run=run)

        self.assertTrue(state["exists"])
        self.assertEqual(state["enabled"], "disabled")
        self.assertEqual(state["active"], "inactive")

    def test_apply_service_runs_explicit_stop_fallbacks_for_sysv_service(self):
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0)

        _apply_service(
            "xl2tpd",
            root=Path("/"),
            sudo_password="qiditech",
            run=run,
            preimage={"exists": True},
        )

        self.assertEqual(
            commands,
            [
                ["sudo", "-S", "-p", "", "systemctl", "disable", "--now", "xl2tpd"],
                ["sudo", "-S", "-p", "", "systemctl", "stop", "xl2tpd"],
                ["sudo", "-S", "-p", "", "/etc/init.d/xl2tpd", "stop"],
            ],
        )

    def test_apply_service_skips_init_script_fallback_for_dotted_service(self):
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0)

        _apply_service(
            "algo_app.service",
            root=Path("/"),
            sudo_password="qiditech",
            run=run,
            preimage={"exists": True},
        )

        self.assertEqual(
            commands,
            [
                ["sudo", "-S", "-p", "", "systemctl", "disable", "--now", "algo_app.service"],
                ["sudo", "-S", "-p", "", "systemctl", "stop", "algo_app.service"],
            ],
        )

    def test_missing_default_service_is_recorded_without_restore_preimage(self):
        printer_root, system_root = _runtime_with_fake_system()
        _write_fake_service(system_root, "xl2tpd", exists=False, enabled="not-found", active="not-found")
        env = _env(printer_root, system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=io.StringIO("yes\nyes\nno\nno\nno\n"),
            urlopen=moonraker_urlopen(),
            environ=env,
        )

        state = load_installed_state(printer_root / manifest.state_file)
        xl2tpd_actions = [action for action in state.system_ledger["actions"] if action["id"] == "service_xl2tpd"]
        self.assertEqual(xl2tpd_actions[-1]["status"], "missing")
        self.assertFalse(xl2tpd_actions[-1]["preimage"]["exists"])
        self.assertNotIn("service_xl2tpd", state.system_ledger["restore_preimages"])

    def test_auto_update_reconciles_prior_system_policy(self):
        printer_root, system_root = _runtime_with_fake_system()
        env = _env(printer_root, system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=io.StringIO("yes\nyes\nyes\nno\nno\n"),
            urlopen=moonraker_urlopen(),
            environ=env,
        )

        (system_root / "etc/resolv.conf").unlink()
        (system_root / "etc/resolv.conf").write_text("nameserver 114.114.114.114\n", encoding="utf-8")
        (system_root / "etc/apt/sources.list").write_text("deb http://mirrors.ustc.edu.cn/debian bullseye main\n", encoding="utf-8")
        (system_root / "systemd/algo_app.service.json").write_text('{"exists": true, "service": "algo_app.service", "enabled": "enabled", "active": "active"}', encoding="utf-8")
        env[LOCK_HELD_ENV] = "1"
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=None,
            urlopen=moonraker_urlopen(),
            environ=env,
        )

        self.assertTrue((system_root / "etc/resolv.conf").is_symlink())
        self.assertIn("deb http://deb.debian.org/debian", (system_root / "etc/apt/sources.list").read_text(encoding="utf-8"))
        self.assertIn('"enabled": "disabled"', (system_root / "systemd/algo_app.service.json").read_text(encoding="utf-8"))

    def test_auto_update_disabled_system_policy_does_not_apply_new_operations(self):
        printer_root, system_root = _runtime_with_fake_system()
        _write_fake_service(system_root, "bluetooth", enabled="enabled", active="active")
        env = _env(printer_root, system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=io.StringIO("yes\nno\nno\n"),
            urlopen=moonraker_urlopen(),
            environ=env,
            system_options=SystemOptimizationCliOptions(skip_system_optimizations=True),
        )

        env[LOCK_HELD_ENV] = "1"
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=None,
            urlopen=moonraker_urlopen(),
            environ=env,
        )

        self.assertFalse((system_root / "etc/resolv.conf").is_symlink())
        self.assertEqual(json.loads((system_root / "systemd/bluetooth.json").read_text(encoding="utf-8"))["enabled"], "enabled")

    def test_auto_update_keep_ai_detection_reconciles_other_operations_only(self):
        printer_root, system_root = _runtime_with_fake_system()
        _write_fake_service(system_root, "algo_app.service", enabled="enabled", active="active")
        env = _env(printer_root, system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=io.StringIO("yes\nyes\nno\nno\nno\n"),
            urlopen=moonraker_urlopen(),
            environ=env,
        )

        (system_root / "etc/resolv.conf").unlink()
        (system_root / "etc/resolv.conf").write_text("nameserver 114.114.114.114\n", encoding="utf-8")
        _write_fake_service(system_root, "algo_app.service", enabled="enabled", active="active")
        env[LOCK_HELD_ENV] = "1"
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=None,
            urlopen=moonraker_urlopen(),
            environ=env,
        )

        self.assertTrue((system_root / "etc/resolv.conf").is_symlink())
        self.assertEqual(json.loads((system_root / "systemd/algo_app.service.json").read_text(encoding="utf-8"))["enabled"], "enabled")

    def test_auto_update_enabled_policy_applies_operation_missing_from_prior_ledger(self):
        printer_root, system_root = _runtime_with_fake_system()
        _write_fake_service(system_root, "bluetooth", enabled="enabled", active="active")
        env = _env(printer_root, system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=io.StringIO("yes\nyes\nno\nno\nno\n"),
            urlopen=moonraker_urlopen(),
            environ=env,
        )
        state_path = printer_root / manifest.state_file
        state = load_installed_state(state_path)
        ledger = dict(state.system_ledger)
        ledger["restore_preimages"] = dict(ledger["restore_preimages"])
        ledger["restore_preimages"].pop("service_bluetooth", None)
        ledger["actions"] = [action for action in ledger["actions"] if action["id"] != "service_bluetooth"]
        write_installed_state(state_path, type(state)(**{**state.__dict__, "system_ledger": ledger}))
        _write_fake_service(system_root, "bluetooth", enabled="enabled", active="active")

        env[LOCK_HELD_ENV] = "1"
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=None,
            urlopen=moonraker_urlopen(),
            environ=env,
        )

        self.assertEqual(json.loads((system_root / "systemd/bluetooth.json").read_text(encoding="utf-8"))["enabled"], "disabled")
        updated = load_installed_state(state_path)
        self.assertIn("service_bluetooth", updated.system_ledger["restore_preimages"])

    def test_real_root_file_restore_replaces_current_target_symlink(self):
        printer_root = copy_base_runtime()
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=build_env(printer_root, moonraker_url="http://moonraker.invalid"))
        with tempfile.TemporaryDirectory(prefix="system-preimage-", dir=REPO_ROOT) as tmp:
            tmp_path = Path(tmp)
            backup = tmp_path / "resolv.conf.backup"
            backup.write_text("nameserver 114.114.114.114\n", encoding="utf-8")
            restore_path = tmp_path / "resolv.conf"
            restore_path.symlink_to("current-resolv.conf")
            commands = []

            def run(command, **kwargs):
                commands.append(command)
                return subprocess.CompletedProcess(command, 0)

            _restore_file_preimage(
                {
                    "path": str(restore_path),
                    "exists": True,
                    "type": "file",
                    "mode": "0644",
                    "backup_path": str(backup),
                },
                paths=paths,
                root=Path("/"),
                sudo_password="qiditech",
                run=run,
            )

            install_commands = [command for command in commands if command[:7] == ["sudo", "-S", "-p", "", "install", "-D", "-m"]]
            mv_commands = [command for command in commands if command[:6] == ["sudo", "-S", "-p", "", "mv", "-f"]]
            rm_commands = [command for command in commands if command[:6] == ["sudo", "-S", "-p", "", "rm", "-f"]]
            self.assertEqual(len(install_commands), 1)
            self.assertEqual(install_commands[0][7], "0644")
            self.assertEqual(install_commands[0][8], str(backup))
            self.assertTrue(install_commands[0][9].startswith(f"{restore_path}.tltg-restore-"))
            self.assertEqual(len(mv_commands), 1)
            self.assertEqual(mv_commands[0][7], str(restore_path))
            self.assertTrue(mv_commands[0][6].startswith(f"{restore_path}.tltg-restore-"))
            self.assertNotIn(["sudo", "-S", "-p", "", "rm", "-f", str(restore_path)], rm_commands)

    def test_restore_service_skips_units_missing_at_restore_time(self):
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            if command[:2] == ["systemctl", "is-enabled"]:
                return subprocess.CompletedProcess(command, 1, stdout="not-found\n")
            if command[:2] == ["systemctl", "is-active"]:
                return subprocess.CompletedProcess(command, 3, stdout="unknown\n")
            return subprocess.CompletedProcess(command, 0)

        _restore_service(
            {"service": "xl2tpd", "exists": True, "enabled": "enabled", "active": "active"},
            root=Path("/"),
            sudo_password="qiditech",
            run=run,
        )

        self.assertEqual(commands, [["systemctl", "is-enabled", "xl2tpd"], ["systemctl", "is-active", "xl2tpd"]])

    def test_qidiclient_archive_validation_rejects_unsafe_members(self):
        cases = [
            _tar_member("/account/process.gif"),
            _tar_member("account/../evil.gif"),
            _tar_member("account/link.gif", tarfile.SYMTYPE),
            _tar_member("account/device.gif", tarfile.CHRTYPE),
            _tar_member("unexpected/process.gif"),
        ]
        for member in cases:
            with self.subTest(member=member.name, type=member.type):
                with self.assertRaises(SystemOptimizationError):
                    _validate_archive_members([member])

    def test_uninstall_can_restore_system_preimages(self):
        printer_root, system_root = _runtime_with_fake_system()
        env = _env(printer_root, system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        compatibility = load_supported_upgrade_sources(REPO_ROOT / "installer/supported_upgrade_sources.yaml")
        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=io.StringIO("yes\nyes\nyes\nno\nno\n"),
            urlopen=moonraker_urlopen(),
            environ=env,
        )
        run_uninstall(
            paths,
            manifest,
            compatibility,
            PlainReporter(io.StringIO()),
            input_stream=io.StringIO("yes\nyes\nno\n"),
            urlopen=moonraker_urlopen(),
            environ=env,
        )

        self.assertFalse((printer_root / manifest.state_file).exists())
        self.assertFalse((system_root / "etc/resolv.conf").is_symlink())
        self.assertEqual((system_root / "etc/resolv.conf").read_text(encoding="utf-8"), "nameserver 114.114.114.114\n")
        self.assertEqual((system_root / "etc/apt/sources.list").read_text(encoding="utf-8"), "old apt\n")


def _runtime_with_fake_system() -> tuple[Path, Path]:
    printer_root = copy_base_runtime()
    system_root = Path(tempfile.mkdtemp(prefix="system-root-"))
    (system_root / "etc/resolvconf/resolv.conf.d").mkdir(parents=True)
    (system_root / "etc/resolv.conf").write_text("nameserver 114.114.114.114\n", encoding="utf-8")
    (system_root / "etc/resolvconf/resolv.conf.d/head").write_text("nameserver 8.8.8.8\n", encoding="utf-8")
    (system_root / "etc/resolvconf/resolv.conf.d/tail").write_text("", encoding="utf-8")
    (system_root / "etc/apt").mkdir(parents=True)
    (system_root / "etc/apt/sources.list").write_text("old apt\n", encoding="utf-8")
    gif = system_root / "home/qidi/QIDI_Client/access/account/process.gif"
    gif.parent.mkdir(parents=True)
    gif.write_bytes(b"old")
    gif.chmod(0o600)
    return printer_root, system_root


def _env(printer_root: Path, system_root: Path) -> dict[str, str]:
    env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
    env[SYSTEM_ROOT_ENV] = str(system_root)
    return env


def _write_fake_service(
    system_root: Path,
    service: str,
    *,
    exists: bool = True,
    enabled: str = "enabled",
    active: str = "active",
) -> None:
    path = system_root / "systemd" / f"{service}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"exists": exists, "service": service, "enabled": enabled, "active": active}, sort_keys=True),
        encoding="utf-8",
    )


def _tar_member(name: str, member_type: bytes = tarfile.REGTYPE) -> tarfile.TarInfo:
    member = tarfile.TarInfo(name)
    member.type = member_type
    if member_type == tarfile.REGTYPE:
        member.size = 1
    return member


if __name__ == "__main__":
    unittest.main()
