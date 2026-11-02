from __future__ import annotations

import os
import pwd
import shutil
import sys
from pathlib import Path

PRINTER_DATA_ROOT_ENV = "TLTG_OPTIMIZED_PRINTER_DATA_ROOT"
DEFAULT_PRINTER_DATA_ROOT = "/home/qidi/printer_data"
BUNDLE_DIRECTORY = "tltg-optimized-macros"


class BootstrapError(RuntimeError):
    pass



def run_as_printer_user(bundle_root: Path) -> Path:
    """Switch a root run to the user who owns printer_data; return the bundle to run.

    Every file the installer writes then gets the owner and mode an
    unprivileged run gives it, and privileged steps use sudo as they always
    do. A bundle that user can't reach, such as one unpacked under /root by
    `sudo`, is copied into the user's home first. Runs only stdlib code, so
    nothing in the bundle is compiled or written as root.
    """
    if os.geteuid() != 0:
        return bundle_root
    printer_data = Path(os.environ.get(PRINTER_DATA_ROOT_ENV, DEFAULT_PRINTER_DATA_ROOT))
    try:
        owner = pwd.getpwuid(printer_data.stat().st_uid)
    except (OSError, KeyError) as exc:
        raise BootstrapError(f"Could not find the user that owns {printer_data}.") from exc
    if owner.pw_uid == 0:
        raise BootstrapError(f"{printer_data} is owned by root; it should belong to the printer's user, such as qidi.")
    home = Path(owner.pw_dir)
    if not bundle_root.resolve().is_relative_to(home.resolve()):
        bundle_root = _copy_bundle(bundle_root, home / BUNDLE_DIRECTORY, owner)
    os.chdir(bundle_root)
    os.initgroups(owner.pw_name, owner.pw_gid)
    os.setgid(owner.pw_gid)
    os.setuid(owner.pw_uid)
    os.environ.update(HOME=owner.pw_dir, USER=owner.pw_name, LOGNAME=owner.pw_name)
    return bundle_root



def _copy_bundle(source: Path, target: Path, owner: pwd.struct_passwd) -> Path:
    staging = target.with_name(f".{target.name}.{os.getpid()}")
    previous = target.with_name(f".{target.name}.{os.getpid()}.previous")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(source, staging, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
    for directory, dirnames, filenames in os.walk(staging):
        os.lchown(directory, owner.pw_uid, owner.pw_gid)
        for name in dirnames + filenames:
            os.lchown(os.path.join(directory, name), owner.pw_uid, owner.pw_gid)
    if target.exists() or target.is_symlink():
        os.replace(target, previous)
    os.replace(staging, target)
    shutil.rmtree(previous, ignore_errors=True)
    return target



def bundle_root_from_file(file_path: str) -> Path:
    return Path(file_path).resolve().parents[2]



def prepare_sys_path(bundle_root: Path) -> Path:
    vendor_root = bundle_root / "installer" / "runtime" / "vendor"
    cwd = Path.cwd().resolve()
    cleaned = []
    for entry in sys.path:
        if not entry:
            continue
        try:
            resolved = Path(entry).resolve()
        except OSError:
            cleaned.append(entry)
            continue
        if resolved == cwd:
            continue
        if str(resolved) in {str(bundle_root), str(vendor_root)}:
            continue
        cleaned.append(entry)
    sys.path[:] = [str(vendor_root), str(bundle_root)] + cleaned
    return vendor_root



def validate_vendored_imports(vendor_root: Path) -> None:
    from installer.runtime.vendor_imports import (
        VendoredImportError,
        import_required_vendored_module,
    )

    try:
        import_required_vendored_module("yaml", vendor_root)
    except VendoredImportError as exc:
        raise BootstrapError(
            "Vendored yaml import did not resolve inside installer/runtime/vendor."
        ) from exc


def main(argv: list[str] | None = None) -> int:
    bundle_root = bundle_root_from_file(__file__)
    try:
        bundle_root = run_as_printer_user(bundle_root)
    except (BootstrapError, OSError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    try:
        vendor_root = prepare_sys_path(bundle_root)
        validate_vendored_imports(vendor_root)
        from installer.runtime.cli import main as cli_main
    except KeyboardInterrupt:
        sys.stderr.write("Interrupted. No further installer actions will run.\n")
        return 130
    except (BootstrapError, ImportError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    try:
        return cli_main(argv=argv, bundle_root=bundle_root)
    except KeyboardInterrupt:
        sys.stderr.write("Interrupted. No further installer actions will run.\n")
        return 130



if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
