from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


class VendoredImportError(ImportError):
    pass


MODULE_NOT_VENDORED = "Module is not available from installer/runtime/vendor."


def bundle_root_from_runtime() -> Path:
    return Path(__file__).resolve().parents[2]


def vendor_root_from_bundle_root(bundle_root: Path) -> Path:
    return bundle_root / "installer" / "runtime" / "vendor"


def default_vendor_root() -> Path:
    return vendor_root_from_bundle_root(bundle_root_from_runtime())


def ensure_vendor_root_on_sys_path(vendor_root: Path) -> None:
    vendor_entry = str(vendor_root)
    if vendor_entry in sys.path:
        sys.path.remove(vendor_entry)
    sys.path.insert(0, vendor_entry)


def purge_non_vendored_module(module_name: str, vendor_root: Path) -> None:
    prefix = module_name + "."
    for key, module in list(sys.modules.items()):
        if key != module_name and not key.startswith(prefix):
            continue
        origin = _module_origin(module)
        if origin is None or not _is_relative_to(origin, vendor_root):
            del sys.modules[key]


def import_required_vendored_module(module_name: str, vendor_root: Path) -> ModuleType:
    ensure_vendor_root_on_sys_path(vendor_root)
    purge_non_vendored_module(module_name, vendor_root)
    module = importlib.import_module(module_name)
    origin = _module_origin(module)
    if origin is None or not _is_relative_to(origin, vendor_root):
        raise VendoredImportError(MODULE_NOT_VENDORED)
    return module


def find_optional_vendored_module_origin(module_name: str, vendor_root: Path) -> Path | None:
    ensure_vendor_root_on_sys_path(vendor_root)
    purge_non_vendored_module(module_name, vendor_root)
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return None
    origin = _spec_origin(spec)
    if origin is None or not _is_relative_to(origin, vendor_root):
        return None
    return origin


def import_optional_vendored_module(module_name: str, vendor_root: Path) -> ModuleType:
    origin = find_optional_vendored_module_origin(module_name, vendor_root)
    if origin is None:
        raise VendoredImportError(MODULE_NOT_VENDORED)
    module = importlib.import_module(module_name)
    loaded_origin = _module_origin(module)
    if loaded_origin is None or not _is_relative_to(loaded_origin, vendor_root):
        raise VendoredImportError(MODULE_NOT_VENDORED)
    return module


def _module_origin(module: ModuleType) -> Path | None:
    filename = getattr(module, "__file__", None)
    if not filename:
        return None
    try:
        return Path(filename).resolve()
    except OSError:
        return None


def _spec_origin(spec) -> Path | None:
    origin = getattr(spec, "origin", None)
    if origin and origin != "built-in":
        try:
            return Path(origin).resolve()
        except OSError:
            return None
    search_locations = getattr(spec, "submodule_search_locations", None) or ()
    for location in search_locations:
        try:
            return Path(location).resolve()
        except OSError:
            continue
    return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
