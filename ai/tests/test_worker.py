import json
import sys
import unittest
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from mini_sorting_ai import load_snapshot  # noqa: E402
from mini_sorting_ai.gemini_client import MockClient  # noqa: E402
from mini_sorting_ai.ocr import OcrLine  # noqa: E402
from mini_sorting_ai.worker import VisionWorker  # noqa: E402

CONFIG = json.loads((AI_ROOT / "config.example.json").read_text(encoding="utf-8"))
SNAP = load_snapshot(AI_ROOT / "fixtures" / "registry_demo.csv", CONFIG)
JOB = {"job_id": "JOB-0123456789ab", "vision_attempt": 1}
REPLY = json.dumps({"tracking_id": None, "recipient_name_raw": "คุณธนา ใจดี",
                    "recipient_room": "202", "recipient_floor": None,
                    "source_excerpt": "ผู้รับ: คุณธนา ใจดี ห้อง 202", "issues": []},
                   ensure_ascii=False)


class Response:
    def __init__(self, status=200, payload=None, content=b"jpeg", headers=None):
        self.status_code, self._payload = status, payload or {}
        self.content, self.headers, self.text = content, headers or {}, json.dumps(payload or {})

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeHttp:
    def __init__(self, capture_status=200):
        self.capture_status = capture_status
        self.results = []

    def get(self, url, timeout):
        return Response(payload={"job": dict(JOB)})

    def post(self, url, json, timeout):
        if url.endswith("/api/camera/capture"):
            return Response(self.capture_status, headers={"X-Image-Path": "/data/images/x.jpg"})
        self.results.append(json)
        return Response()


class FakeEngine:
    name = "fake"

    def run(self, image):
        return [OcrLine("ผู้ส่ง: ร้านทดสอบ ห้อง 502", 0.95, top=0),
                OcrLine("ผู้รับ: คุณธนา ใจดี ห้อง 202", 0.95, top=40)]


class WorkerTests(unittest.TestCase):
    def worker(self, http):
        return VisionWorker("http://hub", SNAP, MockClient(response_text=REPLY), FakeEngine(), http=http,
                            use_preprocess=False)

    def test_pending_job_is_captured_read_and_submitted_once(self):
        http = FakeHttp()
        worker = self.worker(http)
        envelope = worker.step()
        self.assertEqual((envelope["outcome"], envelope["target_bin"]), ("RESOLVED", "A"))
        self.assertEqual(envelope["artifacts"]["image_path"], "/data/images/x.jpg")
        self.assertIsNotNone(envelope["timings_ms"]["ocr"])
        self.assertIsNone(worker.step())  # same job/attempt is not processed twice
        self.assertEqual(len(http.results), 1)

    def test_capture_failure_reports_pipeline_error(self):
        http = FakeHttp(capture_status=503)
        envelope = self.worker(http).step()
        self.assertEqual((envelope["outcome"], envelope["reason_code"]), ("PIPELINE_ERROR", "CAPTURE_FAILED"))
        self.assertEqual(http.results[0]["vision_attempt"], 1)


if __name__ == "__main__":
    unittest.main()
