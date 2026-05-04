from __future__ import annotations

import io
import unittest

from installer.runtime import messages
from installer.runtime.interaction import maybe_restart_klipper, moonraker_restart_url


class _DummyReporter:
    def __init__(self):
        self.lines: list[str] = []
        self.prompt_prepared = 0

    def line(self, message: str = "") -> None:
        self.lines.append(message)

    def prepare_for_prompt(self) -> None:
        self.prompt_prepared += 1


class _DummyResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b"{}"


class InteractionTests(unittest.TestCase):
    def test_moonraker_restart_url_replaces_query_endpoint(self):
        self.assertEqual(
            moonraker_restart_url("http://127.0.0.1:7125/printer/objects/query?print_stats"),
            "http://127.0.0.1:7125/printer/restart",
        )
        self.assertEqual(
            moonraker_restart_url("http://127.0.0.1:7125/moonraker/printer/objects/query?print_stats"),
            "http://127.0.0.1:7125/moonraker/printer/restart",
        )

    def test_maybe_restart_klipper_accepts_yes_responses_and_posts_restart_request(self):
        for response in ("y\n", "yes\n"):
            with self.subTest(response=response.strip()):
                reporter = _DummyReporter()
                seen = {}

                def fake_urlopen(request, timeout=0):
                    seen["full_url"] = request.full_url
                    seen["method"] = request.get_method()
                    seen["timeout"] = timeout
                    return _DummyResponse()

                restarted = maybe_restart_klipper(
                    reporter=reporter,
                    input_stream=io.StringIO(response),
                    moonraker_query_url="http://127.0.0.1:7125/printer/objects/query?print_stats",
                    urlopen=fake_urlopen,
                )

                self.assertTrue(restarted)
                self.assertEqual(reporter.prompt_prepared, 1)
                self.assertEqual(seen["full_url"], "http://127.0.0.1:7125/printer/restart")
                self.assertEqual(seen["method"], "POST")
                self.assertEqual(seen["timeout"], 10)
                self.assertIn(messages.RESTARTING_KLIPPER, reporter.lines)
                self.assertIn(messages.KLIPPER_RESTARTED, reporter.lines)

    def test_maybe_restart_klipper_decline_prints_manual_restart_message(self):
        reporter = _DummyReporter()
        restarted = maybe_restart_klipper(
            reporter=reporter,
            input_stream=io.StringIO("no\n"),
            moonraker_query_url="http://127.0.0.1:7125/printer/objects/query?print_stats",
        )

        self.assertFalse(restarted)
        self.assertEqual(reporter.prompt_prepared, 1)
        self.assertIn(messages.RESTART_KLIPPER_TO_APPLY, reporter.lines)
