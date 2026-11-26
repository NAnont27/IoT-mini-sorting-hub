"""Camera Module 3 snapshots for the dashboard (read-only preview).

Uses Picamera2 on the Raspberry Pi. Picamera2 is an OS package (python3-picamera2),
so the Pi .venv must see system site-packages. On machines without a camera the
class reports a clear reason instead of returning fake images.

This module only captures frames. It does not run OCR/AI and does not touch the
controller; the AI team integrates capture -> OCR -> Gemini later.
"""
import io
import logging
import os
import threading
import time


class CameraUnavailable(RuntimeError):
    pass


class Camera:
    # 0.15 s cache: allows ~5 fps preview; several viewers share one frame instead of re-encoding.
    def __init__(self, width=None, height=None, min_interval_s=0.15):
        self.enabled = os.getenv("CAMERA_ENABLED", "1") == "1"
        # One full-size stream: OCR uses it as-is, the dashboard gets a reduced copy.
        self.size = (int(width or os.getenv("CAMERA_WIDTH", "1920")),
                     int(height or os.getenv("CAMERA_HEIGHT", "1080")))
        self.min_interval_s = min_interval_s
        # Dashboard preview = full frame / CAMERA_PREVIEW_SCALE (3 -> 640x360); OCR keeps full size.
        self.preview_scale = max(1, int(os.getenv("CAMERA_PREVIEW_SCALE", "3")))
        self._lock = threading.Lock()
        self._camera = None
        self._error = None if self.enabled else "CAMERA_ENABLED=0"
        self._last_jpeg = None
        self._last_at = 0.0

    def _start(self):
        try:
            from picamera2 import Picamera2  # imported lazily: absent on Windows/tests
        except ImportError as exc:
            raise CameraUnavailable("picamera2 not importable (install python3-picamera2 and "
                                    "allow system site-packages in .venv)") from exc
        try:
            camera = Picamera2()
            camera.configure(camera.create_still_configuration(main={"size": self.size}))
            camera.start()
            time.sleep(1.0)  # let autofocus/auto-exposure settle once
        except Exception as exc:
            raise CameraUnavailable("camera start failed: " + type(exc).__name__ + ": " + str(exc)) from exc
        self._camera = camera

    def _ensure_started_locked(self):
        if self._camera is None:
            try:
                self._start()
                self._error = None
            except CameraUnavailable as exc:
                self._error = str(exc)
                raise

    def _capture_locked(self, scale, quality):
        """Grab one frame from the full-size stream; scale>1 shrinks it with PIL reduce()."""
        self._ensure_started_locked()
        buffer = io.BytesIO()
        try:
            image = self._camera.capture_image("main")
            if scale > 1:
                image = image.reduce(scale)  # 1920x1080 / 3 = 640x360, cheap integer box filter
            image.convert("RGB").save(buffer, format="JPEG", quality=quality)
        except Exception as exc:
            logging.exception("Camera capture failed")
            self._error = "capture failed: " + type(exc).__name__
            self.close_locked()
            raise CameraUnavailable(self._error) from exc
        return buffer.getvalue()

    def preview_jpeg(self):
        """Small JPEG for the dashboard (~640x360); viewers within min_interval_s share a frame."""
        if not self.enabled:
            raise CameraUnavailable(self._error)
        with self._lock:
            if self._last_jpeg is not None and time.monotonic() - self._last_at < self.min_interval_s:
                return self._last_jpeg
            self._last_jpeg = self._capture_locked(self.preview_scale, 70)
            self._last_at = time.monotonic()
            return self._last_jpeg

    def full_jpeg(self):
        """Fresh full-resolution JPEG for OCR (never cached, taken after the request)."""
        if not self.enabled:
            raise CameraUnavailable(self._error)
        with self._lock:
            return self._capture_locked(1, 92)

    def status(self):
        with self._lock:
            return {"enabled": self.enabled, "running": self._camera is not None,
                    "error": self._error,
                    "last_frame_age_s": round(time.monotonic() - self._last_at, 1) if self._last_jpeg else None}

    def close_locked(self):
        if self._camera is not None:
            try:
                self._camera.stop()
                self._camera.close()
            except Exception:
                logging.exception("Camera close failed")
            self._camera = None
