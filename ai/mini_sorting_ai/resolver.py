"""Deterministic resolver: ข้อมูลที่ AI แยกได้ + snapshot ทะเบียน -> ผล A/B/HOLD/RETRY_CAPTURE

ไม่เรียก AI และไม่สั่งฮาร์ดแวร์ โมดูลนี้เป็นเจ้าของกฎ A/B/HOLD เพียงชุดเดียว
"""

from __future__ import annotations

import time
from typing import Any

from .extraction_schema import AIResponseError, validate_extraction
from .registry import Snapshot, normalize_name

SCHEMA_VERSION = 1

__all__ = ["AIResponseError", "SCHEMA_VERSION", "resolve_recipient",
           "service_error", "pipeline_error"]


def _envelope(job_id, vision_attempt, outcome, extraction, snapshot, *,
              room=None, floor=None, target=None, reason, evidence,
              artifacts, started, error=None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "vision_attempt": vision_attempt,
        "outcome": outcome,
        "extraction": extraction,
        "resolved_room": room,
        "resolved_floor": floor,
        "target_bin": target,
        "reason_code": reason,
        "tracking_id": extraction.get("tracking_id") if extraction else None,
        "registry_version": snapshot.registry_version,
        "a_max_floor": snapshot.a_max_floor,
        "evidence": evidence,
        "artifacts": artifacts or {},
        # เวลาวัดจริงของขั้น resolve เท่านั้น ขั้นอื่นให้ Pipeline ใส่เอง
        "timings_ms": {"resolve": round((time.perf_counter() - started) * 1000, 3)},
        "error": error,
    }


def resolve_recipient(job_id: str, raw_extraction: Any, snapshot: Snapshot, *,
                      vision_attempt: int = 1, artifacts: dict | None = None) -> dict:
    started = time.perf_counter()
    ext = validate_extraction(raw_extraction)  # AIResponseError ให้ผู้เรียกแปลเป็น SERVICE_ERROR
    room = ext["recipient_room"]
    name_raw = ext["recipient_name_raw"]
    floor_text = ext["recipient_floor"]

    def done(outcome, reason, evidence, **kw):
        return _envelope(job_id, vision_attempt, outcome, ext, snapshot,
                         reason=reason, evidence=evidence, artifacts=artifacts,
                         started=started, **kw)

    def hold(reason, evidence):
        return done("HOLD", reason, evidence, target="HOLD")

    # 1) ไม่มีข้อมูลผู้รับเลย -> ขอถ่ายซ้ำ (Backend คุมจำนวนรอบ)
    if room is None and name_raw is None and floor_text is None:
        return done("RETRY_CAPTURE", "RETRY_NO_RECIPIENT_FIELDS",
                    ["no recipient room, name or floor was extracted"], target=None)

    evidence: list[str] = []

    # 2) ชั้นที่ข้อความระบุ ต้องเป็นชั้นที่มีจริงในตาราง ไม่ map ตัวเลขนอกทะเบียน
    if floor_text is not None:
        if floor_text not in snapshot.valid_floors:
            return hold("HOLD_FLOOR_NOT_IN_VALID_FLOORS",
                        [f"text states floor {floor_text} which is not in valid_floors"])
        evidence.append(f"text states floor {floor_text}")

    # 3) ห้อง -> ชั้นจากทะเบียน; ห้องที่ไม่มีในทะเบียนตรวจไม่ได้ -> HOLD (ไม่เดาจากเลขห้อง)
    room_floor = None
    if room is not None:
        if room not in snapshot.room_floor:
            return hold("HOLD_ROOM_NOT_IN_REGISTRY",
                        [f"room {room} is not in the registry"])
        room_floor = snapshot.room_floor[room]
        evidence.append(f"room {room} maps to floor {room_floor}")

    # 4) ชื่อ: ตรงแบบ normalize แล้วและต้องได้บุคคลเดียว ไม่เลือกคนแรกเงียบ ๆ
    person = None
    if name_raw is not None:
        key = normalize_name(name_raw)
        matches = [p for p in snapshot.people if p.name_key == key]
        if len(matches) > 1:
            # ชื่อซ้ำ: ใช้ห้องช่วยจำกัดได้เฉพาะเมื่อเหลือผู้รับที่สอดคล้องเพียงคนเดียว
            narrowed = [p for p in matches if room is not None and p.room == room]
            if len(narrowed) != 1:
                return hold("HOLD_NAME_AMBIGUOUS",
                            [f"name matches {len(matches)} residents"])
            matches = narrowed
        if len(matches) == 1:
            person = matches[0]
            evidence.append(f"recipient name matches {person.resident_id}")
            if room is not None and person.room != room:
                return hold("HOLD_CONFLICT_ROOM_NAME",
                            [f"room {room} conflicts with {person.resident_id} in room {person.room}"])
        else:
            # ชื่อไม่พบ: ไม่ใช้ชื่อคล้ายแทน และไม่ถือเป็นข้อขัดแย้งเอง
            evidence.append("recipient name not found in registry (not used)")

    # 5) รวมชั้นจากทุกแหล่ง: ต้องเหลือชั้นเดียว มิฉะนั้น HOLD
    floors = {f for f in (room_floor, person.floor if person else None, floor_text) if f is not None}
    if not floors:
        return hold("HOLD_NO_RESOLVABLE_FLOOR", evidence or ["no usable evidence"])
    if len(floors) > 1:
        return hold("HOLD_CONFLICT_FLOOR", [f"sources disagree on floor: {sorted(floors)}"])
    floor = floors.pop()

    if room is not None and person is not None:
        reason = "RESOLVED_ROOM_AND_NAME"
    elif room is not None:
        reason = "RESOLVED_ROOM"
    elif person is not None:
        reason = "RESOLVED_NAME"
    else:
        reason = "RESOLVED_FLOOR_TEXT"

    resolved_room = room or (person.room if person else None)
    target = "A" if floor <= snapshot.a_max_floor else "B"
    return done("RESOLVED", reason, evidence, room=resolved_room, floor=floor,
                target=target)


def service_error(job_id, snapshot: Snapshot, reason: str, *, vision_attempt: int = 1,
                  extraction: dict | None = None) -> dict:
    """AI/API/network ใช้ไม่ได้ หรือ JSON ไม่ผ่าน schema -> Backend เข้า PAUSED_AI"""
    started = time.perf_counter()
    return _envelope(job_id, vision_attempt, "SERVICE_ERROR", extraction, snapshot,
                     reason=reason, evidence=[], artifacts=None, started=started,
                     error={"kind": "SERVICE", "reason": reason})


def pipeline_error(job_id, snapshot: Snapshot | None, reason: str, *,
                   vision_attempt: int = 1) -> dict:
    """ความผิดปกติภายใน เช่น กล้อง ไฟล์ config หรือทะเบียน -> Backend แจ้ง fault"""
    started = time.perf_counter()
    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "vision_attempt": vision_attempt,
        "outcome": "PIPELINE_ERROR",
        "extraction": None,
        "resolved_room": None,
        "resolved_floor": None,
        "target_bin": None,
        "reason_code": reason,
        "tracking_id": None,
        "registry_version": snapshot.registry_version if snapshot else None,
        "a_max_floor": snapshot.a_max_floor if snapshot else None,
        "evidence": [],
        "artifacts": {},
        "timings_ms": {"resolve": round((time.perf_counter() - started) * 1000, 3)},
        "error": {"kind": "PIPELINE", "reason": reason},
    }
