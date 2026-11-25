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
    def __init__(self, width=None, height=None, min_interval_s=0.3):
        self.enabled = os.getenv("CAMERA_ENABLED", "1") == "1"
        # One configuration serves preview and OCR; labels need more pixels than a 720p preview.
        self.size = (int(width or os.getenv("CAMERA_WIDTH", "1920")),
                     int(height or os.getenv("CAMERA_HEIGHT", "1080")))
        self.min_interval_s = min_interval_s
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

    def snapshot_jpeg(self, fresh=False):
        """Return JPEG bytes; reuse a frame newer than min_interval_s unless fresh=True.

        fresh=True is used for OCR capture so the label image is taken after the request.
        """
        if not self.enabled:
            raise CameraUnavailable(self._error)
        with self._lock:
            now = time.monotonic()
            if (not fresh and self._last_jpeg is not None
                    and now - self._last_at < self.min_interval_s):
                return self._last_jpeg
            if self._camera is None:
                try:
                    self._start()
                    self._error = None
                except CameraUnavailable as exc:
                    self._error = str(exc)
                    raise
            buffer = io.BytesIO()
            try:
                self._camera.capture_file(buffer, format="jpeg")
            except Exception as exc:
                logging.exception("Camera capture failed")
                self._error = "capture failed: " + type(exc).__name__
                self.close_locked()
                raise CameraUnavailable(self._error) from exc
            self._last_jpeg = buffer.getvalue()
            self._last_at = time.monotonic()
            return self._last_jpeg

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
