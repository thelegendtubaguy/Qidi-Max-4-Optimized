from __future__ import annotations

import ast
import hashlib
from functools import lru_cache

from .errors import InstallerError


# Scoped admission preserves the vendor module and rejects unreviewed metadata changes.
STOCK_CLASS_SHA256 = "16374372639ce76bede68cc35caa68ac93cd7e7d15ab9213a01c0c4fd721eaee"
PATCHED_CLASS_SHA256 = "57988d33edebac362199aa3d7e830c8621aab0e1902d6be99d2605621ec4b0a3"
METASCAN_STOCK_SHA256 = "e11adab7f2771ed11b4c28f5403e103db4513aed4c118cbf45d7fc7612adb8b3"
METASCAN_PATCHED_SHA256 = "5e639a40f028a4789d7077337b6ee322e8c4efcb82bfceeb27c17e78341c8ded"
OPERATION = "moonraker_file_manager_3mf_cache"


class MoonrakerFileManagerError(InstallerError):
    pass


def _source_span(text: str, class_name: str, method_name: str | None = None) -> tuple[int, int, str]:
    try:
        nodes = [node for node in ast.parse(text).body if isinstance(node, ast.ClassDef) and node.name == class_name]
    except SyntaxError as exc:
        raise MoonrakerFileManagerError("Moonraker file_manager.py is not valid Python.") from exc
    if len(nodes) != 1:
        raise MoonrakerFileManagerError(f"Moonraker {class_name} class is not recognized.")
    if method_name is not None:
        nodes = [node for node in nodes[0].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name]
        if len(nodes) != 1:
            raise MoonrakerFileManagerError(f"Moonraker {class_name}.{method_name} is not recognized.")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    first_line = min([node.lineno, *(item.lineno for item in node.decorator_list)])
    start = sum(map(len, lines[:first_line - 1]))
    end = sum(map(len, lines[:node.end_lineno]))
    return start, end, text[start:end]


@lru_cache(maxsize=4)
def patch_file_manager(text: str) -> str:
    return _patch_metadata_storage(_patch_metascan(text))


def _patch_metascan(text: str) -> str:
    start, end, source = _source_span(text, "FileManager", "_handle_metascan_request")
    newline = "\r\n" if "\r\n" in source else "\n"
    if newline == "\r\n" and "\n" in source.replace("\r\n", ""):
        raise MoonrakerFileManagerError("Moonraker metascan has mixed line endings; preserving the source.")
    original = source.replace("\r\n", "\n")
    digest = hashlib.sha256(original.encode()).hexdigest()
    if digest == METASCAN_PATCHED_SHA256:
        return text
    if digest != METASCAN_STOCK_SHA256:
        raise MoonrakerFileManagerError("Moonraker metascan does not match the reviewed source; preserving file_manager.py.")
    anchor = '            gcpath = pathlib.Path(self.file_paths["gcodes"]).joinpath(requested_file)\n'
    branch = '''\
            if gcpath.suffix.lower() == ".3mf":
                root = pathlib.Path(self.file_paths["gcodes"])
                if not gcpath.resolve().is_relative_to(root.resolve()):
                    raise self.server.error("3MF rescan path is outside the gcodes root", 403)
                self.check_reserved_path(gcpath, False)
                if not gcpath.is_file():
                    raise self.server.error(f"File '{requested_file}' does not exist", 404)
                requested_file = os.path.relpath(gcpath, root)
                path_info = self.get_path_info(gcpath, "gcodes")
                path_info['_3mf_path'] = str(gcpath)
                metadata = await self.gcode_metadata.rescan_3mf_metadata(requested_file, path_info)
                metadata['filename'] = requested_file
                return metadata
'''
    if original.count(anchor) != 1:
        raise MoonrakerFileManagerError("Moonraker metascan patch did not match its admitted source.")
    patched = original.replace(anchor, anchor + branch, 1)
    if hashlib.sha256(patched.encode()).hexdigest() != METASCAN_PATCHED_SHA256:
        raise MoonrakerFileManagerError("Moonraker metascan patch failed its output integrity check.")
    result = text[:start] + patched.replace("\n", newline) + text[end:]
    compile(result, "file_manager.py", "exec")
    return result


