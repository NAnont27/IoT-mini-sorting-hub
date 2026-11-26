"use client";

import { useEffect, useState } from "react";

// Live preview from Camera Module 3 on the Pi via Flask /api/camera/snapshot.jpg.
// Polls one JPEG at a time: the next request is scheduled only after the previous image
// loads or fails, so a slow Pi never gets a backlog. Each frame is a JPEG encode on the Pi.
const FPS_OPTIONS = [1, 2, 5] as const;

export function CameraPanel() {
  const [running, setRunning] = useState(true);
  const [tick, setTick] = useState(0);
  const [settled, setSettled] = useState(0); // increments when a frame loads or fails
  const [fps, setFps] = useState<(typeof FPS_OPTIONS)[number]>(2);
  const [error, setError] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState<string | null>(null);

  useEffect(() => {
    if (!running) return;
    const timer = window.setTimeout(() => setTick((value) => value + 1), 1000 / fps);
    return () => window.clearTimeout(timer);
  }, [running, settled, fps]);

  async function explainFailure() {
    try {
      const response = await fetch("/api/camera/status", { cache: "no-store" });
      const data = (await response.json()) as { error?: string | null };
      setError(data.error || "โหลดภาพไม่ได้ (backend/กล้อง)");
    } catch {
      setError("ติดต่อ backend ไม่ได้");
    }
  }

  return (
    <section id="camera" className="content-section" aria-labelledby="camera-title">
      <div className="section-heading">
        <div><p className="eyebrow">CAMERA</p><h2 id="camera-title">กล้องจุดอ่านฉลาก</h2></div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label>เฟรมเรท <select value={fps} onChange={(e) => setFps(Number(e.target.value) as (typeof FPS_OPTIONS)[number])} aria-label="เฟรมเรท">
            {FPS_OPTIONS.map((value) => <option key={value} value={value}>{value} fps</option>)}
          </select></label>
          <button className="button secondary" onClick={() => setRunning((value) => !value)}>{running ? "หยุดภาพ" : "เริ่มภาพ"}</button>
        </div>
      </div>
      <div className="camera-frame">
        {/* eslint-disable-next-line @next/next/no-img-element -- live JPEG from backend, not a static asset */}
        <img
          src={`/api/camera/snapshot.jpg?t=${tick}`}
          alt="ภาพจาก Camera Module 3"
          style={{ width: "100%", maxWidth: 960, aspectRatio: "16 / 9", objectFit: "contain", background: "#111", borderRadius: 12 }}
          onLoad={() => { setError(null); setLoadedAt(new Date().toLocaleTimeString("th-TH")); setSettled((value) => value + 1); }}
          onError={() => { void explainFailure(); setSettled((value) => value + 1); }}
        />
      </div>
      <p className="refresh-note">
        {error ? `⚠ ${error}` : loadedAt ? `ภาพล่าสุด ${loadedAt} · เป้าหมาย ${fps} fps (จริงอาจต่ำกว่าถ้า Pi/เครือข่ายช้า)` : "กำลังโหลดภาพ…"}
        {" "}· แสดงภาพอย่างเดียว ยังไม่ได้ส่งเข้า OCR/AI
      </p>
    </section>
  );
}
