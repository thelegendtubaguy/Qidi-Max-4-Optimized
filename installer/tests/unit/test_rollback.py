from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from installer.runtime.rollback import RollbackJournal


class RollbackTests(unittest.TestCase):
    def test_rollback_failure_writes_recovery_sentinel(self):
        temp_root = Path(tempfile.mkdtemp(prefix="rollback-test-"))
        sentinel = temp_root / ".sentinel"
        path = temp_root / "printer.cfg"
        path.write_text("before\n", encoding="utf-8")
        journal = RollbackJournal(sentinel)
        journal.track_file(path)
        journal.note_write()
        path.write_text("after\n", encoding="utf-8")
        with mock.patch.object(journal, "rollback", side_effect=RuntimeError("boom")):
            with self.assertRaises(Exception):
                journal.rollback_or_raise(
                    RuntimeError("write failed"),
                    backup_label="backup",
                    backup_zip_path=temp_root / "backup.zip",
                )
        self.assertTrue(sentinel.exists())
