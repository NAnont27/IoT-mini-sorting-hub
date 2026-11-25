import sys
import tempfile
import unittest
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from mini_sorting_ai.ocr import OcrError, OcrLine, parse_paddle_output, read_text  # noqa: E402


class FakeEngine:
    name = "fake"

    def __init__(self, lines):
        self.lines = lines

    def run(self, image):
        return self.lines


BOX = lambda x, y: [[x, y], [x + 50, y], [x + 50, y + 10], [x, y + 10]]  # noqa: E731


class ParseTests(unittest.TestCase):
    def test_paddle_2x_shape(self):
        raw = [[[BOX(0, 40), ("ผู้รับ: คุณธนา ใจดี", 0.93)], [BOX(0, 0), ("ผู้ส่ง: ร้านทดสอบ", 0.88)]]]
        lines = parse_paddle_output(raw)
        self.assertEqual([line.text for line in lines], ["ผู้รับ: คุณธนา ใจดี", "ผู้ส่ง: ร้านทดสอบ"])
        self.assertEqual(lines[0].top, 40.0)

    def test_paddle_2x_no_text_page_is_none(self):
        self.assertEqual(parse_paddle_output([None]), [])

    def test_paddle_3x_dict_shape(self):
        raw = [{"rec_texts": ["ห้อง 202"], "rec_scores": [0.9], "rec_polys": [BOX(5, 20)]}]
        lines = parse_paddle_output(raw)
        self.assertEqual(len(lines), 1)
        self.assertEqual((lines[0].text, lines[0].top, lines[0].left), ("ห้อง 202", 20.0, 5.0))


class ReadTextTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        handle.close()
        self.image = Path(handle.name)

    def tearDown(self):
        self.image.unlink(missing_ok=True)

    def test_orders_top_to_bottom_and_drops_low_confidence(self):
        engine = FakeEngine([OcrLine("ผู้รับ: คุณธนา ใจดี ห้อง 202", 0.9, top=50),
                             OcrLine("ผู้ส่ง: ร้านทดสอบ ห้อง 502", 0.95, top=10),
                             OcrLine("###", 0.2, top=30)])
        result = read_text(self.image, engine, use_preprocess=False)
        self.assertEqual(result.text, "ผู้ส่ง: ร้านทดสอบ ห้อง 502\nผู้รับ: คุณธนา ใจดี ห้อง 202")
        self.assertEqual(result.dropped_low_confidence, 1)
        self.assertEqual(result.engine, "fake")
        self.assertIsNotNone(result.ocr_ms)

    def test_no_text_gives_empty_string_for_retry_capture(self):
        result = read_text(self.image, FakeEngine([]), use_preprocess=False)
        self.assertEqual(result.text, "")
        self.assertIsNone(result.mean_confidence)

    def test_missing_image_is_ocr_error(self):
        with self.assertRaises(OcrError):
            read_text(self.image.with_name("missing-label.jpg"), FakeEngine([]))


if __name__ == "__main__":
    unittest.main()
