"use client";

import { useState } from "react";
import { api } from "@/lib/api/client";
import type { History, Metric } from "@/types/hub";

const metrics: { value: Metric; label: string }[] = [
  { value: "weight_g", label: "น้ำหนัก (g)" },
  { value: "height_mm", label: "ความสูง (mm)" },
  { value: "angle_deg", label: "มุมราง (°)" },
  { value: "light_lux", label: "ความสว่าง (lux)" },
];

export function HistoryPanel() {
  const [metric, setMetric] = useState<Metric>("weight_g");
  const [loadedMetric, setLoadedMetric] = useState<Metric>("weight_g");
  const [history, setHistory] = useState<History | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setHistory(await api<History>(`/api/history?metric=${metric}`));
      setLoadedMetric(metric);
    } catch (error) {
      setHistory(null);
      setError(error instanceof Error ? error.message : "โหลดประวัติไม่ได้");
    } finally {
      setLoading(false);
    }
  }

  const points = history?.points.filter((p) => Number.isFinite(p.value)) ?? [];
  const values = points.map((p) => p.value);
  const lo = values.length ? Math.min(...values) : 0;
  const hi = values.length ? Math.max(...values) : 0;
  const span = hi - lo || 1;
  const line = values.map((value, i) => `${30 + (i * 940) / Math.max(1, values.length - 1)},${180 - ((value - lo) / span) * 140}`).join(" ");

  return <section className="panel">
    <div className="section-heading"><div><p className="eyebrow">TELEMETRY HISTORY</p><h2>กราฟย้อนหลัง</h2></div>{history && <span className="summary-chip ready">{history.source}</span>}</div>
    <p className="muted">ดึงจากฐานข้อมูลเมื่อกดโหลด แสดงแหล่งข้อมูลตามจริง</p>
    <div className="actions">
      <label>ค่าที่ต้องการดู <select value={metric} onChange={(e) => setMetric(e.target.value as Metric)}>
        {metrics.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
      </select></label>
      <button onClick={load} disabled={loading}>{loading ? "กำลังโหลด…" : "โหลดกราฟ"}</button>
    </div>
    {error && <p role="alert" className="error">{error}</p>}
    {history && <p className={history.source === "InfluxDB" ? "muted" : "warning"}>{history.source} · {points.length} จุด · {loadedMetric}</p>}
    {history && !points.length && <p className="muted">ไม่มีข้อมูลในช่วงเวลานี้</p>}
    {points.length > 0 && <figure className="chart-frame">
      <svg viewBox="0 0 1000 220" role="img" aria-label={`กราฟ ${loadedMetric} ต่ำสุด ${lo.toFixed(2)} สูงสุด ${hi.toFixed(2)}`}>
        {[45, 80, 115, 150, 185].map((y) => <line key={y} x1="30" y1={y} x2="970" y2={y} stroke="currentColor" opacity="0.08" />)}
        <text x="30" y="20" fontSize="14" fill="currentColor">min {lo.toFixed(2)} · max {hi.toFixed(2)}</text>
        <polyline points={line} fill="none" stroke="var(--green)" strokeWidth="3" />
        {points.length === 1 && <circle cx="30" cy="180" r="4" fill="var(--green)" />}
        <text x="30" y="212" fontSize="12" fill="currentColor">{points[0].time}</text>
        <text x="970" y="212" textAnchor="end" fontSize="12" fill="currentColor">{points[points.length - 1].time}</text>
      </svg>
    </figure>}
  </section>;
}
