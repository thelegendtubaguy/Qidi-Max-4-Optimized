from __future__ import annotations

import io
import unittest

from installer.runtime import messages
from installer.runtime.reporter import RichReporter
from installer.tests.helpers import REPO_ROOT


class _TtyStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


class RichReporterTests(unittest.TestCase):
    def test_rich_reporter_renders_live_counters_and_prompt_panel(self):
        stream = _TtyStringIO()
        reporter = RichReporter(stream, bundle_root=REPO_ROOT)

        reporter.status(messages.PERFORMING_PREFLIGHT_CHECKS)
        reporter.emit_install_preflight_counters(
            files=(1, 2),
            sections=(2, 2),
            lines=(3, 3),
            patch_targets=(4, 5),
        )
        reporter.emit_prompt(question="Proceed with install?", instruction="Type Y or Yes to continue.")

        output = stream.getvalue()
        self.assertIn("QIDI Max 4 Optimized installer", output)
        self.assertIn("stage 3/5", output)
        self.assertIn("Preflight checks", output)
        self.assertIn("patch targets", output)
        self.assertIn("4/5", output)
        self.assertIn("Confirmation required", output)
        self.assertIn("Proceed with install?", output)
        self.assertIn("Type Y or Yes to continue.", output)

    def test_rich_reporter_renders_restore_backup_table(self):
        stream = _TtyStringIO()
        reporter = RichReporter(stream, bundle_root=REPO_ROOT)

        reporter.emit_backup_choices(
            (
                (1, "2026-04-27 12:34:56 UTC", "backup-one", "/tmp/backup-one.zip"),
                (2, "2026-04-27 12:35:56 UTC", "backup-two", "/tmp/backup-two.zip"),
            )
        )
        reporter.emit_restore_warning(config_path="/home/qidi/printer_data/config")

        output = stream.getvalue()
        self.assertIn("Available installer backups", output)
        self.assertIn("backup-one", output)
        self.assertIn("/tmp/backup-two.zip", output)
        self.assertIn("Restore warning:", output)
        self.assertIn("Warning: restore will overwrite current config changes under", output)
        self.assertIn("This helper does not clear the recovery sentinel.", output)


if __name__ == "__main__":
    unittest.main()
