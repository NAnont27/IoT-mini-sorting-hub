"""ภาพฉลาก -> ข้อความ OCR ด้วย PaddleOCR (D025) + OpenCV preprocess

- ผลลัพธ์ (OcrResult.text) ส่งต่อให้ pipeline.process_ocr_text() ได้ทันที
- import paddleocr/cv2 แบบ lazy: เทสต์และเครื่องที่ไม่มีไลบรารียัง import โมดูลนี้ได้
- รองรับผลทั้ง PaddleOCR 2.x (.ocr) และ 3.x (.predict) เพราะยังไม่ได้ล็อกเวอร์ชันบน Pi
- ไม่ส่งภาพออกนอกเครื่อง; Gemini ได้เฉพาะข้อความที่ OCR อ่านได้
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path


class OcrError(RuntimeError):
    """OCR ใช้ไม่ได้ (ไลบรารี/โมเดล/ไฟล์ภาพ) — ไม่ใช่กรณีอ่านแล้วไม่เจอข้อความ"""


@dataclass
class OcrLine:
    text: str
    confidence: float
    top: float = 0.0   # y บนสุดของกรอบ ใช้เรียงบรรทัดบนลงล่าง
    left: float = 0.0


@dataclass
class OcrResult:
    text: str
    lines: list[OcrLine] = field(default_factory=list)
    dropped_low_confidence: int = 0
    engine: str = "paddleocr"
    preprocess_ms: float | None = None
    ocr_ms: float | None = None

    @property
    def mean_confidence(self) -> float | None:
        if not self.lines:
            return None
        return round(sum(line.confidence for line in self.lines) / len(self.lines), 3)


def preprocess(image_path: Path, *, min_width: int = 1280):
    """อ่านภาพด้วย OpenCV, ขยายภาพเล็ก, เพิ่ม contrast (CLAHE) บนช่องความสว่าง

    คืน ndarray แบบ BGR ที่ PaddleOCR รับได้ ถ้าไม่มี cv2 จะคืน path เดิม (PaddleOCR อ่านไฟล์เองได้)
    """
    try:
        import cv2
    except ImportError:
        return str(image_path)
    image = cv2.imread(str(image_path))
    if image is None:
        raise OcrError(f"อ่านไฟล์ภาพไม่ได้: {image_path}")
    height, width = image.shape[:2]
    if width < min_width:
        scale = min_width / width
        image = cv2.resize(image, (min_width, int(height * scale)), interpolation=cv2.INTER_CUBIC)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, a, b = cv2.split(lab)
    lightness = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lightness)
    return cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2BGR)


def _as_list(value) -> list:
    return [] if value is None else list(value)


def _box_top_left(box) -> tuple[float, float]:
    try:
        points = [(float(p[0]), float(p[1])) for p in box]
        return min(y for _, y in points), min(x for x, _ in points)
    except (TypeError, ValueError, IndexError):
        return 0.0, 0.0


def parse_paddle_output(raw) -> list[OcrLine]:
    """แปลงผล PaddleOCR ทั้งสองรุ่นเป็น OcrLine

    3.x: list ของผล (dict-like) ที่มี rec_texts / rec_scores / rec_polys (หรือ dt_polys)
    2.x: [[ [box, (text, score)], ... ]]  หรือ [None] เมื่อไม่เจอข้อความ
    """
    lines: list[OcrLine] = []
    for page in raw or []:
        if page is None:
            continue
        data = getattr(page, "json", None)
        if isinstance(data, dict):  # 3.x result object: {"res": {...}}
            page = data.get("res", data)
        if isinstance(page, dict) or hasattr(page, "get"):
            # ค่าอาจเป็น numpy array: ห้ามใช้ `x or []` (truth value กำกวม)
            texts = _as_list(page.get("rec_texts"))
            scores = _as_list(page.get("rec_scores"))
            polys = page.get("rec_polys")
            if polys is None:
                polys = page.get("dt_polys")
            polys = _as_list(polys) or [None] * len(texts)
            for text, score, poly in zip(texts, scores, polys):
                top, left = _box_top_left(poly)
                lines.append(OcrLine(str(text), float(score), top, left))
            continue
        for item in page:  # 2.x
            try:
                box, (text, score) = item[0], item[1]
            except (TypeError, ValueError, IndexError):
                continue
            top, left = _box_top_left(box)
            lines.append(OcrLine(str(text), float(score), top, left))
    return lines


class PaddleOcrEngine:
    """PaddleOCR ภาษาไทย (โมเดล th รู้จักตัวอักษรอังกฤษ/ตัวเลขด้วย) โหลดครั้งเดียวต่อ process"""

    name = "paddleocr"

    def __init__(self, lang: str = "th"):
        self.lang = lang
        self._ocr = None

    def _load(self):
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OcrError("ไม่พบ paddleocr: pip install paddleocr (และ paddlepaddle)") from exc
        try:  # 3.x
            # enable_mkldnn=False: paddlepaddle 3.3 CPU + oneDNN ล้มด้วย
            # "ConvertPirAttribute2RuntimeAttribute not support" (พบบน Windows 25 พ.ย.)
            return PaddleOCR(lang=self.lang, use_doc_orientation_classify=False,
                             use_doc_unwarping=False, use_textline_orientation=True,
                             enable_mkldnn=False,
                             # ค่าเริ่มต้นคือ PP-OCRv5_server_det (~16 วินาที/ภาพบนคอม) หนักเกินสำหรับ Pi
                             text_detection_model_name="PP-OCRv5_mobile_det",
                             # ต้องระบุคู่กัน: ระบุ det อย่างเดียว Paddle จะไม่ map lang=th ให้ rec
                             text_recognition_model_name=f"{self.lang}_PP-OCRv5_mobile_rec")
        except TypeError:  # 2.x ไม่รู้จักพารามิเตอร์ข้างบน
            return PaddleOCR(lang=self.lang, use_angle_cls=True, show_log=False)
        except Exception as exc:
            raise OcrError(f"โหลดโมเดล PaddleOCR ไม่ได้: {type(exc).__name__}: {exc}") from exc

    def run(self, image) -> list[OcrLine]:
        if self._ocr is None:
            self._ocr = self._load()
        try:
            if hasattr(self._ocr, "predict"):
                raw = self._ocr.predict(image)
            else:
                raw = self._ocr.ocr(image, cls=True)
        except Exception as exc:
            raise OcrError(f"PaddleOCR ล้มระหว่างอ่าน: {type(exc).__name__}: {exc}") from exc
        return parse_paddle_output(raw)


def read_text(image_path, engine=None, *, min_confidence: float = 0.5,
              use_preprocess: bool = True) -> OcrResult:
    """ภาพ -> OcrResult; บรรทัดเรียงบนลงล่าง ซ้ายไปขวา ตัดบรรทัดความมั่นใจต่ำ"""
    path = Path(image_path)
    if not path.is_file():
        raise OcrError(f"ไม่พบไฟล์ภาพ: {path}")
    engine = engine or PaddleOcrEngine()

    started = time.perf_counter()
    image = preprocess(path) if use_preprocess else str(path)
    preprocess_ms = round((time.perf_counter() - started) * 1000, 3)

    started = time.perf_counter()
    lines = engine.run(image)
    ocr_ms = round((time.perf_counter() - started) * 1000, 3)

    kept = [line for line in lines if line.text.strip() and line.confidence >= min_confidence]
    kept.sort(key=lambda line: (round(line.top / 12), line.left))  # 12px ≈ บรรทัดเดียวกัน
    return OcrResult(text="\n".join(line.text.strip() for line in kept), lines=kept,
                     dropped_low_confidence=len(lines) - len(kept),
                     engine=getattr(engine, "name", type(engine).__name__),
                     preprocess_ms=preprocess_ms, ocr_ms=ocr_ms)
