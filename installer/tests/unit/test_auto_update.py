from __future__ import annotations

import io
import json
import subprocess
import unittest
from unittest.mock import patch

from installer.runtime.auto_update import (
    SERVICE_NAME,
    TIMER_NAME,
    AutoUpdateError,
    enable_auto_updates,
    run_auto_update_check,
    state_path,
)
from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.reporter import PlainReporter
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, moonraker_server


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class AutoUpdateTests(unittest.TestCase):
    def test_active_print_skips_update_before_running_installer(self):
        printer_root = copy_base_runtime()
        checksum = "a" * 64
        stream = io.StringIO()
        calls = []

        def urlopen(url, timeout=0):
            if str(url).endswith(".sha256"):
                return _Response(f"{checksum}  tltg-optimized-macros.tar.gz\n".encode())
            if "printer/objects/query" in str(url):
                payload = {"result": {"status": {"print_stats": {"state": "printing"}}}}
                return _Response(json.dumps(payload).encode())
            raise AssertionError(f"unexpected url: {url}")

        def run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)

        with moonraker_server("printing") as moonraker_url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=moonraker_url),
            )
            result = run_auto_update_check(
                paths=paths,
                reporter=PlainReporter(stream),
                environ={"TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256"},
                urlopen=urlopen,
                run=run,
            )

        self.assertEqual(result.action, "skipped-active-print")
        self.assertEqual(calls, [])
        self.assertIn("Auto-update skipped because a print is active or paused.", stream.getvalue())

    def test_checksum_fetch_failure_skips_without_running_installer(self):
        printer_root = copy_base_runtime()
        stream = io.StringIO()
        calls = []

        def urlopen(url, timeout=0):
            raise AutoUpdateError("fetch failed")

        def run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)

        with moonraker_server("standby") as moonraker_url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=moonraker_url),
            )
            result = run_auto_update_check(
                paths=paths,
                reporter=PlainReporter(stream),
                environ={"TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256"},
                urlopen=urlopen,
                run=run,
            )

        self.assertEqual(result.action, "skipped-checksum-unavailable")
        self.assertEqual(calls, [])
        self.assertFalse(state_path(paths).exists())
        self.assertIn(
            "Auto-update skipped because the latest release checksum could not be fetched.",
            stream.getvalue(),
        )

    def test_first_successful_check_initializes_state_without_running_installer(self):
        printer_root = copy_base_runtime()
        checksum = "c" * 64
        stream = io.StringIO()
        calls = []

        def urlopen(url, timeout=0):
            if str(url).endswith(".sha256"):
                return _Response(f"{checksum}  tltg-optimized-macros.tar.gz\n".encode())
            if "printer/objects/query" in str(url):
                payload = {"result": {"status": {"print_stats": {"state": "standby"}}}}
                return _Response(json.dumps(payload).encode())
            raise AssertionError(f"unexpected url: {url}")

        def run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)

        with moonraker_server("standby") as moonraker_url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=moonraker_url),
            )
            result = run_auto_update_check(
                paths=paths,
                reporter=PlainReporter(stream),
                environ={"TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256"},
                urlopen=urlopen,
                run=run,
            )

        self.assertEqual(result.action, "initialized")
        self.assertEqual(calls, [])
        self.assertEqual(json.loads(state_path(paths).read_text())["latest_checksum"], checksum)
        self.assertIn("Auto-update check: initialized latest release state.", stream.getvalue())

    def test_enable_auto_updates_installs_systemd_units_through_sudo(self):
        printer_root = copy_base_runtime()
        checksum = "b" * 64
        stream = io.StringIO()
        commands = []
        run_kwargs = []

        def urlopen(url, timeout=0):
            return _Response(f"{checksum}  tltg-optimized-macros.tar.gz\n".encode())

        def run(command, **kwargs):
            commands.append(command)
            run_kwargs.append(kwargs)
            return subprocess.CompletedProcess(command, 0)

        with moonraker_server("standby") as moonraker_url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=moonraker_url),
            )
            with patch("installer.runtime.auto_update.shutil.which", return_value="/usr/bin/tool"):
                enable_auto_updates(
                    paths=paths,
                    reporter=PlainReporter(stream),
                    environ={"TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256"},
                    urlopen=urlopen,
                    run=run,
                )

        self.assertEqual(json.loads(state_path(paths).read_text())["latest_checksum"], checksum)
        self.assertIn(["sudo", "-S", "-p", "", "-v"], commands)
        self.assertIn(["sudo", "-S", "-p", "", "systemctl", "daemon-reload"], commands)
        self.assertIn(["sudo", "-S", "-p", "", "systemctl", "enable", "--now", TIMER_NAME], commands)
        sudo_kwargs = [kwargs for command, kwargs in zip(commands, run_kwargs) if command[:4] == ["sudo", "-S", "-p", ""]]
        self.assertTrue(sudo_kwargs)
        self.assertTrue(all(kwargs.get("input") == "qiditech\n" for kwargs in sudo_kwargs))
        self.assertTrue(all(kwargs.get("text") is True for kwargs in sudo_kwargs))
        install_targets = [command[-1] for command in commands if command[:6] == ["sudo", "-S", "-p", "", "install", "-m"]]
        self.assertIn(f"/etc/systemd/system/{SERVICE_NAME}", install_targets)
        self.assertIn(f"/etc/systemd/system/{TIMER_NAME}", install_targets)
        self.assertIn("Auto-updates enabled.", stream.getvalue())

    def test_enable_auto_updates_prompts_when_default_sudo_password_fails(self):
        printer_root = copy_base_runtime()
        checksum = "d" * 64
        stream = io.StringIO()
        commands = []
        run_kwargs = []

        def urlopen(url, timeout=0):
            return _Response(f"{checksum}  tltg-optimized-macros.tar.gz\n".encode())

        def run(command, **kwargs):
            commands.append(command)
            run_kwargs.append(kwargs)
            if command == ["sudo", "-S", "-p", "", "-v"] and kwargs.get("input") == "qiditech\n":
                return subprocess.CompletedProcess(command, 1)
            return subprocess.CompletedProcess(command, 0)

        with moonraker_server("standby") as moonraker_url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=moonraker_url),
            )
            with patch("installer.runtime.auto_update.shutil.which", return_value="/usr/bin/tool"):
                enable_auto_updates(
                    paths=paths,
                    reporter=PlainReporter(stream),
                    input_stream=io.StringIO("correct-password\n"),
                    environ={"TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256"},
                    urlopen=urlopen,
                    run=run,
                )

        sudo_inputs = [
            kwargs.get("input")
            for command, kwargs in zip(commands, run_kwargs)
            if command[:4] == ["sudo", "-S", "-p", ""]
        ]
        self.assertGreaterEqual(len(sudo_inputs), 2)
        self.assertEqual(sudo_inputs[0], "qiditech\n")
        self.assertEqual(sudo_inputs[1], "correct-password\n")
        self.assertTrue(all(item == "correct-password\n" for item in sudo_inputs[1:]))
        output = stream.getvalue()
        self.assertIn("Initial sudo authentication failed.", output)
        self.assertIn("Enter sudo password to continue:", output)
        self.assertIn("Auto-updates enabled.", output)

    def test_enable_auto_updates_continues_when_checksum_seed_fails(self):
        printer_root = copy_base_runtime()
        stream = io.StringIO()
        commands = []
        run_kwargs = []

        def urlopen(url, timeout=0):
            raise AutoUpdateError("seed failed")

        def run(command, **kwargs):
            commands.append(command)
            run_kwargs.append(kwargs)
            return subprocess.CompletedProcess(command, 0)

        with moonraker_server("standby") as moonraker_url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=moonraker_url),
            )
            with patch("installer.runtime.auto_update.shutil.which", return_value="/usr/bin/tool"):
                enable_auto_updates(
                    paths=paths,
                    reporter=PlainReporter(stream),
                    environ={"TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256"},
                    urlopen=urlopen,
                    run=run,
                )

        self.assertFalse(state_path(paths).exists())
        self.assertIn(["sudo", "-S", "-p", "", "-v"], commands)
        sudo_kwargs = [kwargs for command, kwargs in zip(commands, run_kwargs) if command[:4] == ["sudo", "-S", "-p", ""]]
        self.assertTrue(sudo_kwargs)
        self.assertTrue(all(kwargs.get("input") == "qiditech\n" for kwargs in sudo_kwargs))
        self.assertIn("Could not seed the latest release checksum", stream.getvalue())
        self.assertIn("Auto-updates enabled.", stream.getvalue())
