import copy
import json
import unittest
from pathlib import Path

from backend.app.controller import Controller, circular_error


class FakeStore:
    influx_status = "TEST"

    def __init__(self):
        self.saved = []

    def unfinished(self): return []
    def save_job(self, job): self.saved.append(copy.deepcopy(job))
    def metric(self, name, value): pass
    def event(self, name, value): pass


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.sent = []
        config = json.loads((Path(__file__).resolve().parents[1] / "config.example.json").read_text())
        config.update(max_weight_g=500, max_height_mm=200,
                      target_angles_deg={"A": 30, "B": 90, "HOLD": 150})
        self.store = FakeStore()
        self.c = Controller(config, self.store, lambda t, p: self.sent.append((t, p)) or True,
                            clock=lambda: self.now)
        self.c.broker = True
        self.seq = 0
        self.refresh()

    def feed(self, topic, **fields):
        self.seq += 1
        self.c.ingest(topic, {"schema_version": 1, "session_id": "boot1", "device_id": "node-01",
                             "seq": self.seq, "uptime_ms": 100000, **fields})

    def refresh(self, weight=0, tray=None):
        # D011: one tray IR; by default it sees a parcel whenever weight is on the tray.
        tray = weight > 0 if tray is None else tray
        self.feed("sorter/weight", valid=True, weight_g=weight, stable=True, node_fault=False)
        self.feed("sorter/height", valid=True, height_mm=50)
        self.feed("sorter/passage", active={"tray": tray}, events=[])
        self.feed("sorter/gateway", angle_valid=True, angle_deg=30, light_valid=True, light_lux=300)

    def start(self):
        self.c.operator("resume")
        self.refresh(weight=100)
        self.c.tick()
        self.assertEqual(self.c.job["state"], "WAIT_DECISION")
        self.c.operator("target", target_bin="A")

    def done(self):
        command = self.c.pending["message"]
        self.c.ingest("sorter/ack", {"schema_version": 1, "session_id": "boot1",
                      "command_id": command["command_id"], "status": "DONE"})

    def release(self):
        self.start()
        self.done()  # POSITION acknowledgement alone must not release.
        self.c.tick()
        self.now += 0.6
        self.refresh(weight=100)
        self.c.tick()
        self.assertEqual(self.c.job["state"], "RELEASE")
        self.done()

    def passage(self, *names, tray=False):
        job_id = self.c.job["job_id"]
        events = [{"id": i+1, "sensor": name, "job_id": job_id, "after_release": True}
                  for i, name in enumerate(names)]
        self.feed("sorter/passage", active={"tray": tray}, events=events)

    def test_no_auto_start_before_operator_resume(self):
        self.refresh(weight=100)
        self.c.tick()
        self.assertIsNone(self.c.job)

    def test_uncalibrated_weight_blocks_resume(self):
        self.feed("sorter/weight", valid=False)
        with self.assertRaises(ValueError): self.c.operator("resume")

    def test_stale_magnet_never_releases(self):
        self.start()
        self.done()
        self.now += 4
        self.c.tick()
        self.assertEqual(self.c.job["state"], "FAULT")
        self.assertFalse(any(p["action"] == "RELEASE" for _, p in self.sent))

    def test_ack_is_not_arrival(self):
        self.release()
        self.assertEqual(self.c.job["state"], "VERIFY_EXIT")
        self.assertIsNone(self.c.job["result"])

    def test_no_job_without_tray_ir(self):
        self.c.operator("resume")
        self.refresh(weight=100, tray=False)
        self.c.tick()
        self.assertIsNone(self.c.job)

    def test_tray_ir_clear_but_weight_still_on_tray_does_not_complete(self):
        self.release()
        self.refresh(weight=100, tray=False)
        self.c.tick()
        self.assertEqual(self.c.job["state"], "VERIFY_EXIT")
        self.assertIsNone(self.c.job["result"])

    def test_parcel_left_tray_completes(self):
        self.release()
        self.refresh(weight=0)
        self.c.tick()
        self.assertEqual(self.c.pending["message"]["action"], "COMPLETE")
        self.done()
        self.assertIsNone(self.c.job)
        self.assertEqual(self.store.saved[-1]["result"], "SORTED_A")
        self.assertFalse(self.store.saved[-1]["destination_sensed"])

    def test_pending_command_timeout_faults_without_retry(self):
        self.start()
        self.now += 6
        self.refresh(weight=100)
        self.c.tick()
        self.assertEqual(self.c.job["reason"], "COMMAND_TIMEOUT")
        self.assertEqual(sum(p["action"] == "POSITION" for _, p in self.sent), 1)

    def test_pause_after_release_does_not_switch_route(self):
        self.release()
        self.c.operator("pause")
        self.passage("tray")
        self.refresh(weight=0)
        self.c.tick()
        self.assertEqual(self.c.pending["message"]["action"], "COMPLETE")

    def test_paused_before_release_never_opens(self):
        self.start()
        self.done()
        self.c.operator("pause")
        self.now += 1
        self.refresh(weight=100)
        self.c.tick()
        self.assertFalse(any(p["action"] == "RELEASE" for _, p in self.sent))

    def test_ai_outage_pauses_instead_of_hold(self):
        self.c.config["mode"] = "ai"
        self.c.operator("resume")
        self.refresh(weight=100)
        self.c.tick()
        self.c.vision({"job_id": self.c.job["job_id"], "vision_attempt": 1,
                       "outcome": "SERVICE_ERROR", "target_bin": None, "reason_code": "API_TIMEOUT"})
        self.assertEqual(self.c.job["state"], "PAUSED_AI")
        self.assertNotIn("POSITION", [p.get("action") for _, p in self.sent])

    def test_ai_result_leaves_controller_without_recipient_data(self):
        self.c.config["mode"] = "ai"
        self.c.operator("resume")
        self.refresh(weight=100)
        self.c.tick()
        self.c.vision({"job_id": self.c.job["job_id"], "vision_attempt": 1,
                       "outcome": "RESOLVED", "target_bin": "A", "reason_code": "RESOLVED_ROOM_AND_NAME",
                       "tracking_id": None, "registry_version": "demo-v1", "a_max_floor": 3,
                       "resolved_room": "202", "resolved_floor": 2,
                       "extraction": {"recipient_name_raw": "คุณธนา ใจดี", "source_excerpt": "ผู้รับ: คุณธนา"},
                       "evidence": ["recipient name matches R001"], "artifacts": {"image_path": "x.jpg"},
                       "extraction_source": "gemini", "grounding_issues": []})
        payload = next(p for t, p in self.sent if t == "sorter/vision")
        self.assertEqual(payload["outcome"], "RESOLVED")
        for key in ("extraction", "resolved_room", "evidence", "artifacts", "extraction_source"):
            self.assertNotIn(key, payload)
        self.assertNotIn("คุณธนา", json.dumps(payload, ensure_ascii=False))
        self.assertNotIn("คุณธนา", json.dumps(self.c.job["vision_result"], ensure_ascii=False))

    def test_old_ai_result_rejected(self):
        with self.assertRaises(ValueError):
            self.c.vision({"job_id": "old", "outcome": "RESOLVED", "target_bin": "A"})

    def test_circular_angle(self):
        self.assertEqual(circular_error(359, 1), 2)

    def test_overweight_blocks_resume(self):
        self.refresh(weight=600)
        with self.assertRaises(ValueError): self.c.operator("resume")

    def test_invalid_angle_never_releases(self):
        self.start()
        self.done()
        self.feed("sorter/gateway", angle_valid=False, light_valid=True, light_lux=300)
        self.c.tick()
        self.assertEqual(self.c.job["state"], "FAULT")

    def test_node_reboot_during_job_faults(self):
        self.start()
        self.c.ingest("sorter/weight", {"schema_version": 1, "session_id": "boot2",
                      "device_id": "node-01", "seq": 0, "uptime_ms": 100,
                      "valid": True, "weight_g": 100})
        self.assertEqual(self.c.job["reason"], "NODE_REBOOT")

    def test_repeated_passage_cannot_double_count(self):
        self.release()
        self.passage("tray")
        self.passage("tray")
        self.refresh(weight=0)
        self.c.tick()
        self.done()
        self.assertEqual(sum(j.get("state") == "COMPLETE" for j in self.store.saved), 1)

    def test_reset_requires_physical_clear_and_empty(self):
        self.release()
        self.c.fail("TEST")
        with self.assertRaises(ValueError): self.c.operator("reset")

    def test_out_of_window_angle_does_not_release(self):
        self.start()
        self.done()
        self.feed("sorter/gateway", angle_valid=True, angle_deg=90, light_valid=True, light_lux=300)
        self.now += 0.6
        self.c.tick()
        self.assertEqual(self.c.job["state"], "POSITION")
        self.assertFalse(any(p.get("action") == "RELEASE" for _, p in self.sent))

    def test_hold_requires_actual_passage_too(self):
        self.c.operator("resume")
        self.refresh(weight=100)
        self.c.tick()
        self.c.operator("target", target_bin="HOLD")
        self.assertIsNone(self.c.job["result"])
        self.assertEqual(self.c.job["state"], "POSITION")


    def test_servo_test_sends_when_paused_without_job(self):
        self.c.operator("servo_test", servo="chute", angle=120)
        self.assertEqual(self.sent[-1][1]["action"], "SERVO_TEST")
        self.assertEqual(self.sent[-1][1]["angle"], 120)
        self.assertIsNone(self.c.pending)

    def test_servo_test_rejected_during_job_or_bad_input(self):
        with self.assertRaises(ValueError): self.c.operator("servo_test", servo="chute", angle=200)
        with self.assertRaises(ValueError): self.c.operator("servo_test", servo="arm", angle=90)
        self.start()
        self.c.operator("pause")
        with self.assertRaises(ValueError): self.c.operator("servo_test", servo="gate", angle=60)


if __name__ == "__main__":
    unittest.main()
