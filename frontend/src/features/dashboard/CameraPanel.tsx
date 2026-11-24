"use client";

import { useEffect, useState } from "react";

// Live preview from Camera Module 3 on the Pi via Flask /api/camera/snapshot.jpg.
// Polls one JPEG at a time (next request only after the previous image loads/fails).
const REFRESH_MS = 1000;

export function CameraPanel() {
  const [running, setRunning] = useState(true);
  const [tick, setTick] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState<string | null>(null);

  useEffect(() => {
    if (!running) return;
    const timer = window.setTimeout(() => setTick((value) => value + 1), REFRESH_MS);
    return () => window.clearTimeout(timer);
  }, [running, tick, loadedAt, error]);

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
        <button className="button secondary" onClick={() => setRunning((value) => !value)}>{running ? "หยุดภาพ" : "เริ่มภาพ"}</button>
      </div>
      <div className="camera-frame">
        {/* eslint-disable-next-line @next/next/no-img-element -- live JPEG from backend, not a static asset */}
        <img
          src={`/api/camera/snapshot.jpg?t=${tick}`}
          alt="ภาพจาก Camera Module 3"
          style={{ width: "100%", maxWidth: 960, aspectRatio: "16 / 9", objectFit: "contain", background: "#111", borderRadius: 12 }}
          onLoad={() => { setError(null); setLoadedAt(new Date().toLocaleTimeString("th-TH")); }}
          onError={() => { void explainFailure(); }}
        />
      </div>
      <p className="refresh-note">
        {error ? `⚠ ${error}` : loadedAt ? `ภาพล่าสุด ${loadedAt} · รีเฟรชประมาณทุก 1 วินาที` : "กำลังโหลดภาพ…"}
        {" "}· แสดงภาพอย่างเดียว ยังไม่ได้ส่งเข้า OCR/AI
      </p>
    </section>
  );
}
