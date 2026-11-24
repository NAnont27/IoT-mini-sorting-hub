"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/lib/api/client";
import type { HubSnapshot, TargetBin } from "@/types/hub";
import { HistoryPanel } from "./HistoryPanel";
import { JobsPanel } from "./JobsPanel";
import { ServoTestPanel } from "./ServoTestPanel";
import { SettingsPanel } from "./SettingsPanel";

const stateLabels: Record<string, string> = {
  IDLE: "พร้อมรับพัสดุ", BLOCKED: "ยังไม่พร้อม", PAUSED_OPERATOR: "พักโดยผู้ควบคุม",
  WAIT_DECISION: "รอเลือกช่อง", WAIT_VISION: "รอผล AI", POSITION: "กำลังจัดตำแหน่งราง",
  RELEASE: "กำลังเปิดประตู", VERIFY_EXIT: "รอยืนยันการผ่าน", WAIT_CLEAR: "รอเคลียร์ทาง",
  CLOSING: "กำลังปิดประตู", PAUSED_AI: "AI หยุดทำงาน", FAULT: "ระบบขัดข้อง",
};

const iconPaths: Record<string, ReactNode> = {
  overview: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
  activity: <path d="M3 12h4l2.5-6 5 12 2.5-6H21"/>,
  parcel: <><path d="m4 7 8-4 8 4-8 4-8-4Z"/><path d="M4 7v10l8 4 8-4V7M12 11v10"/></>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
};

function Icon({ name }: { name: keyof typeof iconPaths }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{iconPaths[name]}</svg>;
}

function numberValue(payload: Record<string, unknown> | undefined, key: string, digits = 1) {
  const value = payload?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
}

function SensorCard({ label, value, unit, valid, detail, children }: {
  label: string; value: string; unit: string; valid: boolean; detail: string; children: ReactNode;
}) {
  return <article className="sensor-card">
    <div className="sensor-card-top"><div className="sensor-icon">{children}</div><span className={`signal ${valid ? "ok" : "bad"}`}>{valid ? "พร้อม" : "ไม่มีข้อมูล"}</span></div>
    <p className="sensor-label">{label}</p><p className="sensor-value">{value}<span>{unit}</span></p><p className="sensor-detail">{detail}</p>
  </article>;
}

