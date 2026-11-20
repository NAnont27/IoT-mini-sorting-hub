"""Mini Sorting Hub — โมดูล AI: resolver ตามกฎทะเบียน (OCR/Gemini จะเพิ่มในขั้นถัดไป)"""

from .registry import RegistryError, Snapshot, load_snapshot, normalize_name
from .resolver import AIResponseError, pipeline_error, resolve_recipient, service_error

__all__ = [
    "AIResponseError",
    "RegistryError",
    "Snapshot",
    "load_snapshot",
    "normalize_name",
    "pipeline_error",
    "resolve_recipient",
    "service_error",
]
