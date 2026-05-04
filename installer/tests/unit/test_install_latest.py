from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from installer.tests.helpers import REPO_ROOT


SCRIPT = REPO_ROOT / "installer/release/install-latest.sh"


def _make_archive(root: Path, members: dict[str, bytes]) -> Path:
    archive_path = root / "bundle.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        directories = {Path(name).parent.as_posix() for name in members if Path(name).parent.as_posix() != "."}
        for directory in sorted(directories):
            info = tarfile.TarInfo(directory)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            archive.addfile(info)
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o755 if name.endswith(".sh") else 0o644
            archive.addfile(info, io.BytesIO(payload))
    checksum_path = root / "bundle.tar.gz.sha256"
    checksum_path.write_text(f"{hashlib.sha256(archive_path.read_bytes()).hexdigest()}  {archive_path.name}\n", encoding="utf-8")
    return archive_path


def _run_install_latest(home: Path, archive_path: Path, *, path: str | None = None) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "HOME": str(home),
        "TLTG_INSTALLER_ARCHIVE_URL": archive_path.as_uri(),
        "TLTG_INSTALLER_CHECKSUM_URL": (archive_path.parent / "bundle.tar.gz.sha256").as_uri(),
    }
    if path is not None:
        env["PATH"] = path
    return subprocess.run(["/bin/sh", str(SCRIPT), "--plain"], text=True, capture_output=True, env=env)


def _path_without_checksum_tools(root: Path) -> str:
    bin_dir = root / "bin"
    bin_dir.mkdir()
    for tool in ("curl", "tar", "mktemp", "rm", "mkdir", "mv", "grep", "find"):
        target = shutil.which(tool)
        if target is None:
            raise AssertionError(f"missing required test tool: {tool}")
        (bin_dir / tool).symlink_to(target)
    return str(bin_dir)


class InstallLatestTests(unittest.TestCase):
    def test_missing_checksum_tool_fails_closed(self):
        temp_root = Path(tempfile.mkdtemp(prefix="install-latest-"))
        home = temp_root / "home"
        home.mkdir()
        archive_path = _make_archive(
            temp_root,
            {"tltg-optimized-macros/install.sh": b"#!/bin/sh\ntouch \"$HOME/installed\"\n"},
        )

        result = _run_install_latest(
            home,
            archive_path,
            path=_path_without_checksum_tools(temp_root),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required tool: sha256sum or shasum", result.stderr)
        self.assertFalse((home / "installed").exists())
        self.assertFalse((home / "tltg-optimized-macros").exists())

    def test_invalid_archive_layout_fails_before_replacing_existing_install(self):
        temp_root = Path(tempfile.mkdtemp(prefix="install-latest-"))
        home = temp_root / "home"
        install_dir = home / "tltg-optimized-macros"
        install_dir.mkdir(parents=True)
        marker = install_dir / "keep.txt"
        marker.write_text("existing install", encoding="utf-8")
        archive_path = _make_archive(temp_root, {"unexpected-root/install.sh": b"#!/bin/sh\nexit 0\n"})

        result = _run_install_latest(home, archive_path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Archive does not use the expected tltg-optimized-macros/ root.", result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "existing install")

    def test_valid_archive_replaces_install_and_runs_installer(self):
        temp_root = Path(tempfile.mkdtemp(prefix="install-latest-"))
        home = temp_root / "home"
        install_dir = home / "tltg-optimized-macros"
        install_dir.mkdir(parents=True)
        (install_dir / "old.txt").write_text("old install", encoding="utf-8")
        archive_path = _make_archive(
            temp_root,
            {
                "tltg-optimized-macros/install.sh": b"#!/bin/sh\ntouch \"$HOME/installed\"\n",
                "tltg-optimized-macros/new.txt": b"new install\n",
            },
        )

        result = _run_install_latest(home, archive_path)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue((home / "installed").exists())
        self.assertFalse((install_dir / "old.txt").exists())
        self.assertEqual((install_dir / "new.txt").read_text(encoding="utf-8"), "new install\n")


if __name__ == "__main__":
    unittest.main()
