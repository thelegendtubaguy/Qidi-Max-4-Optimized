from __future__ import annotations

import sys

from .bootstrap import bundle_root_from_file, prepare_sys_path, validate_vendored_imports



def main(argv: list[str] | None = None) -> int:
    bundle_root = bundle_root_from_file(__file__)
    vendor_root = prepare_sys_path(bundle_root)
    validate_vendored_imports(bundle_root, vendor_root)
    from .cli import main as cli_main

    return cli_main(argv=argv, bundle_root=bundle_root)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
