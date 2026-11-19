"use client";

import { useState } from "react";
import type { HubSnapshot, TargetBin } from "@/types/hub";

interface Props {
  snapshot: HubSnapshot | null;
  disabled: boolean;
  onSave: (settings: Record<string, unknown>) => Promise<void>;
}

export function SettingsPanel({ snapshot, disabled, onSave }: Props) {
  const [weight, setWeight] = useState("");
  const [height, setHeight] = useState("");
  const blocked = disabled || !snapshot?.paused || Boolean(snapshot?.job);
  return <section className="panel">
    <h2>ตั้งต้นก่อนเริ่ม</h2>
    <p className="muted">ต้องพักรับงานและไม่มีงานค้าง กำหนดจากชุดทดลองที่วัดจริง</p>
    <form className="actions" onSubmit={(e) => {
      e.preventDefault();
      void onSave({ max_weight_g: Number(weight), max_height_mm: Number(height) });
    }}>
      <label>น้ำหนักสูงสุด (g)<input type="number" min="1" step="any" required value={weight} onChange={(e) => setWeight(e.target.value)} placeholder={String(snapshot?.config.max_weight_g ?? "ยังไม่ตั้ง")} disabled={blocked} /></label>
      <label>ความสูงสูงสุด (mm)<input type="number" min="1" step="any" required value={height} onChange={(e) => setHeight(e.target.value)} placeholder={String(snapshot?.config.max_height_mm ?? "ยังไม่ตั้ง")} disabled={blocked} /></label>
      <button type="submit" disabled={blocked}>บันทึกขีดจำกัด</button>
    </form>
    <p>วางแม่เหล็กที่มุมของแต่ละช่อง แล้วบันทึกมุมจาก AS5600 จริง ช่วงมุมต้องไม่ทับกัน</p>
    <div className="actions">{(["A", "B", "HOLD"] as TargetBin[]).map((bin) => <button key={bin} disabled={blocked} onClick={() => void onSave({ save_angle_for: bin })}>จำมุมนี้เป็น {bin}</button>)}</div>
    <details><summary>ค่าตั้งปัจจุบัน</summary><pre>{JSON.stringify(snapshot?.config ?? {}, null, 2)}</pre></details>
  </section>;
}
