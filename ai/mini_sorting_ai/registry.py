"""โหลดทะเบียนผู้พักและตั้งค่าชั้น เป็น snapshot ที่อ่านอย่างเดียวตลอดหนึ่ง job"""

from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

REQUIRED_COLUMNS = ("resident_id", "full_name", "room", "floor")
# เรียงจากยาวไปสั้น เพื่อให้ "นางสาว" ถูกตัดก่อน "นาง"
NAME_PREFIXES = ("นางสาว", "นาง", "คุณ", "นาย")


class RegistryError(ValueError):
    """ทะเบียนหรือ config ใช้ไม่ได้ -> ฝั่ง Backend ต้องแปลเป็น PIPELINE_ERROR"""


@dataclass(frozen=True)
class Person:
    resident_id: str
    name_key: str
    room: str
    floor: int


@dataclass(frozen=True)
class Snapshot:
    registry_version: str
    a_max_floor: int
    valid_floors: frozenset[int]
    people: tuple[Person, ...]
    room_floor: MappingProxyType  # room (str) -> floor (int), อ่านอย่างเดียว


def normalize_name(raw: str) -> str:
    """จัดรูปแบบชื่อ: Unicode NFC, ยุบช่องว่าง, ตัดคำนำหน้าที่ระบุชัด ไม่ fuzzy-match"""
    text = unicodedata.normalize("NFC", " ".join(str(raw).split()))
    for prefix in NAME_PREFIXES:
        if text.startswith(prefix) and len(text) > len(prefix):
            rest = text[len(prefix):].lstrip()
            if rest:
                text = rest
            break
    return text


def load_snapshot(csv_path: str | Path, config: dict) -> Snapshot:
    """อ่าน CSV ทะเบียนและ config แล้วตรวจความถูกต้อง; ข้อผิดพลาดใด ๆ โยน RegistryError"""
    registry_version = config.get("registry_version")
    if not isinstance(registry_version, str) or not registry_version.strip():
        raise RegistryError("config: registry_version ต้องเป็นข้อความที่ไม่ว่าง")

    valid_raw = config.get("valid_floors")
    if not isinstance(valid_raw, list) or not valid_raw:
        raise RegistryError("config: valid_floors ต้องเป็นรายการชั้นที่ไม่ว่าง")
    try:
        valid_floors = frozenset(int(v) for v in valid_raw)
    except (TypeError, ValueError) as exc:
        raise RegistryError("config: valid_floors มีค่าที่ไม่ใช่ตัวเลข") from exc

    a_max = config.get("a_max_floor")
    if not isinstance(a_max, int) or isinstance(a_max, bool) or a_max not in valid_floors:
        raise RegistryError("config: a_max_floor ต้องเป็นชั้นที่อยู่ใน valid_floors")

    path = Path(csv_path)
    try:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None or any(c not in reader.fieldnames for c in REQUIRED_COLUMNS):
                raise RegistryError(f"ทะเบียน: ต้องมีคอลัมน์ {', '.join(REQUIRED_COLUMNS)}")
            rows = list(reader)
    except OSError as exc:
        raise RegistryError(f"ทะเบียน: อ่านไฟล์ไม่ได้ ({exc})") from exc

    if not rows:
        raise RegistryError("ทะเบียน: ไม่มีข้อมูลผู้พัก")

    people: list[Person] = []
    seen_ids: set[str] = set()
    room_floor: dict[str, int] = {}

    for line_no, row in enumerate(rows, start=2):
        resident_id = (row.get("resident_id") or "").strip()
        full_name = (row.get("full_name") or "").strip()
        room = (row.get("room") or "").strip()
        floor_raw = (row.get("floor") or "").strip()

        if not resident_id or not full_name or not room or not floor_raw:
            raise RegistryError(f"ทะเบียน บรรทัด {line_no}: มีค่าว่างในช่องที่จำเป็น")
        if resident_id in seen_ids:
            raise RegistryError(f"ทะเบียน บรรทัด {line_no}: resident_id ซ้ำ {resident_id}")
        seen_ids.add(resident_id)

        try:
            floor = int(floor_raw)
        except ValueError as exc:
            raise RegistryError(f"ทะเบียน บรรทัด {line_no}: floor ไม่ใช่ตัวเลข") from exc
        if floor not in valid_floors:
            raise RegistryError(f"ทะเบียน บรรทัด {line_no}: ชั้น {floor} ไม่อยู่ใน valid_floors")

        existing = room_floor.get(room)
        if existing is not None and existing != floor:
            raise RegistryError(f"ทะเบียน บรรทัด {line_no}: ห้อง {room} map ได้มากกว่าหนึ่งชั้น")
        room_floor[room] = floor

        people.append(Person(resident_id, normalize_name(full_name), room, floor))

    return Snapshot(
        registry_version=registry_version.strip(),
        a_max_floor=a_max,
        valid_floors=valid_floors,
        people=tuple(people),
        room_floor=MappingProxyType(room_floor),
    )
