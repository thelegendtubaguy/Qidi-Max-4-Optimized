from __future__ import annotations

import hashlib
from pathlib import Path

from .fs_atomic import atomic_delete, atomic_write_bytes, fsync_directory
from .models import DriftRecord, InstalledState
from .rollback import RollbackJournal



def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()



def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())



def collect_tree_hashes(root: Path, *, relative_to: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    result: dict[str, str] = {}
    for item in sorted(root.rglob("*")):
        if item.is_file():
            result[item.relative_to(relative_to).as_posix()] = sha256_file(item)
    return result



def collect_source_hashes(
    source_root: Path,
    *,
    destination_root: Path,
    relative_to: Path,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in sorted(source_root.rglob("*")):
        if item.is_file():
            rel = item.relative_to(source_root)
            runtime_path = destination_root / rel
            result[runtime_path.relative_to(relative_to).as_posix()] = sha256_file(item)
    return result



def detect_install_managed_tree_drift(
    *,
    destination_root: Path,
    printer_data_root: Path,
    prior_state: InstalledState | None,
    source_hashes: dict[str, str],
) -> tuple[DriftRecord, ...]:
    if prior_state is None:
        return ()
    prior_hashes = {item.path: item.sha256 for item in prior_state.managed_tree.files}
    current_hashes = collect_tree_hashes(destination_root, relative_to=printer_data_root)
    drift: list[DriftRecord] = []
    for path, current_hash in sorted(current_hashes.items()):
        prior_hash = prior_hashes.get(path)
        source_hash = source_hashes.get(path)
        if prior_hash == current_hash:
            continue
        if source_hash is not None and current_hash == source_hash:
            continue
        drift.append(DriftRecord(path=path, sha256_before_remove=current_hash))
    extra_paths = sorted(set(prior_hashes) - set(current_hashes))
    for path in extra_paths:
        # Missing files are not local drift; they are handled by mirror convergence.
        pass
    return tuple(drift)



def detect_uninstall_managed_tree_drift(
    *,
    destination_root: Path,
    printer_data_root: Path,
    state: InstalledState,
) -> tuple[DriftRecord, ...]:
    prior_hashes = {item.path: item.sha256 for item in state.managed_tree.files}
    current_hashes = collect_tree_hashes(destination_root, relative_to=printer_data_root)
    drift: list[DriftRecord] = []
    for path, current_hash in sorted(current_hashes.items()):
        prior_hash = prior_hashes.get(path)
        if prior_hash == current_hash:
            continue
        drift.append(DriftRecord(path=path, sha256_before_remove=current_hash))
    return tuple(drift)



def mirror_tree(
    *, source_root: Path, destination_root: Path, journal: RollbackJournal
) -> None:
    journal.track_tree(destination_root)
    source_files = {
        item.relative_to(source_root): item
        for item in sorted(source_root.rglob("*"))
        if item.is_file()
    }
    destination_files = {
        item.relative_to(destination_root): item
        for item in sorted(destination_root.rglob("*"))
        if item.is_file()
    } if destination_root.exists() else {}

    for rel_path, destination_file in sorted(destination_files.items(), reverse=True):
        if rel_path in source_files:
            continue
        journal.note_write()
        atomic_delete(destination_file)

    current_dirs = [item for item in destination_root.rglob("*") if item.is_dir()] if destination_root.exists() else []
    for directory in sorted(current_dirs, key=lambda item: len(item.parts), reverse=True):
        if any(directory.iterdir()):
            continue
        directory.rmdir()
        fsync_directory(directory.parent)

    for rel_path, source_file in source_files.items():
        destination_file = destination_root / rel_path
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        source_bytes = source_file.read_bytes()
        if destination_file.exists() and destination_file.is_file() and destination_file.read_bytes() == source_bytes:
            continue
        journal.note_write()
        atomic_write_bytes(destination_file, source_bytes, mode=0o644)



def remove_tree(root: Path, journal: RollbackJournal) -> None:
    journal.track_tree(root)
    if not root.exists():
        return
    for item in sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True):
        if item.is_file():
            journal.note_write()
            atomic_delete(item)
        elif item.is_dir() and not any(item.iterdir()):
            journal.note_write()
            item.rmdir()
            fsync_directory(item.parent)
    if root.exists() and not any(root.iterdir()):
        journal.note_write()
        root.rmdir()
        fsync_directory(root.parent)