export function Dashboard() {
  const [snapshot, setSnapshot] = useState<HubSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [connectionError, setConnectionError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const data = await api<HubSnapshot>("/api/status", undefined, controller.signal);
        if (!controller.signal.aborted) { setSnapshot(data); setConnected(true); setConnectionError(""); setLastUpdated(new Date()); }
      } catch (error) {
        if (!controller.signal.aborted) { setConnected(false); setConnectionError(error instanceof Error ? error.message : "เชื่อมต่อ Backend ไม่ได้"); }
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
      const next = await api<HubSnapshot>(path, body);
      setSnapshot(next); setLastUpdated(new Date());
      setNotice("ส่งคำขอแล้ว — ระบบจะยืนยันมุมราง และนับสำเร็จเมื่อกล่องออกจากถาดแล้ว");
    } catch (error) { setActionError(error instanceof Error ? error.message : "ส่งคำขอไม่สำเร็จ"); }
    finally { setBusy(false); }
  }

  const disabled = busy || !connected;
  const control = (action: string, target_bin?: TargetBin) => act("/api/control", { action, target_bin });
  const weight = snapshot?.latest["sorter/weight"];
  const height = snapshot?.latest["sorter/height"];
  const gateway = snapshot?.latest["sorter/gateway"];
  const passage = snapshot?.latest["sorter/passage"];
  const active = passage?.active as Record<string, unknown> | undefined;
  // D011: one tray IR only (true = parcel on tray). Destination bins are not sensed.
  const trayIr = active ? active["tray"] : undefined;
  const routeClear = trayIr === false;
  const currentState = snapshot?.state ?? "CONNECTING";
  const readinessErrors = snapshot?.readiness_errors ?? [];
  const statusTone = !connected ? "neutral" : currentState === "FAULT" || currentState === "PAUSED_AI" ? "danger" : readinessErrors.length ? "warning" : "success";
  const job = snapshot?.job;
  const selectedBin = job?.target_bin ?? null;
  const weightReady = weight?.valid === true && !readinessErrors.some((error) => error.includes("sorter/weight stale"));
  const heightReady = height?.valid === true && !readinessErrors.some((error) => error.includes("sorter/height stale"));
  const passageReady = Boolean(active) && !readinessErrors.some((error) => error.includes("sorter/passage stale"));
  const gatewayFresh = !readinessErrors.some((error) => error.includes("Pi sensors stale"));
  const angleReady = gateway?.angle_valid === true && gatewayFresh;
  const lightReady = gateway?.light_valid === true && gatewayFresh;
  const sensorCount = useMemo(() => [weightReady, heightReady, angleReady, lightReady, passageReady].filter(Boolean).length, [weightReady, heightReady, angleReady, lightReady, passageReady]);

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><span /></div><div><strong>Sorta</strong><small>MINI SORTING HUB</small></div></div>
      <nav aria-label="เมนูหลัก">
        <a className="active" href="#overview"><Icon name="overview" />ภาพรวม</a><a href="#sensors"><Icon name="activity" />เซนเซอร์</a><a href="#current-job"><Icon name="parcel" />งานปัจจุบัน</a><a href="#history"><Icon name="history" />ประวัติ</a><a href="#settings"><Icon name="settings" />ตั้งค่า</a>
      </nav>
      <div className="sidebar-status"><span className={`connection-dot ${connected ? "connected" : ""}`} /><div><strong>{connected ? "Backend online" : "Backend offline"}</strong><small>{lastUpdated ? `อัปเดต ${lastUpdated.toLocaleTimeString("th-TH")}` : "กำลังเชื่อมต่อ"}</small></div></div>
      <p className="sidebar-foot">BENCH v2<br />สำหรับเครือข่ายทีมเท่านั้น</p>
    </aside>

    <main className="workspace">
      <header className="topbar"><div><p className="eyebrow">OPERATOR CONSOLE</p><h1>ศูนย์ควบคุมการคัดแยก</h1><p className="subtitle">ติดตามสถานะ เลือกเส้นทาง และตรวจผลยืนยันจากอุปกรณ์จริง</p></div><div className="topbar-meta"><span className={`live-badge ${connected ? "is-live" : ""}`}><i />{connected ? "LIVE" : "OFFLINE"}</span><span className="mode-badge">{snapshot?.config.mode === "ai" ? "AI MODE" : "BENCH MODE"}</span></div></header>
      {connectionError && <div role="alert" className="alert danger-alert"><strong>เชื่อมต่อ Backend ไม่ได้</strong><span>{connectionError} ข้อมูลบนหน้าจออาจไม่เป็นปัจจุบัน</span></div>}
      <div className="announcer" role="status" aria-live="polite">{notice && <div className="alert success-alert">{notice}</div>}{actionError && <div className="alert danger-alert">{actionError}</div>}</div>

      <section id="overview" className="overview-grid">
        <article className={`hero-card tone-${statusTone}`}>
          <div className="hero-head"><span className="card-kicker">สถานะระบบ</span><span className="state-code">{currentState}</span></div>
          <div className="state-lockup"><span className="state-orb"><i /></span><div><h2>{stateLabels[currentState] ?? currentState}</h2><p>{readinessErrors.length ? `พบ ${readinessErrors.length} เงื่อนไขที่ต้องตรวจ` : "เซนเซอร์และเส้นทางพร้อมสำหรับขั้นตอนปัจจุบัน"}</p></div></div>
          <div className="hero-metrics"><div><span>เซนเซอร์พร้อม</span><strong>{sensorCount}<small>/5</small></strong></div><div><span>ถาด</span><strong>{trayIr === true ? "มีกล่อง" : routeClear ? "ว่าง" : "ตรวจสอบ"}</strong></div><div><span>ฐานข้อมูล</span><strong>{snapshot?.influx_status === "OK" ? "Influx OK" : "ดูสถานะ"}</strong></div></div>
        </article>
        <article className="control-card">
          <div className="card-heading"><div><span className="card-kicker">ควบคุมเครื่อง</span><h2>การทำงานหลัก</h2></div>{busy && <span className="working">กำลังส่ง…</span>}</div>
          <div className="control-buttons"><button className="button primary" disabled={disabled} onClick={() => void control("resume")}><span className="button-icon play" />เริ่ม / ทำงานต่อ</button><button className="button secondary" disabled={disabled} onClick={() => void control("pause")}><span className="button-icon pause" />พักรับงาน</button></div>
          <div className="control-secondary"><button className="text-button" disabled={disabled || currentState !== "PAUSED_AI"} onClick={() => void control("retry_ai")}>ลอง AI ใหม่</button><button className="text-button danger-text" disabled={disabled || currentState !== "FAULT"} onClick={() => { if (window.confirm("เอากล่องออกจากถาดและเคลียร์เส้นทางทุกจุดแล้วใช่ไหม?")) void control("reset"); }}>เคลียร์ Fault แล้ว</button></div>
          <p className="control-note"><span>!</span> ACK จาก Servo ยังไม่ใช่ผลคัดสำเร็จ ระบบนับสำเร็จเมื่อ IR ถาดว่างและน้ำหนักกลับศูนย์ (ไม่มีเซนเซอร์ยืนยันช่องปลายทาง)</p>
          <ServoTestPanel enabled={!disabled && currentState === "PAUSED_OPERATOR" && !snapshot?.job} onSend={(servo, angle) => void act("/api/control", { action: "servo_test", servo, angle })} />
        </article>
      </section>

      <section className="content-section" aria-labelledby="readiness-title"><div className="section-heading"><div><p className="eyebrow">READINESS</p><h2 id="readiness-title">เงื่อนไขก่อนเริ่ม</h2></div><span className={`summary-chip ${readinessErrors.length ? "needs-attention" : "ready"}`}>{readinessErrors.length ? `${readinessErrors.length} รายการต้องตรวจ` : "พร้อมทำงาน"}</span></div>{readinessErrors.length ? <div className="issue-grid">{readinessErrors.map((error, index) => <div className="issue" key={`${error}-${index}`}><span>{index + 1}</span><p>{error}</p></div>)}</div> : <div className="empty-success"><span>✓</span><div><strong>ผ่านการตรวจ readiness</strong><p>ระบบยังจะตรวจซ้ำทุกครั้งก่อนขยับกลไก</p></div></div>}</section>

      <section id="sensors" className="content-section" aria-labelledby="sensor-title"><div className="section-heading"><div><p className="eyebrow">LIVE TELEMETRY</p><h2 id="sensor-title">เซนเซอร์ล่าสุด</h2></div><span className="refresh-note">รีเฟรชประมาณทุก 1 วินาที</span></div><div className="sensor-grid">
        <SensorCard label="น้ำหนักบนถาด" value={numberValue(weight, "weight_g")} unit="g" valid={weightReady} detail={weight?.stable ? "ค่านิ่งแล้ว" : "กำลังรอค่านิ่ง"}><span className="scale-symbol">kg</span></SensorCard>
        <SensorCard label="ความสูงพัสดุ" value={numberValue(height, "height_mm", 0)} unit="mm" valid={heightReady} detail="HY-SRF05 · ESP32"><span className="ruler-symbol" /></SensorCard>
        <SensorCard label="มุมราง" value={numberValue(gateway, "angle_deg")} unit="°" valid={angleReady} detail="AS5600 · Raspberry Pi"><span className="angle-symbol" /></SensorCard>
        <SensorCard label="ความสว่าง" value={numberValue(gateway, "light_lux", 0)} unit="lux" valid={lightReady} detail="BH1750 · Raspberry Pi"><span className="sun-symbol">✦</span></SensorCard>
        <SensorCard label="IR ถาด" value={trayIr === true ? "มีกล่อง" : routeClear ? "ว่าง" : "ตรวจ"} unit="" valid={passageReady} detail="E18 จุดวางกล่อง (GPIO11)"><span className="beam-symbol" /></SensorCard>
      </div></section>

      <section id="current-job" className="content-section" aria-labelledby="job-title"><div className="section-heading"><div><p className="eyebrow">ACTIVE PARCEL</p><h2 id="job-title">งานปัจจุบัน</h2></div>{job && <code className="job-id">{job.job_id}</code>}</div><div className="job-layout">
        <div className="job-summary">{job ? <><div className="job-state-line"><span className="parcel-glyph"><Icon name="parcel" /></span><div><span>ขั้นตอนปัจจุบัน</span><strong>{stateLabels[job.state] ?? job.state}</strong></div></div><dl className="job-facts"><div><dt>น้ำหนัก</dt><dd>{typeof job.weight_g === "number" ? `${job.weight_g.toFixed(1)} g` : "—"}</dd></div><div><dt>ความสูง</dt><dd>{typeof job.height_mm === "number" ? `${job.height_mm.toFixed(0)} mm` : "—"}</dd></div><div><dt>โหมด</dt><dd>{job.mode.toUpperCase()}</dd></div></dl></> : <div className="no-job"><span className="parcel-glyph"><Icon name="parcel" /></span><div><strong>ยังไม่มีพัสดุบนถาด</strong><p>เมื่อ resume และกล่องนิ่ง ระบบจะสร้าง job_id อัตโนมัติ</p></div></div>}</div>
        <div className="route-panel"><div className="route-title"><div><strong>เลือกช่องปลายทาง</strong><span>ใช้ได้เฉพาะสถานะ WAIT_DECISION</span></div><span className="manual-tag">MANUAL</span></div><div className="route-visual"><span className="route-origin">ถาดชั่ง</span><span className="route-line" /><div className="bin-stack">{(["A", "B", "HOLD"] as TargetBin[]).map((bin) => <button key={bin} className={`bin-choice ${selectedBin === bin ? "selected" : ""}`} disabled={disabled || currentState !== "WAIT_DECISION"} onClick={() => void control("target", bin)}><strong>{bin}</strong><span>{bin === "A" ? "ชั้นล่าง" : bin === "B" ? "ชั้นบน" : "รอตรวจ"}</span></button>)}</div></div></div>
      </div>{snapshot?.pending_command && <details className="technical-details"><summary>คำสั่ง MQTT ที่กำลังรอ ACK</summary><pre>{JSON.stringify(snapshot.pending_command, null, 2)}</pre></details>}</section>

      <div id="settings"><SettingsPanel snapshot={snapshot} disabled={disabled} onSave={(settings) => act("/api/settings", settings)} /></div>
      <div id="history"><HistoryPanel /></div>
      <JobsPanel />
      <footer className="page-footer"><span>Mini Sorting Hub · BENCH v2</span><span>Frontend :3000 · Backend :5000 · LAN only</span></footer>
    </main>
  </div>;
}
