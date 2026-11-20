"""Gemini adapter: ส่ง prompt ไปยัง Gemini แล้วคืนข้อความ JSON ดิบ

- อ่าน key จาก GEMINI_API_KEY และชื่อโมเดลจาก GEMINI_MODEL เท่านั้น ไม่มีค่าเริ่มต้นที่เดา
- ไม่ log และไม่ใส่ key ในข้อความ error
- retry จำกัดจำนวนครั้ง; ล้มเหลวทั้งหมดโยน AIServiceError (ฝั่งเรียกแปลเป็น SERVICE_ERROR)
- MockClient ให้ผลที่มี source="mock" เพื่อไม่ให้ถูกรายงานเป็นผลจริง
"""

from __future__ import annotations

import os
import time
from typing import Callable

__all__ = ["AIServiceError", "GeminiClient", "MockClient"]


class AIServiceError(RuntimeError):
    """AI ใช้ไม่ได้ -> SERVICE_ERROR; reason เป็นรหัสสั้น ไม่มี key หรือข้อความดิบ"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _sdk_call(api_key: str) -> Callable[[str, str], str]:
    """สร้างฟังก์ชันเรียก SDK จริง; import ตอนใช้งานเท่านั้น เพื่อให้เทสต์ไม่ต้องติดตั้ง SDK"""
    from google import genai  # pip install google-genai

    client = genai.Client(api_key=api_key)

    def call(model: str, prompt: str) -> str:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return response.text

    return call


class GeminiClient:
    source = "gemini"

    def __init__(self, *, api_key: str | None = None, model: str | None = None,
                 max_retries: int = 2, backoff_s: float = 1.0,
                 _call: Callable[[str, str], str] | None = None,
                 _sleep: Callable[[float], None] = time.sleep):
        api_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", "")
        model = model if model is not None else os.environ.get("GEMINI_MODEL", "")
        if not api_key.strip():
            raise AIServiceError("AI_NOT_CONFIGURED_KEY")
        if not model.strip():
            raise AIServiceError("AI_NOT_CONFIGURED_MODEL")
        if max_retries < 0:
            raise ValueError("max_retries ต้องไม่ติดลบ")
        self._model = model.strip()
        self._max_retries = max_retries
        self._backoff_s = backoff_s
        self._sleep = _sleep
        self._call = _call if _call is not None else _sdk_call(api_key.strip())

    def generate_json(self, prompt: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                text = self._call(self._model, prompt)
                if not isinstance(text, str) or not text.strip():
                    raise AIServiceError("AI_EMPTY_RESPONSE")
                return text
            except AIServiceError as exc:
                last_error = exc
            except Exception as exc:  # network, quota, server error จาก SDK
                last_error = AIServiceError("AI_UNAVAILABLE")
                last_error.__cause__ = exc
            if attempt < self._max_retries:
                self._sleep(self._backoff_s * (2 ** attempt))
        assert last_error is not None
        raise last_error


class MockClient:
    """ใช้แทน Gemini ตอนไม่มี key หรือเทสต์ ผลต้องแสดง source=mock เสมอ"""

    source = "mock"

    def __init__(self, response_text: str | None = None, error_reason: str | None = None):
        self._response_text = response_text
        self._error_reason = error_reason
        self.calls = 0

    def generate_json(self, prompt: str) -> str:
        self.calls += 1
        if self._error_reason is not None:
            raise AIServiceError(self._error_reason)
        if self._response_text is None:
            raise AIServiceError("AI_EMPTY_RESPONSE")
        return self._response_text
