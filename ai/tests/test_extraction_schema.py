import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mini_sorting_ai.extraction_schema import AIResponseError, validate_extraction  # noqa: E402


def good(**overrides):
    base = {
        "tracking_id": None,
        "recipient_name_raw": "คุณธนา ใจดี",
        "recipient_room": "202",
        "recipient_floor": None,
        "source_excerpt": "ผู้รับ: คุณธนา ใจดี ห้อง 202",
        "issues": [],
    }
    base.update(overrides)
    return base


class ExtractionSchemaTests(unittest.TestCase):
    def test_valid_payload_is_accepted_and_cleaned(self):
        out = validate_extraction(good(recipient_room="  202  ", tracking_id="   "))
        self.assertEqual(out["recipient_room"], "202")
        self.assertIsNone(out["tracking_id"])

    def test_all_nulls_are_allowed(self):
        out = validate_extraction(good(recipient_name_raw=None, recipient_room=None,
                                       source_excerpt=None))
        self.assertIsNone(out["recipient_room"])

    def test_missing_field_rejected(self):
        raw = good()
        del raw["issues"]
        with self.assertRaises(AIResponseError):
            validate_extraction(raw)

    def test_non_object_rejected(self):
        with self.assertRaises(AIResponseError):
            validate_extraction(["202"])

    def test_floor_as_text_rejected(self):
        with self.assertRaises(AIResponseError):
            validate_extraction(good(recipient_floor="สาม"))

    def test_floor_as_bool_rejected(self):
        with self.assertRaises(AIResponseError):
            validate_extraction(good(recipient_floor=True))

    def test_room_as_number_rejected(self):
        # ห้องต้องเป็น string เพื่อรักษาเลขศูนย์นำหน้า
        with self.assertRaises(AIResponseError):
            validate_extraction(good(recipient_room=202))

    def test_issues_must_be_list(self):
        with self.assertRaises(AIResponseError):
            validate_extraction(good(issues="ไม่มี"))


if __name__ == "__main__":
    unittest.main()
