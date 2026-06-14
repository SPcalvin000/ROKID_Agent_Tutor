import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integration.learning_state_client import (
    build_frame_request,
    build_learning_state_summary,
    fetch_lsg_status,
    is_lsg_enabled,
    normalize_base_url,
    send_frame_to_lsg,
)


class LearningStateClientTests(unittest.TestCase):
    def test_is_lsg_enabled_defaults_to_false(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_lsg_enabled())

    def test_normalize_base_url_strips_trailing_slash(self):
        self.assertEqual(normalize_base_url("http://127.0.0.1:5000/"), "http://127.0.0.1:5000")

    def test_build_frame_request_constructs_frame_payload(self):
        payload = build_frame_request(b"abc", mime_type="image/webp", task_mode="reading")

        self.assertIn("data", payload)
        self.assertIn("files", payload)
        self.assertEqual(payload["data"]["task_mode"], "reading")
        self.assertIn("timestamp_ms", payload["data"])
        self.assertIn("frame", payload["files"])
        filename, file_bytes, mime_type = payload["files"]["frame"]
        self.assertEqual(filename, "lsg-bridge-frame.webp")
        self.assertEqual(file_bytes, b"abc")
        self.assertEqual(mime_type, "image/webp")

    def test_build_learning_state_summary_extracts_core_fields(self):
        summary = build_learning_state_summary(
            {
                "interpreted_state": "Stable learning state",
                "interpreted_confidence": 0.81,
                "state_hint": "stable",
                "interpreted_evidence": ["scene_lock", "low_switching"],
            }
        )

        self.assertEqual(summary["interpreted_state"], "Stable learning state")
        self.assertEqual(summary["interpreted_confidence"], 0.81)
        self.assertEqual(summary["state_hint"], "stable")
        self.assertEqual(summary["interpreted_evidence"], ["scene_lock", "low_switching"])

    def test_send_frame_to_lsg_returns_none_on_request_failure(self):
        with patch.dict(os.environ, {"ENABLE_LSG_BRIDGE": "true"}, clear=True):
            with patch("integration.learning_state_client._requests_post", side_effect=Exception("boom")):
                self.assertIsNone(send_frame_to_lsg(b"abc"))

    def test_fetch_lsg_status_returns_none_on_non_200(self):
        mock_response = Mock(status_code=503)
        mock_response.json.return_value = {"status": "error"}
        with patch.dict(os.environ, {"ENABLE_LSG_BRIDGE": "true"}, clear=True):
            with patch("integration.learning_state_client._requests_get", return_value=mock_response):
                self.assertIsNone(fetch_lsg_status())


if __name__ == "__main__":
    unittest.main()
