"""CLI ทดลองจากไฟล์ข้อความ OCR -> envelope JSON

ตัวอย่าง (ใช้ mock เมื่อไม่มี key หรือเทสต์):
  python -m mini_sorting_ai.cli --ocr ai/fixtures/ocr_demo.txt --job-id JOB-0001 --mock-response ai/fixtures/mock_response_demo.json

ตัวอย่าง (Gemini จริง ต้องตั้ง GEMINI_API_KEY และ GEMINI_MODEL):
  python -m mini_sorting_ai.cli --ocr ai/fixtures/ocr_demo.txt --job-id JOB-0001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .gemini_client import AIServiceError, GeminiClient, MockClient
from .pipeline import process_ocr_text
from .registry import RegistryError, load_snapshot

AI_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="OCR text -> A/B/HOLD envelope")
    p.add_argument("--ocr", required=True, type=Path, help="ไฟล์ข้อความ OCR")
    p.add_argument("--job-id", required=True, help="job_id ที่ Backend สร้าง")
    p.add_argument("--registry", type=Path, default=AI_ROOT / "fixtures" / "registry_demo.csv")
    p.add_argument("--config", type=Path, default=AI_ROOT / "config.example.json")
    p.add_argument("--vision-attempt", type=int, default=1)
    p.add_argument("--mock-response", type=Path,
                   help="ใช้ผลจำลองจากไฟล์ JSON แทน Gemini (แสดง source=mock)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        snapshot = load_snapshot(args.registry, config)
    except (OSError, json.JSONDecodeError, RegistryError) as exc:
        print(json.dumps({"outcome": "PIPELINE_ERROR", "reason_code": "CONFIG_OR_REGISTRY_INVALID",
                          "detail": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    try:
        ocr_text = args.ocr.read_text(encoding="utf-8")
    except OSError as exc:
        print(json.dumps({"outcome": "PIPELINE_ERROR", "reason_code": "OCR_FILE_UNREADABLE",
                          "detail": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    if args.mock_response is not None:
        client = MockClient(response_text=args.mock_response.read_text(encoding="utf-8"))
    else:
        try:
            client = GeminiClient()
        except AIServiceError as exc:
            print(json.dumps({"outcome": "SERVICE_ERROR", "reason_code": exc.reason},
                             ensure_ascii=False, indent=2))
            return 1

    envelope = process_ocr_text(args.job_id, ocr_text, snapshot, client,
                                vision_attempt=args.vision_attempt,
                                artifacts={"ocr_text_path": str(args.ocr)})
    print(json.dumps(envelope, ensure_ascii=False, indent=2))
    # exit 1 เมื่อ AI ใช้ไม่ได้ เพื่อให้สคริปต์เรียกใช้แยกความล้มเหลวของบริการออกจากผลตัดสิน
    return 1 if envelope.get("outcome") == "SERVICE_ERROR" else 0


if __name__ == "__main__":
    sys.exit(main())
