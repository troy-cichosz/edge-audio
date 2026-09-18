import json
import logging
import os
import socket
import urllib.error
import urllib.request


class TimeContextClient:
    """Client for the hosting node's local edge-time service."""

    DEFAULT_EDGE_TIME_PORT = 8095

    def __init__(self):
        configured_url = os.environ.get("EDGE_TIME_URL", "").strip().rstrip("/")
        self.url = configured_url or (
            f"http://{socket.gethostname()}:{self.DEFAULT_EDGE_TIME_PORT}"
        )

        timeout_value = os.environ.get("EDGE_TIME_TIMEOUT", "").strip()
        self.timeout = float(timeout_value) if timeout_value else 2.0

    def capture_context(self):
        request = urllib.request.Request(
            f"{self.url}/time/context",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                context = json.loads(response.read().decode("utf-8"))

            if not isinstance(context, dict):
                raise ValueError("edge-time context response is not an object")

            if not context.get("context_id"):
                raise ValueError("edge-time context response is missing context_id")

            if not context.get("capture_utc"):
                raise ValueError("edge-time context response is missing capture_utc")

            return context

        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
            OSError,
        ) as exc:
            logging.warning(
                "Unable to acquire edge-time Capture Time Context: %s",
                exc,
            )
            return None