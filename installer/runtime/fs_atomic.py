from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional


class FileMetadata:
    def __init__(self, mode: Optional[int], uid: Optional[int], gid: Optional[int]):
        self.mode = mode
        self.uid = uid
        self.gid = gid



def read_metadata(path: Path) -> FileMetadata:
    if not path.exists():
        return FileMetadata(mode=None, uid=None, gid=None)
    stat_result = path.stat()
    return FileMetadata(
        mode=stat_result.st_mode & 0o777,
        uid=getattr(stat_result, "st_uid", None),
        gid=getattr(stat_result, "st_gid", None),
    )



def atomic_write_bytes(path: Path, data: bytes, *, mode: Optional[int] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = read_metadata(path)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _apply_metadata(temp_path, metadata, default_mode=mode)
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()



def atomic_write_text(path: Path, text: str, *, mode: Optional[int] = None) -> None:
    atomic_write_bytes(path, text.encode("utf-8"), mode=mode)



def atomic_delete(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        raise IsADirectoryError(path)
    path.unlink()
    fsync_directory(path.parent)



def fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)



def _apply_metadata(path: Path, metadata: FileMetadata, *, default_mode: Optional[int]) -> None:
    mode = metadata.mode if metadata.mode is not None else default_mode
    if mode is not None:
        os.chmod(path, mode)
    if metadata.uid is not None and metadata.gid is not None:
        try:
            os.chown(path, metadata.uid, metadata.gid)
        except PermissionError:
            pass
