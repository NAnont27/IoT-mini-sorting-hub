"""SQLite jobs/events + a separate queued InfluxDB v2 telemetry writer."""
import csv
import io
import json
import queue
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root, env):
        self.path = Path(root) / "data" / "hub.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY, created TEXT, updated TEXT, mode TEXT,
            state TEXT, target_bin TEXT, result TEXT, reason TEXT, detail TEXT);
          CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, topic TEXT, payload TEXT);
          CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, metric TEXT, value REAL);
        """)
        self.db.commit()
        self.enabled = env.get("INFLUX_ENABLED", "1") == "1"
        self.url = env.get("INFLUX_URL", "http://127.0.0.1:8086").rstrip("/")
        self.org = env.get("INFLUX_ORG", "mini-sort")
        self.bucket = env.get("INFLUX_BUCKET", "bench")
        self.headers = {"Authorization": "Token " + env.get("INFLUX_TOKEN", "")}
        self.influx_status = "waiting for data" if self.enabled else "DISABLED"
        self.lines = queue.Queue(maxsize=5000)
        self.writer = threading.Thread(target=self._write_loop, daemon=True)
        self.writer.start()

    def event(self, topic, payload):
        with self.lock:
            self.db.execute("INSERT INTO events(ts,topic,payload) VALUES(?,?,?)",
                            (utc_now(), topic, json.dumps(payload, ensure_ascii=False)))
            self.db.commit()

    def metric(self, name, value):
        value = float(value)
        with self.lock:
            self.db.execute("INSERT INTO telemetry(ts,metric,value) VALUES(?,?,?)",
                            (utc_now(), name, value))
            self.db.commit()
        if self.enabled:
            try:
                # name is supplied only by the fixed metric map in hub.py.
                self.lines.put_nowait(f"sensor,metric={name} value={value} {time.time_ns()}")
            except queue.Full:
                self.influx_status = "ERROR: write queue full; SQLite still recording"

    def _write_loop(self):
        while True:
            line = self.lines.get()
            batch = [line]
            while len(batch) < 100:
                try:
                    batch.append(self.lines.get_nowait())
                except queue.Empty:
                    break
            # Retry this batch in order; queue has a bounded size and errors are visible.
            while True:
                try:
                    response = requests.post(
                        self.url + "/api/v2/write", headers=self.headers,
                        params={"org": self.org, "bucket": self.bucket, "precision": "ns"},
                        data="\n".join(batch), timeout=5)
                    response.raise_for_status()
                    self.influx_status = "OK"
                    break
                except requests.RequestException as exc:
                    self.influx_status = "ERROR: " + type(exc).__name__
                    time.sleep(3)

    def save_job(self, job):
        with self.lock:
            self.db.execute("""INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(job_id) DO UPDATE SET updated=excluded.updated,
                state=excluded.state,target_bin=excluded.target_bin,result=excluded.result,
                reason=excluded.reason,detail=excluded.detail""", (
                job["job_id"], job["created"], utc_now(), job["mode"], job["state"],
                job.get("target_bin"), job.get("result"), job.get("reason"),
                json.dumps(job, ensure_ascii=False)))
            self.db.commit()

    def jobs(self, query=""):
        with self.lock:
            rows = self.db.execute(
                "SELECT detail FROM jobs WHERE job_id LIKE ? OR detail LIKE ? "
                "ORDER BY created DESC LIMIT 100", (f"%{query}%", f"%{query}%")).fetchall()
        return [json.loads(row[0]) for row in rows]

    def unfinished(self):
        with self.lock:
            return self.db.execute("SELECT detail FROM jobs WHERE result IS NULL").fetchall()

    def history(self, name):
        if name not in {"weight_g", "height_mm", "angle_deg", "light_lux"}:
            raise ValueError("Unknown metric")
        if self.enabled:
            flux = (f'from(bucket: {json.dumps(self.bucket)}) |> range(start: -1h) '
                    f'|> filter(fn: (r) => r._measurement == "sensor" and '
                    f'r.metric == "{name}" and r._field == "value") '
                    '|> aggregateWindow(every: 5s, fn: mean, createEmpty: false) '
                    '|> keep(columns: ["_time", "_value"])')
            response = requests.post(self.url + "/api/v2/query", params={"org": self.org},
                headers={**self.headers, "Content-Type": "application/vnd.flux",
                         "Accept": "application/csv"}, data=flux.encode(), timeout=8)
            response.raise_for_status()
            rows = csv.DictReader(io.StringIO("\n".join(
                line for line in response.text.splitlines() if not line.startswith("#"))))
            points = [{"time": row["_time"], "value": float(row["_value"])}
                      for row in rows if row.get("_time") and row.get("_value")]
            return {"source": "InfluxDB", "points": points}
        with self.lock:
            rows = self.db.execute("SELECT ts,value FROM telemetry WHERE metric=? "
                                   "ORDER BY id DESC LIMIT 300", (name,)).fetchall()
        return {"source": "SQLite BENCH FALLBACK (InfluxDB disabled)",
                "points": [{"time": ts, "value": value} for ts, value in reversed(rows)]}
