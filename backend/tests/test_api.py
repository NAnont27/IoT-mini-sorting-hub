"""Verify the relocated backend HTTP contract without MQTT or hardware workers."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.app import hub


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        example = Path(__file__).resolve().parents[1] / "config.example.json"
        (root / "config.json").write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        store = MagicMock()
        store.unfinished.return_value = []
        store.jobs.return_value = []
        store.influx_status = "TEST"
        patches = [patch.object(hub, "ROOT", root), patch.object(hub, "Store", return_value=store),
                   patch.object(hub.mqtt, "Client"), patch.object(hub.threading, "Thread"),
                   patch.dict(os.environ, {"MQTT_USER": "test", "MQTT_PASSWORD": "test"})]
        for mock_patch in patches:
            mock_patch.start()
            self.addCleanup(mock_patch.stop)
        app = hub.build_app()
        app.testing = True
        self.client = app.test_client()

    def test_root_is_api_metadata_not_old_template(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["service"], "mini-sorting-hub-backend")
        self.assertEqual(response.json["api_version"], 1)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_status_is_paused_and_reports_missing_hardware(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["paused"])
        self.assertTrue(response.json["readiness_errors"])
        self.assertEqual(response.json["config"]["mode"], "bench")

    def test_ai_pending_is_empty_without_active_job(self):
        self.assertEqual(self.client.get("/api/ai/pending").json, {"job": None})

    def test_resume_cannot_bypass_readiness(self):
        response = self.client.post("/api/control", json={"action": "resume"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json)

    def test_write_endpoints_require_json_objects(self):
        response = self.client.post("/api/control", data="[]", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "Request body must be a JSON object")

        response = self.client.post("/api/control", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "action is required")

    def test_settings_are_saved_under_backend_directory(self):
        response = self.client.post("/api/settings", json={"max_weight_g": 500, "max_height_mm": 200})
        self.assertEqual(response.status_code, 200)
        saved = json.loads((Path(self.directory.name) / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["max_weight_g"], 500)
        self.assertEqual(saved["max_height_mm"], 200)

    def test_settings_reject_unknown_fields(self):
        response = self.client.post("/api/settings", json={"bypass_interlock": True})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown settings", response.json["error"])

    def test_job_search_is_trimmed_and_bounded(self):
        response = self.client.get("/api/jobs?q=%20JOB-1%20")
        self.assertEqual(response.status_code, 200)
        hub.Store.return_value.jobs.assert_called_with("JOB-1")

        response = self.client.get("/api/jobs?q=" + "x" * 121)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