def _patch_metadata_storage(text: str) -> str:
    start, end, source = _source_span(text, "MetadataStorage")
    newline = "\r\n" if "\r\n" in source else "\n"
    if newline == "\r\n" and "\n" in source.replace("\r\n", ""):
        raise MoonrakerFileManagerError("Moonraker MetadataStorage has mixed line endings; preserving the source.")
    original = source.replace("\r\n", "\n")
    digest = hashlib.sha256(original.encode()).hexdigest()
    if digest == PATCHED_CLASS_SHA256:
        return text
    if digest != STOCK_CLASS_SHA256:
        raise MoonrakerFileManagerError("Moonraker MetadataStorage does not match the reviewed QIDI source; preserving file_manager.py.")
    replacements = {
        "_has_valid_data": '''\
    def _tltg_3mf_extractor_stamp(self):
        # Detect extractor replacement as well as edits, without rereading it per archive.
        try:
            st = os.stat(METADATA_SCRIPT)
        except OSError:
            return None
        return [st.st_mtime_ns, st.st_ctime_ns, st.st_size, self.enable_object_proc]

    def _has_valid_data(self, fname, path_info):
        if path_info.get('ufp_path') is not None or path_info.get('_tltg_force_rescan'):
            return False
        mdata = self.metadata.get(fname, {})
        if path_info.get('_3mf_path') is not None:
            stamp = self._tltg_3mf_extractor_stamp()
            if stamp is None or mdata.get('tltg_3mf_extractor') != stamp:
                return False
        return all(mdata.get(field) == path_info.get(field) and field in mdata
                   for field in ('size', 'modified'))
''',
        "_process_3mf_metadata_update": "",
        "parse_3mf_thumbnail": '''\
    def parse_3mf_thumbnail(self, fname, path_info):
        # Uploads and filesystem observation share the same cache and queue worker.
        return self.parse_metadata(fname, path_info)

    async def rescan_3mf_metadata(self, fname, path_info):
        # Join pending work rather than running a second extractor for the same archive.
        if fname in self.pending_requests:
            request, event = self.pending_requests[fname]
            request['_tltg_force_rescan'] = True
        else:
            request = dict(path_info, _tltg_force_rescan=True)
            event = self.parse_3mf_thumbnail(fname, request)
        await event.wait()
        metadata = self.get(fname)
        if not request.get('_tltg_extraction_succeeded') or metadata is None:
            raise self.server.error(f"Failed to parse metadata for file '{fname}'", 500)
        return metadata
''',
    }
    lines = original.splitlines(keepends=True)
    cls = ast.parse(original).body[0]
    for method in reversed(cls.body):
        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name in replacements:
            lines[method.lineno - 1:method.end_lineno] = [replacements[method.name]]
    patched = ''.join(lines)
    edits = (
        ("                else:\n                    break\n            else:\n                if ufp_path is None:\n", "                else:\n                    path_info['_tltg_extraction_succeeded'] = True\n                    break\n            else:\n                if ufp_path is None and not path_info.get('_tltg_force_rescan'):\n"),
        ("ext = os.path.splitext(fname)[1]\n", "ext = os.path.splitext(fname)[1].lower()\n"),
        ("list(self.pending_requests.items())[0]", "next(iter(self.pending_requests.items()))"),
        ("            if self._has_valid_data(fname, path_info):\n                mevt.set()", "            if self._has_valid_data(fname, path_info):\n                self.pending_requests.pop(fname, None)\n                mevt.set()"),
        ('        # Escape single quotes in the file name so that it may be\n', '        extractor_stamp = self._tltg_3mf_extractor_stamp() if _3mf_path is not None else None\n        # Escape single quotes in the file name so that it may be\n'),
        ("        metadata.update({'print_start_time': None, 'job_id': None})\n", "        metadata.update({'print_start_time': None, 'job_id': None})\n        if _3mf_path is not None and extractor_stamp is not None:\n            metadata['tltg_3mf_extractor'] = extractor_stamp\n"),
    )
    for before, after in edits:
        if patched.count(before) != 1:
            raise MoonrakerFileManagerError("Moonraker cache patch did not match its admitted source.")
        patched = patched.replace(before, after, 1)
    if hashlib.sha256(patched.encode()).hexdigest() != PATCHED_CLASS_SHA256:
        raise MoonrakerFileManagerError("Moonraker cache patch failed its output integrity check.")
    result = text[:start] + patched.replace("\n", newline) + text[end:]
    compile(result, "file_manager.py", "exec")
    return result
