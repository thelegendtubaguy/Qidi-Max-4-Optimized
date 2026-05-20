from __future__ import annotations

import subprocess
import sys
import unittest

from installer.tests.helpers import REPO_ROOT


class GcodePathContractTests(unittest.TestCase):
    def test_gcode_path_contracts_and_generated_views_are_current(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "check_gcode_paths.py")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                "G-code path contract check failed. "
                "Run `python3 scripts/check_gcode_paths.py --write` after intentional path changes.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
