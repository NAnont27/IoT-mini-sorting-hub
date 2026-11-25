"""OCR / extraction test bench for the web "ทดสอบ OCR" page.

Runs the AI team's modules (ai/mini_sorting_ai) on one image: PaddleOCR -> Gemini extraction
-> registry resolver. It never touches the controller, MQTT or the jobs table, and uses the
demo registry, so results are test-only. Use fictional label data: the page shows the raw OCR
text and the extracted recipient fields.

OCR runs in a child process: PaddlePaddle segfaulted on the Pi 5 (25 Nov) and took the whole
backend (controller + MQTT) down with it. A crash in the child now becomes a 503 for this page.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[2] / "ai"


class AiTestUnavailable(RuntimeError):
    pass


def _load_ai_env():
    path = AI_ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


class _Bench:
    """Runs inside the child process only."""

    def __init__(self):
        self._lock = threading.Lock()  # one OCR/model run at a time on the Pi
        self._ready = False
        self._modules = None
        self._engine = None
        self._snapshot = None
        self._client = None
        self._client_error = None

    def _setup(self):
        if self._ready:
            return
        if not (AI_ROOT / "mini_sorting_ai").is_dir():
            raise AiTestUnavailable("ai/ module not found next to backend/")
        if str(AI_ROOT) not in sys.path:
            sys.path.insert(0, str(AI_ROOT))
        _load_ai_env()
        from mini_sorting_ai import extraction, ocr, registry, resolver
        from mini_sorting_ai.gemini_client import AIServiceError, GeminiClient
        config = json.loads((AI_ROOT / "config.example.json").read_text(encoding="utf-8"))
        self._snapshot = registry.load_snapshot(AI_ROOT / "fixtures" / "registry_demo.csv", config)
        try:
            self._client = GeminiClient()
        except AIServiceError as exc:  # OCR-only tests still work without a key
            self._client_error = exc.reason
        self._engine = ocr.PaddleOcrEngine()
        self._modules = (extraction, ocr, resolver)
        self._ready = True

    def run(self, jpeg: bytes, use_ai: bool = True) -> dict:
        with self._lock:
            try:
                self._setup()
            except AiTestUnavailable:
                raise
            except Exception as exc:
                raise AiTestUnavailable(f"AI modules failed to load: {type(exc).__name__}: {exc}") from exc
            extraction, ocr, resolver = self._modules
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as handle:
                handle.write(jpeg)
                path = Path(handle.name)
            try:
                result = ocr.read_text(path, self._engine)
            except ocr.OcrError as exc:
                raise AiTestUnavailable(str(exc)) from exc
            finally:
                path.unlink(missing_ok=True)
            report = {
                "ocr": {"engine": result.engine, "text": result.text,
                        "mean_confidence": result.mean_confidence,
                        "dropped_low_confidence": result.dropped_low_confidence,
                        "lines": [{"text": line.text, "confidence": round(line.confidence, 3)}
                                  for line in result.lines]},
                "timings_ms": {"preprocess": result.preprocess_ms, "ocr": result.ocr_ms,
                               "ai": None, "resolve": None},
                "extraction": None, "resolution": None, "ai_error": None,
                "registry": "demo (ai/fixtures/registry_demo.csv)",
            }
            if not use_ai:
                return report
            if self._client is None:
                report["ai_error"] = self._client_error or "AI_NOT_CONFIGURED"
                return report
            started = time.perf_counter()
            extracted = extraction.extract_recipient(result.text, self._client)
            report["timings_ms"]["ai"] = round((time.perf_counter() - started) * 1000, 3)
            report["extraction"] = {"status": extracted.status, "reason": extracted.reason,
                                    "source": extracted.source, "fields": extracted.extraction,
                                    "grounding_issues": list(extracted.grounding_issues)}
            if extracted.status == extraction.STATUS_OK:
                started = time.perf_counter()
                envelope = resolver.resolve_recipient("TEST-" + str(int(time.time())),
                                                      extracted.extraction, self._snapshot)
                report["timings_ms"]["resolve"] = round((time.perf_counter() - started) * 1000, 3)
                report["resolution"] = {key: envelope.get(key) for key in
                                        ("outcome", "target_bin", "resolved_room", "resolved_floor",
                                         "reason_code", "evidence")}
            return report


class AiTester:
    """Backend-side handle: one child process per request, never imports Paddle itself."""

    def __init__(self, timeout_s=float(os.getenv("AI_TEST_TIMEOUT_S", "110"))):
        self.timeout_s = timeout_s
        self._lock = threading.Lock()  # one OCR run at a time on the Pi

    def run(self, jpeg: bytes, use_ai: bool = True) -> dict:
        with self._lock, tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "label.jpg"
            image.write_bytes(jpeg)
            try:
                done = subprocess.run(
                    [sys.executable, "-m", "backend.app.ai_test", str(image), "1" if use_ai else "0"],
                    cwd=str(AI_ROOT.parent), capture_output=True, timeout=self.timeout_s,
                    # UTF-8 for Thai OCR text on any OS; skip Paddle's slow model-host probe.
                    env={**os.environ, "PYTHONIOENCODING": "utf-8",
                         "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True"})
            except subprocess.TimeoutExpired as exc:
                raise AiTestUnavailable(f"OCR/AI took longer than {self.timeout_s:.0f} s") from exc
            if done.returncode != 0:
                tail = done.stderr.decode("utf-8", "replace").strip().splitlines()[-3:]
                crash = "crashed (signal %d)" % -done.returncode if done.returncode < 0 else "failed"
                raise AiTestUnavailable(f"OCR process {crash}: {' | '.join(tail)[:300]}")
            # Paddle prints progress to stdout; the report is the last line.
            last = done.stdout.decode("utf-8", "replace").strip().splitlines()[-1]
            report = json.loads(last)
            if "error" in report:
                raise AiTestUnavailable(report["error"])
            return report


if __name__ == "__main__":
    bench = _Bench()
    try:
        result = bench.run(Path(sys.argv[1]).read_bytes(), use_ai=sys.argv[2] == "1")
    except AiTestUnavailable as exc:
        result = {"error": str(exc)}
    sys.stdout.write(os.linesep + json.dumps(result, ensure_ascii=False) + os.linesep)
