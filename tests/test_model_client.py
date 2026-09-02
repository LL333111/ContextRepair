import json
import unittest
import urllib.error
from unittest.mock import patch

from contextrepair.agent.model_client import ModelClient


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback

    def read(self):
        return json.dumps({"ok": True}).encode()


class ModelClientTests(unittest.TestCase):
    @patch("contextrepair.agent.model_client.time.sleep")
    @patch("contextrepair.agent.model_client.urllib.request.urlopen")
    def test_post_retries_transient_connection_failure(self, urlopen, sleep):
        urlopen.side_effect = [
            urllib.error.URLError(ConnectionResetError("reset")),
            FakeResponse(),
        ]
        result = ModelClient._post("https://example.test", {}, {"value": 1})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
