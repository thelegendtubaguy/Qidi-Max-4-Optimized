from __future__ import annotations

import hashlib
import io
import shutil
import stat
import zipfile
from functools import lru_cache
from pathlib import Path, PurePosixPath

from .errors import InstallerError


# The project's Fluidd build is served by nginx from its own directory; QIDI's bundled Fluidd stays untouched as the rollback.
OPERATION = "fluidd_build"
DESTINATION = "/home/qidi/tltg-fluidd"
QIDI_ROOT = "/home/qidi/fluidd"
# Updates stage the new build beside the destination and keep the replaced build until the host transaction ends.
STAGING = f"{DESTINATION}.tltg-staging"
PREVIOUS = f"{DESTINATION}.tltg-previous"
REMOVING = f"{DESTINATION}.tltg-removing"
# Marks the directory as package-owned and records the archive it was extracted from.
MARKER = ".tltg-optimized-fluidd"
MAX_ENTRIES = 4096
MAX_BYTES = 128 * 1024 * 1024

ABSENT = "absent"
CURRENT = "current"
OUTDATED = "outdated"
FOREIGN = "foreign"


class FluiddBuildError(InstallerError):
    pass


def archive_files(archive: Path, sha256: str) -> dict[str, str]:
    """Return the verified archive's file hashes keyed by relative path."""
    return dict(_archive_files(str(archive), sha256))


@lru_cache(maxsize=4)
def _archive_files(archive: str, sha256: str) -> tuple[tuple[str, str], ...]:
    try:
        data = Path(archive).read_bytes()
    except OSError as exc:
        raise FluiddBuildError("Fluidd build is missing from the package.") from exc
    if hashlib.sha256(data).hexdigest() != sha256:
        raise FluiddBuildError("Fluidd build checksum does not match the package manifest.")
    hashes: dict[str, str] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive_file:
            members = archive_file.infolist()
            _validate_members(members)
            for member in members:
                if not member.is_dir():
                    hashes[member.filename] = hashlib.sha256(archive_file.read(member)).hexdigest()
    except (zipfile.BadZipFile, OSError) as exc:
        raise FluiddBuildError("Fluidd build archive could not be read.") from exc
    if "index.html" not in hashes:
        raise FluiddBuildError("Fluidd build archive has no index.html.")
    return tuple(sorted(hashes.items()))


def _validate_members(members: list[zipfile.ZipInfo]) -> None:
    if len(members) > MAX_ENTRIES or sum(member.file_size for member in members) > MAX_BYTES:
        raise FluiddBuildError("Fluidd build archive is too large.")
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
            raise FluiddBuildError("Fluidd build archive contains an unsafe path.")
        kind = stat.S_IFMT(member.external_attr >> 16)
        if kind not in {0, stat.S_IFREG, stat.S_IFDIR} or (kind == stat.S_IFDIR) != member.is_dir():
            raise FluiddBuildError("Fluidd build archive contains an unsafe entry type.")


def installed_sha256(destination: Path) -> str | None:
    """Return the archive checksum recorded in a package-owned build directory, or None when it is not one."""
    marker = destination / MARKER
    if destination.is_symlink() or not destination.is_dir() or marker.is_symlink() or not marker.is_file():
        return None
    return marker.read_text(encoding="utf-8").strip()


def state(destination: Path, *, hashes: dict[str, str], sha256: str) -> str:
    if not destination.exists() and not destination.is_symlink():
        return ABSENT
    installed = installed_sha256(destination)
    if installed is None:
        return FOREIGN
    if installed != sha256:
        return OUTDATED
    for relative, expected in hashes.items():
        target = destination / relative
        if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            return OUTDATED
    return CURRENT


def extract(archive: Path, sha256: str, target: Path) -> None:
    """Extract the verified archive into a new directory readable by nginx, writing the marker last."""
    archive_files(archive, sha256)
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise FluiddBuildError("Fluidd build checksum does not match the package manifest.")
    target.mkdir(mode=0o755)
    target.chmod(0o755)
    with zipfile.ZipFile(io.BytesIO(data)) as archive_file:
        for member in archive_file.infolist():
            path = target / member.filename
            if member.is_dir():
                path.mkdir(mode=0o755, parents=True, exist_ok=True)
                continue
            path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            with archive_file.open(member) as source, path.open("xb") as destination:
                shutil.copyfileobj(source, destination)
            path.chmod(0o644)
    for directory in (item for item in target.rglob("*") if item.is_dir()):
        directory.chmod(0o755)
    marker = target / MARKER
    marker.write_text(f"{sha256}\n", encoding="utf-8")
    marker.chmod(0o644)


def remove(directory: Path, removing: Path) -> None:
    """Remove a package-owned build, first moving it aside so nginx never serves a partial tree."""
    if installed_sha256(directory) is None:
        raise FluiddBuildError(f"{directory} is not a package-owned Fluidd build; preserving it.")
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
