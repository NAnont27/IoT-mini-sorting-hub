"""Local bench coordinator/API. Start only one process; no Flask reloader."""
import copy
import json
import logging
import math
import os
import queue
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request

from .camera import Camera, CameraUnavailable
from .controller import BINS, Controller
from .store import Store

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
logging.basicConfig(level=logging.INFO)


def _json_object():
    """Return a JSON object or a traceable 400 error for every write endpoint."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object")
    return data


def build_app():
    config_path = ROOT / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("mode") not in {"bench", "ai"}:
        raise ValueError("mode must be bench or ai")
    store = Store(ROOT, os.environ)
    incoming = queue.Queue(maxsize=10000)
    lock = threading.RLock()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="hub-controller")
    client.username_pw_set(os.environ["MQTT_USER"], os.environ["MQTT_PASSWORD"])
    client.reconnect_delay_set(1, 5)

    def publish(topic, payload):
        info = client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1, retain=False)
        return info.rc == mqtt.MQTT_ERR_SUCCESS

    controller = Controller(config, store, publish)

    def on_connect(client, userdata, flags, reason_code, properties):
        incoming.put(("_broker", not reason_code.is_failure))
        if not reason_code.is_failure:
            client.subscribe("sorter/#", qos=1)

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        incoming.put(("_broker", False))

    def on_message(client, userdata, message):
        if message.topic in {"sorter/cmd", "sorter/vision"}:
            return
        try:
            if len(message.payload) > 16384:
                return
            payload = json.loads(message.payload)
            incoming.put_nowait((message.topic, payload))
        except (ValueError, queue.Full):
            logging.warning("Invalid MQTT payload or incoming queue full")

    client.on_connect, client.on_disconnect, client.on_message = on_connect, on_disconnect, on_message

    def run_controller():
        while True:
            with lock:
                try:
                    for _ in range(100):
                        try:
                            topic, payload = incoming.get_nowait()
                        except queue.Empty:
                            break
                        if topic == "_broker":
                            controller.broker = payload
                        else:
                            store.event(topic, payload)
                            controller.ingest(topic, payload)
                    controller.tick()
                except Exception:
                    logging.exception("Controller error")
                    controller.fail("INTERNAL_CONTROLLER_ERROR")
                    controller.paused = True
            time.sleep(0.05)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    camera = Camera()

    @app.get("/")
    def index():
        return jsonify(
            service="mini-sorting-hub-backend",
            api_version=1,
            status_url="/api/status",
            dashboard="Next.js frontend runs separately on port 3000",
        )

    @app.get("/api/status")
    def status():
        with lock:
            return jsonify(controller.snapshot())

    @app.post("/api/control")
    def control():
        data = _json_object()
        if not isinstance(data.get("action"), str):
            raise ValueError("action is required")
        with lock:
            controller.operator(data.get("action"), target_bin=data.get("target_bin"),
                                servo=data.get("servo"), angle=data.get("angle"))
            return jsonify(controller.snapshot())

    @app.post("/api/settings")
    def settings():
        data = _json_object()
        allowed = {"max_weight_g", "max_height_mm", "save_angle_for"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError("Unknown settings: " + ", ".join(unknown))
        if not data:
            raise ValueError("At least one setting is required")
        with lock:
            if not controller.paused or controller.job:
                raise ValueError("Pause and finish/clear the active job before changing settings")
            updated = copy.deepcopy(controller.config)
            for name in ("max_weight_g", "max_height_mm"):
                if name in data:
                    value = float(data[name])
                    if not math.isfinite(value) or value <= 0:
                        raise ValueError(name + " must be positive and finite")
                    updated[name] = value
            if updated["max_weight_g"] is not None and updated["max_weight_g"] <= updated["min_weight_g"]:
                raise ValueError("max_weight_g must exceed min_weight_g")
            if "save_angle_for" in data:
                name = data["save_angle_for"]
                gateway = controller.data("sorter/gateway")
                if name not in BINS or not controller.fresh("sorter/gateway", 3) or not gateway.get("angle_valid"):
                    raise ValueError("Need a fresh valid magnet angle and A/B/HOLD")
                angle = float(gateway["angle_deg"])
                if any(value is not None and other != name and
                       abs((angle - value + 180) % 360 - 180) <= 2 * updated["angle_tolerance_deg"]
                       for other, value in updated["target_angles_deg"].items()):
                    raise ValueError("Target angle windows must not overlap")
                updated["target_angles_deg"][name] = angle
            temporary = config_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
            temporary.replace(config_path)
            controller.config = updated
            return jsonify(controller.snapshot())

    @app.get("/api/jobs")
    def jobs():
        query = request.args.get("q", "").strip()
        if len(query) > 120:
            raise ValueError("Search query is too long")
        return jsonify(store.jobs(query))

    @app.get("/api/history")
    def history():
        try:
            return jsonify(store.history(request.args.get("metric", "weight_g")))
        except ValueError:
            raise
        except Exception as exc:
            return jsonify(error="InfluxDB query failed: " + type(exc).__name__, points=[]), 503

    @app.get("/api/ai/pending")
    def pending_ai():
        with lock:
            job = controller.job
            if not job or job["state"] != "WAIT_VISION":
                return jsonify(job=None)
            return jsonify(job={"job_id": job["job_id"], "vision_attempt": job["vision_attempt"],
                                "weight_g": job["weight_g"], "height_mm": job["height_mm"],
                                "capture_required": True})

    @app.post("/api/ai/result")
    def ai_result():
        data = _json_object()
        with lock:
            controller.vision(data)
            return jsonify(controller.snapshot())

    @app.get("/api/camera/snapshot.jpg")
    def camera_snapshot():
        try:
            jpeg = camera.snapshot_jpeg()
        except CameraUnavailable as exc:
            return jsonify(error="Camera unavailable: " + str(exc)), 503
        return Response(jpeg, mimetype="image/jpeg")

    @app.get("/api/camera/status")
    def camera_status():
        return jsonify(camera.status())

    @app.after_request
    def api_headers(response):
        if request.path == "/" or request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.errorhandler(ValueError)
    def bad_request(error):
        return jsonify(error=str(error)), 400

    client.connect_async(os.getenv("MQTT_HOST", "127.0.0.1"), int(os.getenv("MQTT_PORT", "1883")), 10)
    client.loop_start()
    threading.Thread(target=run_controller, daemon=True).start()
    return app


if __name__ == "__main__":
    build_app().run(host=os.getenv("WEB_HOST", "0.0.0.0"),
                    port=int(os.getenv("WEB_PORT", "5000")), debug=False, use_reloader=False,
                    threaded=True)
