import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from mini_sorting_ai import load_snapshot  # noqa: E402
from mini_sorting_ai.cli import main  # noqa: E402
from mini_sorting_ai.gemini_client import MockClient  # noqa: E402
from mini_sorting_ai.pipeline import process_ocr_text  # noqa: E402

CONFIG = json.loads((AI_ROOT / "config.example.json").read_text(encoding="utf-8"))
SNAP = load_snapshot(AI_ROOT / "fixtures" / "registry_demo.csv", CONFIG)
OCR = "ผู้ส่ง: ร้านทดสอบ ห้อง 502\nผู้รับ: คุณธนา ใจดี ห้อง 202"


def reply(**o):
    base = {"tracking_id": None, "recipient_name_raw": "คุณธนา ใจดี", "recipient_room": "202",
            "recipient_floor": None, "source_excerpt": "ผู้รับ: คุณธนา ใจดี ห้อง 202", "issues": []}
    base.update(o)
    return json.dumps(base, ensure_ascii=False)


class PipelineTests(unittest.TestCase):
    def run_pipeline(self, ocr, client):
        return process_ocr_text("JOB-0001", ocr, SNAP, client)

    def test_recipient_resolves_to_bin_a(self):
        e = self.run_pipeline(OCR, MockClient(response_text=reply()))
        self.assertEqual((e["outcome"], e["target_bin"], e["resolved_floor"]), ("RESOLVED", "A", 2))
        self.assertEqual(e["extraction_source"], "mock")

    def test_empty_ocr_requests_retry_capture(self):
        e = self.run_pipeline("  ", MockClient(response_text=reply()))
        self.assertEqual((e["outcome"], e["target_bin"]), ("RETRY_CAPTURE", None))

    def test_service_down_is_service_error_not_hold(self):
        e = self.run_pipeline(OCR, MockClient(error_reason="AI_UNAVAILABLE"))
        self.assertEqual((e["outcome"], e["target_bin"]), ("SERVICE_ERROR", None))
        self.assertEqual(e["reason_code"], "AI_UNAVAILABLE")

    def test_invalid_json_is_service_error_not_resolve(self):
        e = self.run_pipeline(OCR, MockClient(response_text="{oops"))
        self.assertEqual((e["outcome"], e["reason_code"]), ("SERVICE_ERROR", "AI_INVALID_RESPONSE"))

    def test_invented_room_does_not_resolve(self):
        # AI ตอบห้องที่ไม่มีใน OCR จึงถูกตัดเป็น null และไม่มีข้อมูลผู้รับเหลือ -> ขอถ่ายซ้ำ (ไม่ใช่ A/B)
        e = self.run_pipeline(OCR, MockClient(response_text=reply(recipient_room="999", recipient_name_raw=None)))
        self.assertEqual(e["outcome"], "RETRY_CAPTURE")
        self.assertIsNone(e["target_bin"])
        self.assertIn("ROOM_NOT_IN_OCR", e["grounding_issues"])

    def test_conflict_between_name_and_room_holds(self):
        e = self.run_pipeline("ผู้รับ: คุณธนา ใจดี ห้อง 502",
                              MockClient(response_text=reply(recipient_room="502",
                                                             source_excerpt="ผู้รับ: คุณธนา ใจดี ห้อง 502")))
        self.assertEqual(e["reason_code"], "HOLD_CONFLICT_ROOM_NAME")


class CliTests(unittest.TestCase):
    def run_cli(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(argv)
        return code, json.loads(buf.getvalue())

    def test_cli_with_mock_response_file(self):
        code, out = self.run_cli(["--ocr", str(AI_ROOT / "fixtures" / "ocr_demo.txt"),
                                  "--job-id", "JOB-0001",
                                  "--mock-response", str(AI_ROOT / "fixtures" / "mock_response_demo.json")])
        self.assertEqual(code, 0)
        self.assertEqual((out["outcome"], out["target_bin"]), ("RESOLVED", "A"))
        self.assertEqual(out["extraction_source"], "mock")

    def test_cli_service_error_exits_1(self):
        # ผลตอบ AI ที่ไม่ใช่ JSON -> SERVICE_ERROR -> exit code 1
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            fh.write("{not json")
        self.addCleanup(Path(fh.name).unlink, missing_ok=True)
        code, out = self.run_cli(["--ocr", str(AI_ROOT / "fixtures" / "ocr_demo.txt"),
                                  "--job-id", "JOB-0001", "--mock-response", fh.name])
        self.assertEqual(code, 1)
        self.assertEqual((out["outcome"], out["reason_code"]), ("SERVICE_ERROR", "AI_INVALID_RESPONSE"))

    def test_cli_missing_ocr_file_is_pipeline_error(self):
        code, out = self.run_cli(["--ocr", "no-such-file.txt", "--job-id", "JOB-0001"])
        self.assertEqual(code, 2)
        self.assertEqual(out["outcome"], "PIPELINE_ERROR")

    def test_cli_without_key_is_service_error(self):
        import os
        saved = {k: os.environ.pop(k, None) for k in ("GEMINI_API_KEY", "GEMINI_MODEL")}
        try:
            code, out = self.run_cli(["--ocr", str(AI_ROOT / "fixtures" / "ocr_demo.txt"),
                                      "--job-id", "JOB-0001"])
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
        self.assertEqual(code, 1)
        self.assertEqual(out["outcome"], "SERVICE_ERROR")
        self.assertEqual(out["reason_code"], "AI_NOT_CONFIGURED_KEY")


if __name__ == "__main__":
    unittest.main()
