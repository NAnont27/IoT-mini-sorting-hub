r"""Vision worker: Backend job -> กล้อง -> PaddleOCR -> Gemini -> resolver -> Backend

วนถาม GET /api/ai/pending เมื่อมีงานใน WAIT_VISION:
  POST /api/camera/capture (Backend ถ่ายภาพใหม่และเก็บไฟล์) -> read_text() -> process_ocr_text()
  -> POST /api/ai/result

- worker ไม่เปิดกล้องเอง (Backend ถือกล้องอยู่) และไม่สั่ง GPIO/MQTT ใด ๆ
- ประมวลผลแต่ละ (job_id, vision_attempt) ครั้งเดียว; ผลเก่าที่ Backend ปฏิเสธจะไม่ส่งซ้ำ
- โหลดโมเดล OCR ครั้งเดียวต่อ process เพื่อให้รอบถัดไปเร็ว

รันบนคอม (D026: PaddleOCR segfault บน Pi 5) จากราก repo (โหลด ai/.env ให้เอง):
  .venv\Scripts\python.exe ai\run_worker.py --backend http://<IP Pi>:5000
"""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
import time
from pathlib import Path

import requests

from .gemini_client import AIServiceError, GeminiClient
from .ocr import OcrError, PaddleOcrEngine, read_text
from .pipeline import process_ocr_text
from .registry import RegistryError, load_snapshot

AI_ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("vision_worker")


class VisionWorker:
    def __init__(self, backend: str, snapshot, client, engine, *, min_confidence: float = 0.5,
                 http=requests, timeout: float = 10.0, use_preprocess: bool = True):
        self.backend = backend.rstrip("/")
        self.snapshot, self.client, self.engine = snapshot, client, engine
        self.min_confidence = min_confidence
        self.http, self.timeout = http, timeout
        self.use_preprocess = use_preprocess
        self.done: set[tuple[str, int]] = set()

    def pending(self):
        response = self.http.get(self.backend + "/api/ai/pending", timeout=self.timeout)
        response.raise_for_status()
        return response.json().get("job")

    def process(self, job: dict) -> dict:
        job_id, attempt = job["job_id"], job["vision_attempt"]
        capture = self.http.post(self.backend + "/api/camera/capture",
                                 json={"job_id": job_id, "vision_attempt": attempt},
                                 timeout=self.timeout + 10)
        if capture.status_code != 200:
            # กล้องใช้ไม่ได้ = ระบบภาพล้ม ไม่ใช่ผู้รับกำกวม -> PIPELINE_ERROR ให้คนตรวจ
            return self._pipeline_error(job_id, attempt, "CAPTURE_FAILED", capture.text[:200])
        image_path = capture.headers.get("X-Image-Path", "")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as handle:
            handle.write(capture.content)
            local = Path(handle.name)
        try:
            ocr = read_text(local, self.engine, min_confidence=self.min_confidence,
                            use_preprocess=self.use_preprocess)
        except OcrError as exc:
            return self._pipeline_error(job_id, attempt, "OCR_UNAVAILABLE", str(exc))
        finally:
            local.unlink(missing_ok=True)
        return process_ocr_text(
            job_id, ocr.text, self.snapshot, self.client, vision_attempt=attempt,
            artifacts={"image_path": image_path, "ocr_engine": ocr.engine,
                       "ocr_mean_confidence": ocr.mean_confidence},
            ocr_timings={"preprocess": ocr.preprocess_ms, "ocr": ocr.ocr_ms})

    def _pipeline_error(self, job_id, attempt, reason, detail):
        log.error("%s %s attempt %s: %s", reason, job_id, attempt, detail)
        return {"schema_version": 1, "job_id": job_id, "vision_attempt": attempt,
                "outcome": "PIPELINE_ERROR", "target_bin": None, "reason_code": reason,
                "evidence": [detail]}

    def submit(self, envelope: dict) -> bool:
        response = self.http.post(self.backend + "/api/ai/result", json=envelope,
                                  timeout=self.timeout)
        if response.status_code != 200:
            log.warning("Backend rejected result for %s: %s", envelope.get("job_id"),
                        response.text[:200])
            return False
        return True

    def step(self) -> dict | None:
        job = self.pending()
        if not job:
            return None
        key = (job["job_id"], job["vision_attempt"])
        if key in self.done:
            return None
        self.done.add(key)
        started = time.perf_counter()
        envelope = self.process(job)
        accepted = self.submit(envelope)
        log.info("%s attempt %s -> %s/%s (%s) in %.1fs, backend %s",
                 key[0], key[1], envelope.get("outcome"), envelope.get("target_bin"),
                 envelope.get("reason_code"), time.perf_counter() - started,
                 "accepted" if accepted else "rejected")
        return envelope

    def run_forever(self, interval: float = 0.5):
        while True:
            try:
                self.step()
            except requests.RequestException as exc:
                log.warning("Backend unreachable: %s", type(exc).__name__)
                time.sleep(2)
            time.sleep(interval)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Vision worker for Mini Sorting Hub")
    parser.add_argument("--backend", default="http://127.0.0.1:5000")
    parser.add_argument("--registry", type=Path, default=AI_ROOT / "fixtures" / "registry_demo.csv")
    parser.add_argument("--config", type=Path, default=AI_ROOT / "config.example.json")
    parser.add_argument("--min-confidence", type=float, default=0.5)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        snapshot = load_snapshot(args.registry, config)
    except (OSError, json.JSONDecodeError, RegistryError) as exc:
        log.error("Registry/config invalid: %s", exc)
        return 2
    try:
        client = GeminiClient()
    except AIServiceError as exc:
        log.error("Gemini unavailable: %s", exc.reason)
        return 1
    # โมเดล OCR โหลดตอนกล่องแรก (ช้ากว่ารอบถัดไป; ครั้งแรกบนเครื่องใหม่จะดาวน์โหลดโมเดล)
    engine = PaddleOcrEngine()
    log.info("Vision worker ready; polling %s", args.backend)
    VisionWorker(args.backend, snapshot, client, engine,
                 min_confidence=args.min_confidence).run_forever()
    return 0
