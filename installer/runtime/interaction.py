from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, TextIO

from . import messages

UrlOpenFn = Callable[..., object]

_YES_RESPONSES = {"y", "yes"}


def confirm_yes(
    *,
    reporter,
    input_stream: TextIO | None,
    question: str,
    instruction: str,
    cancel_message: str,
) -> bool:
    if input_stream is None:
        return True
    reporter.prepare_for_prompt()
    reporter.line(question)
    reporter.line(instruction)
    response = input_stream.readline().strip().lower()
    if response in _YES_RESPONSES:
        return True
    reporter.line(cancel_message)
    return False



def maybe_restart_klipper(
    *,
    reporter,
    input_stream: TextIO | None,
    moonraker_query_url: str,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> bool:
    if input_stream is None:
        reporter.line(messages.RESTART_KLIPPER_TO_APPLY)
        return False
    if not confirm_yes(
        reporter=reporter,
        input_stream=input_stream,
        question=messages.RESTART_KLIPPER_PROMPT,
        instruction=messages.RESTART_KLIPPER_PROMPT_INSTRUCTION,
        cancel_message=messages.RESTART_KLIPPER_TO_APPLY,
    ):
        return False
    reporter.line(messages.RESTARTING_KLIPPER)
    request = urllib.request.Request(
        moonraker_restart_url(moonraker_query_url),
        data=b"",
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            response.read()
    except (OSError, urllib.error.URLError, ValueError):
        reporter.line(messages.COULD_NOT_RESTART_KLIPPER)
        return False
    reporter.line(messages.KLIPPER_RESTARTED)
    return True



def moonraker_restart_url(moonraker_query_url: str) -> str:
    parts = urllib.parse.urlsplit(moonraker_query_url)
    prefix = ""
    if parts.path.endswith("/printer/objects/query"):
        prefix = parts.path[: -len("/printer/objects/query")]
    restart_path = f"{prefix}/printer/restart" if prefix else "/printer/restart"
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, restart_path, "", ""))
