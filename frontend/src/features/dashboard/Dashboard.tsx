"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { HubSnapshot, TargetBin } from "@/types/hub";
import { HistoryPanel } from "./HistoryPanel";
import { JobsPanel } from "./JobsPanel";
import { SettingsPanel } from "./SettingsPanel";

export function Dashboard() {
  const [snapshot, setSnapshot] = useState<HubSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [connectionError, setConnectionError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const data = await api<HubSnapshot>("/api/status", undefined, controller.signal);
        if (!controller.signal.aborted) { setSnapshot(data); setConnected(true); setConnectionError(""); }
      } catch (error) {
        if (!controller.signal.aborted) {
          setConnected(false);
          setConnectionError(error instanceof Error ? error.message : "เชื่อมต่อ Backend ไม่ได้");
        }
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(poll, 1000);
      }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, []);

  async function act(path: string, body: Record<string, unknown>) {
    setBusy(true); setActionError(""); setNotice("");
    try {
      setSnapshot(await api<HubSnapshot>(path, body));
      setNotice("ส่งคำขอแล้ว ตรวจสถานะและผลยืนยันจากอุปกรณ์ ไม่ใช่ผลคัดสำเร็จ");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "ส่งคำขอไม่สำเร็จ");
    } finally { setBusy(false); }
  }

  const disabled = busy || !connected;
  function control(action: string, target_bin?: TargetBin) { return act("/api/control", { action, target_bin }); }

  return <main>
    <header className="page-header"><div><p className="eyebrow">MINI SORTING HUB</p><h1>ทดสอบระบบคัดแยกบนโต๊ะ</h1></div><span className={`badge ${connected ? "online" : "offline"}`}>{connected ? "Backend connected" : "Backend disconnected"}</span></header>
    <p className="bench-note">{snapshot?.config.mode === "ai" ? "โหมด AI · " : "BENCH · เลือก A/B/HOLD บนเว็บ · "}ทางเดินกล่องจำลองด้วยมือ · Servo ขยับจริง · มุมและ IR ต้องยืนยันจริง</p>
    {connectionError && <p role="alert" className="error banner">{connectionError} · ข้อมูลเดิมอาจไม่เป็นปัจจุบัน</p>}
    <div role="status" aria-live="polite">{notice && <p className="notice">{notice}</p>}{actionError && <p className="error">{actionError}</p>}</div>

    <section className="panel">
      <div className="section-header"><h2>สถานะเครื่อง</h2><span className="badge">{snapshot?.config.mode.toUpperCase() ?? "CONNECTING"}</span></div>
      <p className="machine-state">{snapshot?.state ?? "กำลังเชื่อมต่อ…"}</p>
      <p className="muted">InfluxDB: {snapshot?.influx_status ?? "ยังไม่มีข้อมูล"}</p>
      {!!snapshot?.readiness_errors.length && <ul className="warning">{snapshot.readiness_errors.map((error) => <li key={error}>{error}</li>)}</ul>}
      <div className="actions">
        <button disabled={disabled} onClick={() => void control("pause")}>พักรับงาน</button>
        <button className="primary" disabled={disabled} onClick={() => void control("resume")}>เริ่ม / เริ่มต่อ</button>
        <button disabled={disabled || snapshot?.state !== "PAUSED_AI"} onClick={() => void control("retry_ai")}>ลอง AI ใหม่</button>
        <button disabled={disabled || snapshot?.state !== "FAULT"} onClick={() => { if (window.confirm("เอากล่องออกจากถาดและเคลียร์เส้นทางทุกจุดแล้วใช่ไหม?")) void control("reset"); }}>เคลียร์ Fault แล้ว</button>
      </div>
    </section>

    <section className="panel">
      <h2>งานปัจจุบัน</h2>
      <pre>{snapshot?.job ? JSON.stringify(snapshot.job, null, 2) : "ไม่มีงาน"}</pre>
      <p className="muted">เลือกช่องได้เมื่อสถานะ WAIT_DECISION เท่านั้น</p>
      <div className="actions">{(["A", "B", "HOLD"] as TargetBin[]).map((bin) => <button key={bin} className="bin-button" disabled={disabled || snapshot?.state !== "WAIT_DECISION"} onClick={() => void control("target", bin)}>{bin}</button>)}</div>
    </section>

    <section className="panel"><h2>ข้อมูลเซนเซอร์ล่าสุด</h2><div className="sensor-grid">{Object.entries(snapshot?.latest ?? {}).map(([topic, value]) => <details key={topic} open><summary><code>{topic}</code></summary><pre>{JSON.stringify(value, null, 2)}</pre></details>)}</div>{!snapshot && <p className="muted">รอข้อมูลจาก Backend</p>}</section>
    <SettingsPanel snapshot={snapshot} disabled={disabled} onSave={(settings) => act("/api/settings", settings)} />
    <JobsPanel />
    <HistoryPanel />
    <footer>โหมดทดสอบสำหรับเครือข่ายทีม · หน้าเว็บไม่มีระบบล็อกอิน · อ่านข้อจำกัดในคู่มือก่อนรัน</footer>
  </main>;
}
