r"""PC-side OCR/extraction service for the web page /ocr-test (D026: OCR runs on the PC).

PaddleOCR segfaults on the Pi 5, so the test page's POST /api/ai/test is routed by Next.js to
this service instead of Flask on the Pi. The OCR model stays loaded between requests.

  .venv\Scripts\python.exe ai\run_test_server.py --backend http://<pi-ip>:5000

- Upload: body = JPEG/PNG -> OCR (+ Gemini if ?ai=1) -> demo registry
- ?capture=1: fetch a fresh frame from the Pi camera (GET /api/camera/snapshot.jpg) first
Uses ai/.env for Gemini. Never creates jobs or moves motors. Fictional label data only.
"""

import argparse
import sys
from pathlib import Path

import requests

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "ai"))

from flask import Flask, jsonify, request  # noqa: E402

from backend.app.ai_test import AiTestUnavailable, _Bench  # noqa: E402  (same logic as the Pi page)


def build_app(backend: str) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
    bench = _Bench()  # in-process: model loads once, later requests take ~4 s

    @app.post("/api/ai/test")
    def ai_test():
        use_ai = request.args.get("ai", "1") == "1"
        if request.args.get("capture") == "1":
            try:
                response = requests.get(backend.rstrip("/") + "/api/camera/snapshot.jpg", timeout=15)
            except requests.RequestException as exc:
                return jsonify(error=f"ติดต่อ backend บน Pi ไม่ได้: {type(exc).__name__}"), 503
            if response.status_code != 200:
                return jsonify(error="กล้องบน Pi: " + response.text[:200]), 503
            image = response.content
        else:
            image = request.get_data()
            if not image:
                return jsonify(error="Send an image body or use ?capture=1"), 400
        try:
            report = bench.run(image, use_ai=use_ai)
        except AiTestUnavailable as exc:
            return jsonify(error="OCR/AI test unavailable: " + str(exc)), 503
        report["ran_on"] = "pc"
        return jsonify(report)

    return app


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PC OCR/extraction service for /ocr-test")
    parser.add_argument("--backend", required=True, help="Flask backend on the Pi, e.g. http://172.20.10.4:5000")
    parser.add_argument("--port", type=int, default=5100)
    args = parser.parse_args(argv)
    build_app(args.backend).run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
