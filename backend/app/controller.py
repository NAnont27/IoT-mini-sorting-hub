"""Single-owner state machine. It never treats a command ACK as a parcel arrival."""
import copy
import time
import uuid

from .store import utc_now

BINS = ("A", "B", "HOLD")
TERMINAL = {"FAULT", "PAUSED_AI", "RESETTING"}


def circular_error(a, b):
    return abs((a - b + 180) % 360 - 180)


class Controller:
    def __init__(self, config, store, publish, clock=time.monotonic):
        self.config, self.store, self.publish, self.clock = config, store, publish, clock
        self.latest, self.received = {}, {}
        self.sequences = {}
        self.pending = None
        self.job = None
        self.paused = True
        self.broker = False
        self.last_ping = 0
        self.angle_since = None
        self.events_seen = set()
        self.position_done = False
        self.resume_state = None
        # Restarting a controller never silently continues a previously open gate/job.
        for row in store.unfinished():
            import json
            old = json.loads(row[0])
            old.update(state="FAULT", result="INTERRUPTED", reason="BACKEND_RESTART")
            store.save_job(old)
            if self.job is None:
                self.job = old

    def data(self, topic):
        return self.latest.get(topic, {})

    def fresh(self, topic, seconds):
        return self.clock() - self.received.get(topic, -1e9) <= seconds

    def _save(self):
        if self.job:
            self.store.save_job(self.job)

    def state(self, state):
        self.job["state"] = state
        self.job["stage_started"] = self.clock()
        self._save()

    def _send(self, action, **extra):
        node = self.data("sorter/weight")
        if not self.broker or not self.fresh("sorter/weight", self.config["node_stale_s"]):
            raise ValueError("Node/broker not ready")
        message = {"schema_version": 1, "command_id": uuid.uuid4().hex,
                   "job_id": self.job["job_id"] if self.job else None,
                   "node_session_id": node.get("session_id"), "action": action,
                   "expires_uptime_ms": (int(node["uptime_ms"]) + 5000) & 0xFFFFFFFF,
                   **extra}
        if not self.publish("sorter/cmd", message):
            raise ValueError("MQTT publish failed")
        return message

    def command(self, action, **extra):
        if self.pending:
            raise ValueError("Another command is pending")
        message = self._send(action, **extra)
        self.pending = {"message": message, "at": self.clock()}

    def checks(self):
        errors = []
        c = self.config
        if not self.broker:
            errors.append("MQTT disconnected")
        for topic in ("sorter/weight", "sorter/height", "sorter/passage"):
            if not self.fresh(topic, c["node_stale_s"]):
                errors.append(topic + " stale")
        if not self.fresh("sorter/gateway", c["gateway_stale_s"]):
            errors.append("Pi sensors stale")
        weight = self.data("sorter/weight")
        height = self.data("sorter/height")
        gateway = self.data("sorter/gateway")
        if not weight.get("valid"):
            errors.append("HX711 unavailable or not calibrated")
        if weight.get("node_fault"):
            errors.append("Node fault; clear route then reset")
        if not height.get("valid"):
            errors.append("ToF unavailable or empty distance not calibrated")
        if not gateway.get("angle_valid"):
            errors.append("AS5600 angle/magnet invalid")
        if not gateway.get("light_valid"):
            errors.append("BH1750 unavailable")
        if c["max_weight_g"] is None or c["max_height_mm"] is None:
            errors.append("Set bench weight/height limits first")
        if (not self.job or self.job["state"] not in {"RELEASE", "VERIFY_EXIT", "WAIT_CLEAR", "CLOSING"}):
            if (weight.get("valid") and c["max_weight_g"] is not None
                    and weight.get("weight_g", 0) > c["max_weight_g"]):
                errors.append("Weight exceeds bench limit")
            if (height.get("valid") and c["max_height_mm"] is not None
                    and height.get("height_mm", 0) > c["max_height_mm"]):
                errors.append("Height exceeds bench limit")
        if any(c["target_angles_deg"].get(b) is None for b in BINS):
            errors.append("Save measured angle for A/B/HOLD first")
        return errors

    def route_clear(self):
        passage = self.data("sorter/passage")
        active = passage.get("active", {})
        return (self.fresh("sorter/passage", self.config["node_stale_s"])
                and all(name in active and active[name] is False
                        for name in ("tray_exit", *BINS)))

    def empty(self):
        weight = self.data("sorter/weight")
        return (self.fresh("sorter/weight", self.config["node_stale_s"])
                and weight.get("valid") and abs(weight["weight_g"]) < self.config["min_weight_g"])

    def ingest(self, topic, payload):
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            return
        if topic == "sorter/ack":
            self._ack(payload)
            return
        if topic not in {"sorter/weight", "sorter/height", "sorter/passage",
                         "sorter/gateway", "sorter/actuator", "sorter/status"}:
            return
        key = (topic, payload.get("device_id"), payload.get("session_id"))
        seq = payload.get("seq")
        if not isinstance(seq, int) or seq <= self.sequences.get(key, -1):
            return
        self.sequences[key] = seq
        old_session = self.data("sorter/weight").get("session_id")
        self.latest[topic] = payload
        self.received[topic] = self.clock()
        if (topic == "sorter/weight" and self.job and old_session
                and old_session != payload.get("session_id")):
            self.fail("NODE_REBOOT")
        if topic == "sorter/status" and payload.get("event") == "PAUSE_BUTTON":
            try:
                self.operator("pause" if not self.paused else "resume")
            except ValueError as exc:
                self.store.event("operator/button_rejected", {"reason": str(exc)})
        metrics = {"sorter/weight": ("weight_g", "valid"),
                   "sorter/height": ("height_mm", "valid")}
        if topic in metrics:
            name, valid = metrics[topic]
            if payload.get(valid) and isinstance(payload.get(name), (int, float)):
                self.store.metric(name, payload[name])
        if topic == "sorter/gateway":
            for name, valid in (("angle_deg", "angle_valid"), ("light_lux", "light_valid")):
                if payload.get(valid):
                    self.store.metric(name, payload[name])
        if topic == "sorter/passage":
            for event in payload.get("events", []):
                self._passage(event, payload.get("session_id"))

    def _ack(self, ack):
        if not self.pending or not self.job:
            return
        command = self.pending["message"]
        if (ack.get("command_id") != command["command_id"]
                or ack.get("session_id") != command["node_session_id"]):
            return
        if ack.get("status") == "REJECTED":
            self.pending = None
            self.fail("COMMAND_REJECTED:" + str(ack.get("reason")))
            return
        if ack.get("status") != "DONE":
            return
        action = command["action"]
        self.pending = None
        if self.job["state"] == "FAULT" and action != "RESET":
            return
        if action == "POSITION":
            self.position_done = True
        elif action == "RELEASE":
            # Passage events may already have arrived; flags are never reset here.
            self.state("VERIFY_EXIT")
        elif action == "COMPLETE":
            target = self.job["target_bin"]
            self.job.update(result="HOLD_DELIVERED" if target == "HOLD" else "SORTED_" + target,
                            reason="BENCH_PASSAGE_SIMULATED" if self.config["mode"] == "bench"
                            else "AI_WITH_PASSAGE_SIMULATED")
            self.state("COMPLETE")
            self.job = None
        elif action == "RESET":
            self.job.update(result=self.job.get("result") or "ABORTED", reason="OPERATOR_CLEARED")
            self.state("CLOSED_AFTER_FAULT")
            self.job = None
            self.paused = True

    def _passage(self, event, session):
        key = (session, event.get("id"))
        if key in self.events_seen:
            return
        self.events_seen.add(key)
        if len(self.events_seen) > 4096:
            # Events are also filtered by job_id; retained duplicates remain harmless.
            self.events_seen = {key}
        if (not self.job or self.job["state"] not in {"RELEASE", "VERIFY_EXIT", "WAIT_CLEAR"}
                or event.get("job_id") != self.job["job_id"]
                or not event.get("after_release")):
            return
        sensor = event.get("sensor")
        if sensor == "tray_exit":
            self.job["tray_seen"] = True
        elif sensor in BINS:
            if sensor != self.job["target_bin"]:
                self.fail("MISROUTE", result="MISROUTE")
            elif not self.job.get("tray_seen"):
                self.fail("BIN_BEFORE_TRAY_EXIT")
            else:
                self.job["bin_seen"] = True
        self._save()

    def fail(self, reason, result="FAULT"):
        if not self.job or self.job["state"] == "FAULT":
            return
        self.pending = None
        self.job.update(reason=reason, result=result)
        self.state("FAULT")
        self.paused = True
        try:
            self._send("FAULT")
        except ValueError:
            pass

    def operator(self, action, **values):
        if action == "pause":
            self.paused = True
        elif action == "resume":
            if self.job and self.job["state"] in TERMINAL:
                raise ValueError("Resolve AI/fault first")
            if self.checks():
                raise ValueError("; ".join(self.checks()))
            self.paused = False
        elif action == "target":
            if (self.config["mode"] != "bench" or not self.job
                    or self.job["state"] != "WAIT_DECISION" or self.paused):
                raise ValueError("Need an active BENCH job in WAIT_DECISION")
            target = values.get("target_bin")
            if target not in BINS:
                raise ValueError("Choose A/B/HOLD")
            self.choose(target, "MANUAL_BENCH_SELECTION")
        elif action == "reset":
            if not self.job or self.job["state"] not in {"FAULT", "PAUSED_AI"}:
                raise ValueError("No fault/AI pause to clear")
            if not self.route_clear() or not self.empty():
                raise ValueError("Remove parcel; all IR paths and weighing tray must be clear")
            self.pending = None
            self.state("RESETTING")
            try:
                self.command("RESET")
            except ValueError:
                self.state("FAULT")
                raise
        elif action == "retry_ai":
            if not self.job or self.job["state"] != "PAUSED_AI":
                raise ValueError("No AI pause")
            self.paused = False
            self.job["vision_attempt"] += 1
            self.state("WAIT_VISION")
        else:
            raise ValueError("Unknown action")

    def choose(self, target, reason):
        self.job.update(target_bin=target, reason=reason)
        self.position_done = False
        self.angle_since = None
        self.state("POSITION")
        self.command("POSITION", target_bin=target)

    def vision(self, result):
        if (self.config["mode"] != "ai" or not self.job or self.job["state"] != "WAIT_VISION"
                or result.get("job_id") != self.job["job_id"]
                or result.get("vision_attempt") != self.job["vision_attempt"]):
            raise ValueError("Stale/non-active AI result")
        outcome, target = result.get("outcome"), result.get("target_bin")
        if not result.get("reason_code"):
            raise ValueError("reason_code required")
        if self.paused and outcome not in {"SERVICE_ERROR", "PIPELINE_ERROR"}:
            raise ValueError("Resume before submitting the result")
        self.job["vision_result"] = result
        self.publish("sorter/vision", {"schema_version": 1, **result})
        if outcome in {"SERVICE_ERROR", "PIPELINE_ERROR"}:
            self.job["reason"] = result["reason_code"]
            self.paused = True
            self.state("PAUSED_AI" if outcome == "SERVICE_ERROR" else "FAULT")
        elif outcome == "RETRY_CAPTURE":
            if self.job["vision_attempt"] < self.config["capture_retry_limit"]:
                self.job["vision_attempt"] += 1
                self.state("WAIT_VISION")
            else:
                self.choose("HOLD", "CAPTURE_RETRIES_EXHAUSTED")
        elif (outcome == "RESOLVED" and target in {"A", "B"}) or (outcome == "HOLD" and target == "HOLD"):
            if self.paused:
                raise ValueError("Resume before submitting the result")
            self.choose(target, result["reason_code"])
        else:
            raise ValueError("Invalid outcome/target_bin")

    def tick(self):
        now = self.clock()
        if self.broker and self.fresh("sorter/weight", self.config["node_stale_s"]) and now - self.last_ping > 1:
            self.last_ping = now
            try:
                self._send("PING", display_state=self.display_state())
            except ValueError:
                pass
        if self.pending and now - self.pending["at"] > self.config["command_timeout_s"]:
            # Never retry a movement automatically after an ambiguous timeout.
            self.pending = None
            if self.job and self.job["state"] == "RESETTING":
                self.state("FAULT")
            else:
                self.fail("COMMAND_TIMEOUT")
        errors = self.checks()
        if not self.job:
            if self.paused or errors or not self.route_clear():
                return
            w, h = self.data("sorter/weight"), self.data("sorter/height")
            if w.get("weight_g", 0) < self.config["min_weight_g"] or not w.get("stable"):
                return
            if w["weight_g"] > self.config["max_weight_g"] or h["height_mm"] > self.config["max_height_mm"]:
                return  # Visible blocked reason in snapshot; never release oversized load.
            self.job = {"job_id": "JOB-" + uuid.uuid4().hex[:12], "created": utc_now(),
                        "mode": self.config["mode"], "passage_simulated": True,
                        "weight_g": w["weight_g"], "height_mm": h["height_mm"],
                        "vision_attempt": 1, "tray_seen": False, "bin_seen": False,
                        "result": None, "config_snapshot": copy.deepcopy(self.config)}
            self.events_seen.clear()
            self.state("WAIT_DECISION" if self.config["mode"] == "bench" else "WAIT_VISION")
            return
        state = self.job["state"]
        if state in TERMINAL:
            return
        if errors:
            self.fail("READINESS_LOST: " + "; ".join(errors))
            return
        age = now - self.job["stage_started"]
        if state in {"RELEASE", "VERIFY_EXIT", "WAIT_CLEAR"}:
            # After release, operator pause only affects the NEXT parcel.
            if self.job.get("bin_seen") and state != "WAIT_CLEAR" and not self.pending:
                self.state("WAIT_CLEAR")
            if self.job["state"] == "WAIT_CLEAR" and self.route_clear() and self.empty() and not self.pending:
                self.state("CLOSING")
                self.command("COMPLETE")
            elif age > self.config["exit_timeout_s"]:
                self.fail("PASSAGE_OR_CLEAR_TIMEOUT")
            return
        if self.paused:
            self.angle_since = None
            return
        if state == "WAIT_VISION" and age > self.config["vision_timeout_s"]:
            self.job["reason"] = "AI_RESULT_TIMEOUT"
            self.paused = True
            self.state("PAUSED_AI")
        elif state == "POSITION":
            if age > self.config["position_timeout_s"]:
                self.fail("ANGLE_TIMEOUT")
                return
            measured = self.data("sorter/gateway")["angle_deg"]
            target = self.config["target_angles_deg"][self.job["target_bin"]]
            if self.position_done and circular_error(measured, target) <= self.config["angle_tolerance_deg"]:
                if self.angle_since is None:
                    self.angle_since = now
                if now - self.angle_since >= self.config["angle_dwell_s"] and not self.pending:
                    if not self.route_clear():
                        self.fail("PATH_BLOCKED_BEFORE_RELEASE")
                        return
                    self.state("RELEASE")
                    self.command("RELEASE", target_bin=self.job["target_bin"], angle_verified=True)
            else:
                self.angle_since = None

    def display_state(self):
        if self.job and self.job["state"] in {"FAULT", "RESETTING"}:
            return "FAULT"
        if self.job and self.job["state"] == "PAUSED_AI":
            return "PAUSED_AI"
        if self.paused:
            return "PAUSED_OPERATOR"
        return self.job["state"] if self.job else ("BLOCKED" if self.checks() or not self.route_clear() else "IDLE")

    def snapshot(self):
        errors = self.checks()
        w, h = self.data("sorter/weight"), self.data("sorter/height")
        if w.get("valid") and self.config["max_weight_g"] is not None and w["weight_g"] > self.config["max_weight_g"]:
            errors.append("Weight exceeds bench limit")
        if h.get("valid") and self.config["max_height_mm"] is not None and h["height_mm"] > self.config["max_height_mm"]:
            errors.append("Height exceeds bench limit")
        return {"state": self.display_state(), "paused": self.paused,
                "job": copy.deepcopy(self.job), "readiness_errors": errors,
                "latest": copy.deepcopy(self.latest), "config": copy.deepcopy(self.config),
                "influx_status": self.store.influx_status,
                "pending_command": self.pending["message"] if self.pending else None}
