import json
import os
import unittest
from unittest.mock import patch

from app.time_context import TimeContextClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class TimeContextClientTests(unittest.TestCase):
    def setUp(self):
        self.env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)

    def test_successful_context_retrieval(self):
        os.environ["EDGE_TIME_URL"] = "http://pi4SSD:8095"

        payload = {
            "context_id": "123e4567-e89b-12d3-a456-426614174000",
            "capture_utc": "2026-09-17T15:00:00+00:00",
        }

        with patch(
            "app.time_context.urllib.request.urlopen",
            return_value=FakeResponse(payload),
        ):
            result = TimeContextClient().capture_context()

        self.assertEqual(result, payload)

    def test_post_method_and_url(self):
        os.environ["EDGE_TIME_URL"] = "http://pi4SSD:8095/"

        payload = {
            "context_id": "context-1",
            "capture_utc": "2026-09-17T15:00:00+00:00",
        }

        with patch(
            "app.time_context.urllib.request.urlopen",
            return_value=FakeResponse(payload),
        ) as urlopen:
            TimeContextClient().capture_context()

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://pi4SSD:8095/time/context")
        self.assertEqual(request.method, "POST")

    def test_timeout_returns_none(self):
        os.environ["EDGE_TIME_URL"] = "http://pi4SSD:8095"

        with patch(
            "app.time_context.urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            result = TimeContextClient().capture_context()

        self.assertIsNone(result)

    def test_missing_url_uses_host_default(self):
        os.environ.pop("EDGE_TIME_URL", None)

        with patch("app.time_context.socket.gethostname", return_value="pi4SSD"):
            client = TimeContextClient()

        self.assertEqual(client.url, "http://pi4SSD:8095")

    def test_empty_url_uses_host_default(self):
        os.environ["EDGE_TIME_URL"] = ""

        with patch("app.time_context.socket.gethostname", return_value="pi4nVME"):
            client = TimeContextClient()

        self.assertEqual(client.url, "http://pi4nVME:8095")

    def test_missing_context_id_returns_none(self):
        os.environ["EDGE_TIME_URL"] = "http://pi4SSD:8095"

        with patch(
            "app.time_context.urllib.request.urlopen",
            return_value=FakeResponse({"capture_utc": "2026-09-17T15:00:00+00:00"}),
        ):
            result = TimeContextClient().capture_context()

        self.assertIsNone(result)

    def test_missing_capture_utc_returns_none(self):
        os.environ["EDGE_TIME_URL"] = "http://pi4SSD:8095"

        with patch(
            "app.time_context.urllib.request.urlopen",
            return_value=FakeResponse({"context_id": "context-1"}),
        ):
            result = TimeContextClient().capture_context()

        self.assertIsNone(result)

    def test_empty_timeout_uses_default(self):
        os.environ["EDGE_TIME_URL"] = "http://pi4SSD:8095"
        os.environ["EDGE_TIME_TIMEOUT"] = ""

        client = TimeContextClient()

        self.assertEqual(client.timeout, 2.0)


if __name__ == "__main__":
    unittest.main()