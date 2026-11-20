"""ตรวจโครงสร้างผล extraction จาก AI ตามเอกสารหลัก

ตรวจเฉพาะรูปแบบ (schema) ไม่รับรองว่าข้อมูลถูกต้อง ความถูกต้องตรวจโดย resolver ตามทะเบียน
"""

from __future__ import annotations

from typing import Any

REQUIRED_FIELDS = (
    "tracking_id",
    "recipient_name_raw",
    "recipient_room",
    "recipient_floor",
    "source_excerpt",
    "issues",
)


class AIResponseError(ValueError):
    """ผล AI ไม่ตรง schema -> SERVICE_ERROR reason AI_INVALID_RESPONSE (ไม่ใช่การ resolve)"""


def validate_extraction(raw: Any) -> dict:
    """คืน dict ที่ทำความสะอาดแล้ว หรือโยน AIResponseError"""
    if not isinstance(raw, dict):
        raise AIResponseError("extraction ต้องเป็น object")
    missing = [k for k in REQUIRED_FIELDS if k not in raw]
    if missing:
        raise AIResponseError(f"ขาดฟิลด์: {', '.join(missing)}")

    def opt_str(key: str) -> str | None:
        value = raw[key]
        if value is None:
            return None
        if not isinstance(value, str):
            raise AIResponseError(f"{key} ต้องเป็นข้อความหรือ null")
        return value.strip() or None

    floor = raw["recipient_floor"]
    if floor is not None and (not isinstance(floor, int) or isinstance(floor, bool)):
        raise AIResponseError("recipient_floor ต้องเป็นตัวเลขหรือ null")
    if not isinstance(raw["issues"], list):
        raise AIResponseError("issues ต้องเป็นรายการ")

    return {
        "tracking_id": opt_str("tracking_id"),
        "recipient_name_raw": opt_str("recipient_name_raw"),
        "recipient_room": opt_str("recipient_room"),
        "recipient_floor": floor,
        "source_excerpt": opt_str("source_excerpt"),
        "issues": list(raw["issues"]),
    }
