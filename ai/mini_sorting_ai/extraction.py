"""ประกอบขั้น extraction: prompt -> AI client -> JSON -> schema -> ตรวจหลักฐานกับข้อความ OCR

ผลที่คืนเป็น ExtractionResult ไม่ใช่ envelope ของ Backend
ฝั่งเรียกจะแปลง status เป็น SERVICE_ERROR, RETRY_CAPTURE หรือส่งเข้า resolver
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .extraction_schema import AIResponseError, validate_extraction
from .gemini_client import AIServiceError
from .prompt import build_prompt

STATUS_OK = "OK"
STATUS_SERVICE_ERROR = "SERVICE_ERROR"
STATUS_NO_TEXT = "NO_TEXT"


@dataclass(frozen=True)
class ExtractionResult:
    status: str
    reason: str | None
    source: str | None
    extraction: dict | None = None
    grounding_issues: tuple[str, ...] = field(default_factory=tuple)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _ground(extraction: dict, ocr_text: str) -> tuple[dict, list[str]]:
    """ค่าที่ AI ระบุต้องปรากฏในข้อความ OCR จริง ไม่เช่นนั้นเป็นค่าที่ AI สร้างขึ้นเอง -> null"""
    issues: list[str] = []
    out = dict(extraction)
    compact_text = _compact(ocr_text)

    room = out["recipient_room"]
    if room is not None and not re.search(rf"(?<!\d){re.escape(room)}(?!\d)", ocr_text):
        out["recipient_room"] = None
        issues.append("ROOM_NOT_IN_OCR")

    name = out["recipient_name_raw"]
    if name is not None and _compact(name) not in compact_text:
        out["recipient_name_raw"] = None
        issues.append("NAME_NOT_IN_OCR")

    tracking = out["tracking_id"]
    if tracking is not None and _compact(tracking) not in compact_text:
        out["tracking_id"] = None
        issues.append("TRACKING_NOT_IN_OCR")

    floor = out["recipient_floor"]
    if floor is not None and not re.search(rf"(?<!\d){floor}(?!\d)", ocr_text):
        out["recipient_floor"] = None
        issues.append("FLOOR_NOT_IN_OCR")

    if out["source_excerpt"] is not None and _compact(out["source_excerpt"]) not in compact_text:
        out["source_excerpt"] = None
        issues.append("EXCERPT_NOT_IN_OCR")

    out["issues"] = list(out["issues"]) + issues
    return out, issues


def extract_recipient(ocr_text: Any, client) -> ExtractionResult:
    """ดึงข้อมูลผู้รับจากข้อความ OCR; ไม่โยน exception เพื่อให้ฝั่งเรียกจัดการทุก status"""
    source = getattr(client, "source", None)

    if not isinstance(ocr_text, str) or not ocr_text.strip():
        return ExtractionResult(STATUS_NO_TEXT, "OCR_TEXT_EMPTY", source)

    prompt = build_prompt(ocr_text)

    try:
        raw_text = client.generate_json(prompt)
    except AIServiceError as exc:
        return ExtractionResult(STATUS_SERVICE_ERROR, exc.reason, source)

    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return ExtractionResult(STATUS_SERVICE_ERROR, "AI_INVALID_RESPONSE", source)

    try:
        extraction = validate_extraction(data)
    except AIResponseError:
        return ExtractionResult(STATUS_SERVICE_ERROR, "AI_INVALID_RESPONSE", source)

    grounded, issues = _ground(extraction, ocr_text)
    return ExtractionResult(STATUS_OK, None, source, grounded, tuple(issues))
