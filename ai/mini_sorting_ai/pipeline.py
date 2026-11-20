"""ข้อความ OCR -> envelope ของ Backend: extraction แล้ว resolver ตามทะเบียน

- NO_TEXT -> RETRY_CAPTURE (Backend คุมจำนวนรอบ)
- SERVICE_ERROR -> SERVICE_ERROR (Backend เข้า PAUSED_AI)
- OK -> resolve_recipient (A/B/HOLD/RETRY_CAPTURE)
"""

from __future__ import annotations

from .extraction import STATUS_NO_TEXT, STATUS_OK, extract_recipient
from .registry import Snapshot
from .resolver import resolve_recipient, service_error


def process_ocr_text(job_id: str, ocr_text, snapshot: Snapshot, client, *,
                     vision_attempt: int = 1, artifacts: dict | None = None) -> dict:
    result = extract_recipient(ocr_text, client)

    if result.status == STATUS_NO_TEXT:
        return _retry_envelope(job_id, snapshot, vision_attempt, artifacts, result.reason)

    if result.status != STATUS_OK:
        return service_error(job_id, snapshot, result.reason,
                             vision_attempt=vision_attempt)

    envelope = resolve_recipient(job_id, result.extraction, snapshot,
                                 vision_attempt=vision_attempt, artifacts=artifacts)
    envelope["extraction_source"] = result.source
    envelope["grounding_issues"] = list(result.grounding_issues)
    return envelope


def _retry_envelope(job_id, snapshot, vision_attempt, artifacts, reason) -> dict:
    return {
        "schema_version": 1,
        "job_id": job_id,
        "vision_attempt": vision_attempt,
        "outcome": "RETRY_CAPTURE",
        "extraction": None,
        "resolved_room": None,
        "resolved_floor": None,
        "target_bin": None,
        "reason_code": reason or "OCR_TEXT_EMPTY",
        "tracking_id": None,
        "registry_version": snapshot.registry_version,
        "a_max_floor": snapshot.a_max_floor,
        "evidence": ["OCR text is empty; capture again"],
        "artifacts": artifacts or {},
        "timings_ms": {"resolve": 0},
        "error": None,
        "extraction_source": None,
        "grounding_issues": [],
    }
