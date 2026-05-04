from __future__ import annotations

import unittest
from unittest import mock

from installer.runtime.rollback import RollbackJournal
from installer.tests.helpers import temp_path


class RollbackTests(unittest.TestCase):
    def test_rollback_failure_writes_recovery_sentinel(self):
        temp_root = temp_path("rollback-test-")
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
