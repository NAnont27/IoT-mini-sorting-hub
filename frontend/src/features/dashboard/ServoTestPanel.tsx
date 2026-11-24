"use client";

import { useState } from "react";

type Servo = "gate" | "chute";

// User request 24 Nov: only the two command ends. Firmware maps 0/180 to its attach range
// (hub_node: 1000/2000 us), so these are command limits, NOT calibrated physical angles.
const ENDS = [
  { label: "ซ้ายสุด (0°)", angle: 0 },
  { label: "ขวาสุด (180°)", angle: 180 },
];

export function ServoTestPanel({ enabled, onSend }: { enabled: boolean; onSend: (servo: Servo, angle: number) => void }) {
  const [servo, setServo] = useState<Servo>("chute");

  return (
    <div className="servo-test">
      <p className="control-note"><span>!</span> ทดสอบ Servo ได้เฉพาะตอนพัก (PAUSED_OPERATOR) และไม่มี job — ถอดราง/สิ่งกีดขวางก่อน คำสั่งนี้ไม่ใช้ AS5600 ยืนยันมุม</p>
      <div className="control-buttons">
        <select value={servo} disabled={!enabled} onChange={(e) => setServo(e.target.value as Servo)} aria-label="เลือก Servo">
          <option value="chute">MG996R ราง (GPIO7)</option>
          <option value="gate">MG90S ประตู (GPIO6)</option>
        </select>
        {ENDS.map((p) => (
          <button key={p.label} className="button secondary" disabled={!enabled} onClick={() => onSend(servo, p.angle)}>{p.label}</button>
        ))}
      </div>
    </div>
  );
}
