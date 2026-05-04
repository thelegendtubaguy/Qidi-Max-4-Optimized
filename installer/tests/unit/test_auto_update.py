from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from installer.runtime.auto_update import (
    LOCK_HELD_ENV,
    SERVICE_NAME,
    TIMER_NAME,
    AutoUpdateError,
    enable_auto_updates,
    run_auto_update_check,
    state_path,
)
from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.naming import BUNDLE_ROOT_NAME
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


def _release_archive(payloads: dict[str, bytes]) -> bytes:
    archive_path = Path(tempfile.mkdtemp(prefix="auto-update-archive-")) / "bundle.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        root = tarfile.TarInfo(BUNDLE_ROOT_NAME)
        root.type = tarfile.DIRTYPE
        root.mode = 0o755
        archive.addfile(root)
        for relative_path, payload in payloads.items():
            info = tarfile.TarInfo(f"{BUNDLE_ROOT_NAME}/{relative_path}")
            info.size = len(payload)
            info.mode = 0o755 if relative_path.endswith(".sh") else 0o644
            archive.addfile(info, io.BytesIO(payload))
    return archive_path.read_bytes()


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

    def test_changed_checksum_downloads_verified_archive_and_runs_extracted_installer(self):
        printer_root = copy_base_runtime()
        bundle_root = Path(tempfile.mkdtemp(prefix="auto-update-bundle-")) / BUNDLE_ROOT_NAME
        bundle_root.mkdir()
        (bundle_root / "old.txt").write_text("old bundle", encoding="utf-8")
        archive = _release_archive({"install.sh": b"#!/bin/sh\nexit 0\n", "payload.txt": b"new bundle\n"})
        checksum = hashlib.sha256(archive).hexdigest()
        old_checksum = "1" * 64
        stream = io.StringIO()
        calls = []
        opened_urls = []

        def urlopen(url, timeout=0):
            opened_urls.append(str(url))
            if str(url).endswith(".sha256"):
                return _Response(f"{checksum}  tltg-optimized-macros.tar.gz\n".encode())
            if str(url).endswith(".tar.gz"):
                return _Response(archive)
            if "printer/objects/query" in str(url):
                payload = {"result": {"status": {"print_stats": {"state": "standby"}}}}
                return _Response(json.dumps(payload).encode())
            raise AssertionError(f"unexpected url: {url}")

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0)

        with moonraker_server("standby") as moonraker_url:
            paths = resolve_runtime_paths(
                bundle_root=bundle_root,
                environ=build_env(printer_root, moonraker_url=moonraker_url),
            )
            state_path(paths).parent.mkdir(parents=True, exist_ok=True)
            state_path(paths).write_text(json.dumps({"latest_checksum": old_checksum}), encoding="utf-8")
            result = run_auto_update_check(
                paths=paths,
                reporter=PlainReporter(stream),
                environ={
                    **build_env(printer_root, moonraker_url=moonraker_url),
                    "TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256",
                    "TLTG_AUTO_UPDATE_ARCHIVE_URL": "https://example.invalid/tltg-optimized-macros.tar.gz",
                },
                urlopen=urlopen,
                run=run,
            )

        self.assertEqual(result.action, "updated")
        self.assertEqual(json.loads(state_path(paths).read_text())["latest_checksum"], checksum)
        self.assertFalse(any("install-latest.sh" in url for url in opened_urls))
        self.assertEqual(calls[0][0], ["/bin/sh", str(bundle_root / "install.sh"), "--yes", "--plain"])
        self.assertEqual(calls[0][1]["cwd"], str(bundle_root))
        self.assertEqual(calls[0][1]["env"][LOCK_HELD_ENV], "1")
        self.assertFalse((bundle_root / "old.txt").exists())
        self.assertEqual((bundle_root / "payload.txt").read_text(encoding="utf-8"), "new bundle\n")
        self.assertIn("Auto-update complete.", stream.getvalue())

    def test_changed_checksum_mismatch_does_not_replace_bundle_or_state(self):
        printer_root = copy_base_runtime()
        bundle_root = Path(tempfile.mkdtemp(prefix="auto-update-bundle-")) / BUNDLE_ROOT_NAME
        bundle_root.mkdir()
        (bundle_root / "old.txt").write_text("old bundle", encoding="utf-8")
        checksum = "2" * 64
        old_checksum = "1" * 64
        stream = io.StringIO()
        calls = []

        def urlopen(url, timeout=0):
            if str(url).endswith(".sha256"):
                return _Response(f"{checksum}  tltg-optimized-macros.tar.gz\n".encode())
            if str(url).endswith(".tar.gz"):
                return _Response(b"not the expected archive bytes")
            if "printer/objects/query" in str(url):
                payload = {"result": {"status": {"print_stats": {"state": "standby"}}}}
                return _Response(json.dumps(payload).encode())
            raise AssertionError(f"unexpected url: {url}")

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0)

        with moonraker_server("standby") as moonraker_url:
            paths = resolve_runtime_paths(
                bundle_root=bundle_root,
                environ=build_env(printer_root, moonraker_url=moonraker_url),
            )
            state_path(paths).parent.mkdir(parents=True, exist_ok=True)
            state_path(paths).write_text(json.dumps({"latest_checksum": old_checksum}), encoding="utf-8")
            with self.assertRaises(AutoUpdateError):
                run_auto_update_check(
                    paths=paths,
                    reporter=PlainReporter(stream),
                    environ={
                        **build_env(printer_root, moonraker_url=moonraker_url),
                        "TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256",
                        "TLTG_AUTO_UPDATE_ARCHIVE_URL": "https://example.invalid/tltg-optimized-macros.tar.gz",
                    },
                    urlopen=urlopen,
                    run=run,
                )

        self.assertEqual(calls, [])
        self.assertEqual(json.loads(state_path(paths).read_text())["latest_checksum"], old_checksum)
        self.assertEqual((bundle_root / "old.txt").read_text(encoding="utf-8"), "old bundle")

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
