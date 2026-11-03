from __future__ import annotations

import hashlib
import io
import shutil
import stat
import zipfile
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path, PurePosixPath

from .errors import InstallerError


# QIDI's Moonraker already uses msgspec for JSON and uvloop for its event loop when it can import them, but QIDI's
# virtualenv has neither. The pinned wheels are extracted into a package-owned directory that a .pth file adds to the
# virtualenv's import path, so nothing QIDI installed is replaced and removal restores stock Moonraker.
OPERATION = "moonraker_speedups"
PATH_OPERATION = "moonraker_speedups_path"
DESTINATION = "/home/qidi/tltg-moonraker-speedups"
# Updates stage the new packages beside the destination and keep the replaced ones until the host transaction ends.
STAGING = f"{DESTINATION}.tltg-staging"
PREVIOUS = f"{DESTINATION}.tltg-previous"
REMOVING = f"{DESTINATION}.tltg-removing"
# Marks the directory as package-owned and records the wheels it was extracted from.
MARKER = ".tltg-moonraker-speedups"
# The wheels are built for QIDI's Python 3.9 virtualenv.
SITE_PACKAGES = "/home/qidi/moonraker-env/lib/python3.9/site-packages"
PATH_FILE = f"{SITE_PACKAGES}/tltg-moonraker-speedups.pth"
RESTART_SERVICE = "moonraker.service"
# Package-created path files start with a marker line so later package versions replace earlier ones.
PATH_MARKER = "# tltg-optimized:moonraker-speedups\n"
PATH_CONTENT = PATH_MARKER + f"{DESTINATION}\n"
MAX_ENTRIES = 4096
MAX_BYTES = 64 * 1024 * 1024

ABSENT = "absent"
CURRENT = "current"
OUTDATED = "outdated"
FOREIGN = "foreign"


class MoonrakerSpeedupsError(InstallerError):
    pass


def patch_path_file(current: str) -> str:
    if current == "" or current.startswith(PATH_MARKER):
        return PATH_CONTENT
    raise InstallerError(f"Existing {PATH_FILE} is unrecognized and was preserved.")


def digest(sha256s: Iterable[str]) -> str:
    """Identify a set of wheels independently of their order."""
    return hashlib.sha256("\n".join(sorted(sha256s)).encode("ascii")).hexdigest()


def wheel_files(wheels: Iterable[tuple[Path, str]]) -> dict[str, str]:
    """Return the verified wheels' file hashes keyed by relative path."""
    files: dict[str, str] = {}
    for path, sha256 in wheels:
        for relative, file_hash in _wheel_files(str(path), sha256):
            if relative in files:
                raise MoonrakerSpeedupsError("Moonraker speedup wheels overlap.")
            files[relative] = file_hash
    return files


@lru_cache(maxsize=8)
def _wheel_files(path: str, sha256: str) -> tuple[tuple[str, str], ...]:
    data = _verified_bytes(Path(path), sha256)
    hashes: dict[str, str] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as wheel:
            members = wheel.infolist()
            _validate_members(members)
            for member in members:
                if not member.is_dir():
                    hashes[member.filename] = hashlib.sha256(wheel.read(member)).hexdigest()
    except (zipfile.BadZipFile, OSError) as exc:
        raise MoonrakerSpeedupsError("Moonraker speedup wheel could not be read.") from exc
    return tuple(sorted(hashes.items()))


def _verified_bytes(path: Path, sha256: str) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise MoonrakerSpeedupsError("Moonraker speedup wheel is missing from the package.") from exc
    if hashlib.sha256(data).hexdigest() != sha256:
        raise MoonrakerSpeedupsError("Moonraker speedup wheel checksum does not match the package manifest.")
    return data


def _validate_members(members: list[zipfile.ZipInfo]) -> None:
    if len(members) > MAX_ENTRIES or sum(member.file_size for member in members) > MAX_BYTES:
        raise MoonrakerSpeedupsError("Moonraker speedup wheel is too large.")
    for member in members:
        name = member.filename.rstrip("/") if member.is_dir() else member.filename
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or path.as_posix() != name
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.parts[0] == MARKER
        ):
            raise MoonrakerSpeedupsError("Moonraker speedup wheel contains an unsafe path.")
        kind = stat.S_IFMT(member.external_attr >> 16)
        if kind not in {0, stat.S_IFREG, stat.S_IFDIR} or (kind == stat.S_IFDIR) != member.is_dir():
            raise MoonrakerSpeedupsError("Moonraker speedup wheel contains an unsafe entry type.")


def installed_digest(destination: Path) -> str | None:
    """Return the wheel digest recorded in a package-owned directory, or None when it is not one."""
    marker = destination / MARKER
    if destination.is_symlink() or not destination.is_dir() or marker.is_symlink() or not marker.is_file():
        return None
    return marker.read_text(encoding="utf-8").strip()


def state(destination: Path, *, files: dict[str, str], wheels_digest: str) -> str:
    if not destination.exists() and not destination.is_symlink():
        return ABSENT
    installed = installed_digest(destination)
    if installed is None:
        return FOREIGN
    if installed != wheels_digest:
        return OUTDATED
    for relative, expected in files.items():
        target = destination / relative
        if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            return OUTDATED
    return CURRENT


def extract(wheels: list[tuple[Path, str]], target: Path) -> None:
    """Extract the verified wheels into a new directory, writing the marker last."""
    wheel_files(wheels)
    target.mkdir(mode=0o755)
    target.chmod(0o755)
    for path, sha256 in wheels:
        with zipfile.ZipFile(io.BytesIO(_verified_bytes(path, sha256))) as wheel:
            for member in wheel.infolist():
                destination = target / member.filename
                if member.is_dir():
                    destination.mkdir(mode=0o755, parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                with wheel.open(member) as source, destination.open("xb") as output:
                    shutil.copyfileobj(source, output)
                destination.chmod(0o755 if (member.external_attr >> 16) & 0o111 else 0o644)
    for directory in (item for item in target.rglob("*") if item.is_dir()):
        directory.chmod(0o755)
    marker = target / MARKER
    marker.write_text(f"{digest(sha256 for _, sha256 in wheels)}\n", encoding="utf-8")
    marker.chmod(0o644)


def remove(directory: Path, removing: Path) -> None:
    """Remove a package-owned directory, first moving it aside so Moonraker never imports a partial tree."""
    if installed_digest(directory) is None:
        raise MoonrakerSpeedupsError(f"{directory} is not a package-owned Moonraker speedups directory; preserving it.")
    discard(removing)
    directory.rename(removing)
    discard(removing)


def discard(directory: Path) -> None:
    """Delete a leftover staging, previous, or removal directory."""
    if directory.is_symlink():
        directory.unlink()
    elif directory.is_dir():
        shutil.rmtree(directory)
    elif directory.exists():
        directory.unlink()
