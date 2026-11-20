import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mini_sorting_ai.extraction import (  # noqa: E402
    STATUS_NO_TEXT, STATUS_OK, STATUS_SERVICE_ERROR, extract_recipient,
)
from mini_sorting_ai.gemini_client import MockClient  # noqa: E402

OCR = "ผู้ส่ง: ร้านทดสอบ ห้อง 502\nผู้รับ: คุณธนา ใจดี ห้อง 202"


def payload(**overrides):
    base = {
        "tracking_id": None,
        "recipient_name_raw": "คุณธนา ใจดี",
        "recipient_room": "202",
        "recipient_floor": None,
        "source_excerpt": "ผู้รับ: คุณธนา ใจดี ห้อง 202",
        "issues": [],
    }
    base.update(overrides)
    return json.dumps(base, ensure_ascii=False)


class ExtractRecipientTests(unittest.TestCase):
    def test_success_path_returns_ok_with_mock_source(self):
        r = extract_recipient(OCR, MockClient(response_text=payload()))
        self.assertEqual(r.status, STATUS_OK)
        self.assertEqual(r.source, "mock")
        self.assertEqual(r.extraction["recipient_room"], "202")
        self.assertEqual(r.grounding_issues, ())

    def test_empty_ocr_is_no_text_and_client_not_called(self):
        client = MockClient(response_text=payload())
        r = extract_recipient("   ", client)
        self.assertEqual((r.status, r.reason), (STATUS_NO_TEXT, "OCR_TEXT_EMPTY"))
        self.assertEqual(client.calls, 0)

    def test_api_down_is_service_error(self):
        r = extract_recipient(OCR, MockClient(error_reason="AI_UNAVAILABLE"))
        self.assertEqual((r.status, r.reason), (STATUS_SERVICE_ERROR, "AI_UNAVAILABLE"))
        self.assertIsNone(r.extraction)

    def test_malformed_json_is_service_error_invalid_response(self):
        r = extract_recipient(OCR, MockClient(response_text="{not json"))
        self.assertEqual((r.status, r.reason), (STATUS_SERVICE_ERROR, "AI_INVALID_RESPONSE"))

    def test_schema_invalid_is_service_error_not_resolve(self):
        r = extract_recipient(OCR, MockClient(response_text=payload(recipient_floor="สาม")))
        self.assertEqual((r.status, r.reason), (STATUS_SERVICE_ERROR, "AI_INVALID_RESPONSE"))
        self.assertIsNone(r.extraction)

    def test_non_object_json_is_invalid_response(self):
        r = extract_recipient(OCR, MockClient(response_text="[1, 2]"))
        self.assertEqual(r.reason, "AI_INVALID_RESPONSE")

    def test_invented_room_is_removed_and_flagged(self):
        r = extract_recipient(OCR, MockClient(response_text=payload(recipient_room="999")))
        self.assertEqual(r.status, STATUS_OK)
        self.assertIsNone(r.extraction["recipient_room"])
        self.assertIn("ROOM_NOT_IN_OCR", r.grounding_issues)

    def test_room_is_matched_as_whole_number_only(self):
        # "20" อยู่ในข้อความ "202" แต่ไม่ใช่เลขห้องทั้งก้อน
        r = extract_recipient(OCR, MockClient(response_text=payload(recipient_room="20")))
        self.assertIsNone(r.extraction["recipient_room"])

    def test_sender_room_is_not_promoted_to_recipient(self):
        # 502 อยู่ในข้อความ แต่เป็นห้องผู้ส่ง; ถ้า AI ตอบ 502 ต้องถูกตัดเพราะไม่ได้ปรากฏเป็นห้องผู้รับ
        # ผมตรวจแค่ว่าค่ามีอยู่ใน OCR; ความถูกต้องเรื่องผู้ส่งยังต้องพึ่ง prompt และ resolver
        r = extract_recipient(OCR, MockClient(response_text=payload(recipient_room="502")))
        self.assertEqual(r.extraction["recipient_room"], "502")

    def test_invented_name_is_removed(self):
        r = extract_recipient(OCR, MockClient(response_text=payload(recipient_name_raw="สมชาย ใจดี")))
        self.assertIsNone(r.extraction["recipient_name_raw"])
        self.assertIn("NAME_NOT_IN_OCR", r.grounding_issues)

    def test_name_spacing_difference_still_grounds(self):
        r = extract_recipient(OCR, MockClient(response_text=payload(recipient_name_raw="คุณธนาใจดี")))
        self.assertEqual(r.extraction["recipient_name_raw"], "คุณธนาใจดี")

    def test_invented_tracking_id_is_removed(self):
        r = extract_recipient(OCR, MockClient(response_text=payload(tracking_id="TH123")))
        self.assertIsNone(r.extraction["tracking_id"])
        self.assertIn("TRACKING_NOT_IN_OCR", r.grounding_issues)

    def test_fabricated_excerpt_is_removed(self):
        r = extract_recipient(OCR, MockClient(response_text=payload(source_excerpt="ข้อความที่ไม่มี")))
        self.assertIsNone(r.extraction["source_excerpt"])
        self.assertIn("EXCERPT_NOT_IN_OCR", r.grounding_issues)

    def test_floor_not_in_ocr_is_removed(self):
        r = extract_recipient(OCR, MockClient(response_text=payload(recipient_floor=7)))
        self.assertIsNone(r.extraction["recipient_floor"])

    def test_no_recipient_data_passes_as_ok_for_resolver_to_decide(self):
        r = extract_recipient(OCR, MockClient(response_text=payload(
            recipient_name_raw=None, recipient_room=None, source_excerpt=None)))
        self.assertEqual(r.status, STATUS_OK)
        self.assertIsNone(r.extraction["recipient_room"])


if __name__ == "__main__":
    unittest.main()
