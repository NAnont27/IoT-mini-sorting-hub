import json
import sys
import tempfile
import unittest
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from mini_sorting_ai import (  # noqa: E402
    AIResponseError, RegistryError, load_snapshot, pipeline_error,
    resolve_recipient, service_error,
)

CONFIG = json.loads((AI_ROOT / "config.example.json").read_text(encoding="utf-8"))
REGISTRY = AI_ROOT / "fixtures" / "registry_demo.csv"


def ext(room=None, name=None, floor=None, tracking=None, excerpt=None):
    return {
        "tracking_id": tracking,
        "recipient_name_raw": name,
        "recipient_room": room,
        "recipient_floor": floor,
        "source_excerpt": excerpt,
        "issues": [],
    }


class ResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = load_snapshot(REGISTRY, CONFIG)

    def resolve(self, extraction):
        return resolve_recipient("JOB-T", extraction, self.snap)

    def test_room_202_resolves_to_floor_2_bin_a(self):
        r = self.resolve(ext(room="202"))
        self.assertEqual((r["outcome"], r["target_bin"], r["resolved_floor"]), ("RESOLVED", "A", 2))
        self.assertEqual(r["reason_code"], "RESOLVED_ROOM")

    def test_room_502_resolves_to_bin_b(self):
        r = self.resolve(ext(room="502"))
        self.assertEqual((r["target_bin"], r["resolved_floor"]), ("B", 5))

    def test_valid_floor_text_only_resolves(self):
        r = self.resolve(ext(floor=4))
        self.assertEqual((r["outcome"], r["target_bin"], r["reason_code"]), ("RESOLVED", "B", "RESOLVED_FLOOR_TEXT"))

    def test_floor_text_not_in_valid_floors_holds(self):
        r = self.resolve(ext(floor=9))
        self.assertEqual((r["outcome"], r["target_bin"]), ("HOLD", "HOLD"))
        self.assertEqual(r["reason_code"], "HOLD_FLOOR_NOT_IN_VALID_FLOORS")

    def test_room_302_is_not_inferred_as_floor_3_when_unknown(self):
        r = self.resolve(ext(room="999"))
        self.assertEqual(r["outcome"], "HOLD")
        self.assertEqual(r["reason_code"], "HOLD_ROOM_NOT_IN_REGISTRY")

    def test_unique_name_resolves_with_prefix_and_spacing(self):
        r = self.resolve(ext(name="  คุณธนา   ใจดี "))
        self.assertEqual((r["outcome"], r["resolved_room"], r["target_bin"]), ("RESOLVED", "202", "A"))
        self.assertEqual(r["reason_code"], "RESOLVED_NAME")

    def test_duplicate_name_without_room_holds(self):
        r = self.resolve(ext(name="กิตติ ทดสอบ"))
        self.assertEqual(r["reason_code"], "HOLD_NAME_AMBIGUOUS")

    def test_duplicate_name_with_room_narrows_to_one_person(self):
        r = self.resolve(ext(name="กิตติ ทดสอบ", room="602"))
        self.assertEqual((r["outcome"], r["resolved_room"], r["target_bin"]), ("RESOLVED", "602", "B"))
        self.assertEqual(r["reason_code"], "RESOLVED_ROOM_AND_NAME")

    def test_name_and_room_conflict_holds(self):
        r = self.resolve(ext(name="ธนา ใจดี", room="502"))
        self.assertEqual(r["reason_code"], "HOLD_CONFLICT_ROOM_NAME")

    def test_room_and_floor_text_conflict_holds(self):
        r = self.resolve(ext(room="202", floor=3))
        self.assertEqual(r["reason_code"], "HOLD_CONFLICT_FLOOR")

    def test_similar_name_is_not_fuzzy_matched(self):
        r = self.resolve(ext(name="ธนา ใจ"))
        self.assertEqual(r["outcome"], "HOLD")
        self.assertEqual(r["reason_code"], "HOLD_NO_RESOLVABLE_FLOOR")

    def test_sender_room_in_excerpt_is_ignored(self):
        # เลขห้องผู้ส่งอยู่ใน excerpt เท่านั้น ไม่มีผู้รับ -> ต้องขอถ่ายซ้ำ ไม่คัดตามห้อง 502
        r = self.resolve(ext(excerpt="ผู้ส่ง: ร้านทดสอบ ห้อง 502"))
        self.assertEqual((r["outcome"], r["target_bin"]), ("RETRY_CAPTURE", None))

    def test_empty_tracking_id_does_not_block_resolution(self):
        r = self.resolve(ext(room="202", tracking=None))
        self.assertEqual(r["outcome"], "RESOLVED")
        self.assertIsNone(r["tracking_id"])

    def test_insufficient_data_requests_retry(self):
        r = self.resolve(ext())
        self.assertEqual((r["outcome"], r["target_bin"], r["reason_code"]),
                         ("RETRY_CAPTURE", None, "RETRY_NO_RECIPIENT_FIELDS"))

    def test_schema_invalid_response_is_rejected(self):
        bad = ext(room="202")
        bad["recipient_floor"] = "สาม"
        with self.assertRaises(AIResponseError):
            self.resolve(bad)

    def test_missing_field_is_rejected(self):
        bad = ext(room="202")
        del bad["issues"]
        with self.assertRaises(AIResponseError):
            self.resolve(bad)

    def test_service_error_envelope_has_no_bin(self):
        r = service_error("JOB-T", self.snap, "AI_UNAVAILABLE")
        self.assertEqual((r["outcome"], r["target_bin"]), ("SERVICE_ERROR", None))
        self.assertEqual(r["reason_code"], "AI_UNAVAILABLE")

    def test_pipeline_error_envelope_has_no_bin(self):
        r = pipeline_error("JOB-T", self.snap, "CONFIG_INVALID")
        self.assertEqual((r["outcome"], r["target_bin"]), ("PIPELINE_ERROR", None))


class RegistryTests(unittest.TestCase):
    def write_csv(self, body):
        fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        fh.write("resident_id,full_name,room,floor\n" + body)
        fh.close()
        self.addCleanup(Path(fh.name).unlink, missing_ok=True)
        return fh.name

    def test_duplicate_resident_id_rejected(self):
        with self.assertRaises(RegistryError):
            load_snapshot(self.write_csv("R1,ก,202,2\nR1,ข,302,3\n"), CONFIG)

    def test_room_mapped_to_two_floors_rejected(self):
        with self.assertRaises(RegistryError):
            load_snapshot(self.write_csv("R1,ก,202,2\nR2,ข,202,3\n"), CONFIG)

    def test_blank_required_field_rejected(self):
        with self.assertRaises(RegistryError):
            load_snapshot(self.write_csv("R1,,202,2\n"), CONFIG)

    def test_floor_outside_valid_floors_rejected(self):
        with self.assertRaises(RegistryError):
            load_snapshot(self.write_csv("R1,ก,902,9\n"), CONFIG)

    def test_two_residents_same_room_same_floor_allowed(self):
        snap = load_snapshot(self.write_csv("R1,ก,202,2\nR2,ข,202,2\n"), CONFIG)
        self.assertEqual(snap.room_floor["202"], 2)

    def test_a_max_floor_must_be_valid(self):
        bad = dict(CONFIG, a_max_floor=99)
        with self.assertRaises(RegistryError):
            load_snapshot(REGISTRY, bad)

    def test_room_keeps_leading_zero_as_string(self):
        snap = load_snapshot(self.write_csv("R1,ก,0102,1\n"), dict(CONFIG, valid_floors=[1, 2, 3]))
        self.assertIn("0102", snap.room_floor)


if __name__ == "__main__":
    unittest.main()
