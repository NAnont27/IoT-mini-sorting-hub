"use client";

import { useState } from "react";

type Servo = "gate" | "chute";

// Firmware defaults (hub_node.ino): gate closed 90 / open 60; chute A60 / B90 / HOLD120.
const PRESETS: Record<Servo, { label: string; angle: number }[]> = {
  gate: [{ label: "ปิด 90°", angle: 90 }, { label: "เปิด 60°", angle: 60 }],
  chute: [{ label: "A 60°", angle: 60 }, { label: "B 90°", angle: 90 }, { label: "HOLD 120°", angle: 120 }],
};

export function ServoTestPanel({ enabled, onSend }: { enabled: boolean; onSend: (servo: Servo, angle: number) => void }) {
  const [servo, setServo] = useState<Servo>("chute");
  const [angle, setAngle] = useState(90);

  return (
    <div className="servo-test">
      <p className="control-note"><span>!</span> ทดสอบ Servo ได้เฉพาะตอนพัก (PAUSED_OPERATOR) และไม่มี job — ถอดราง/สิ่งกีดขวางก่อน คำสั่งนี้ไม่ใช้ AS5600 ยืนยันมุม</p>
      <div className="control-buttons">
        <select value={servo} disabled={!enabled} onChange={(e) => setServo(e.target.value as Servo)} aria-label="เลือก Servo">
          <option value="chute">MG996R ราง (GPIO7)</option>
          <option value="gate">MG90S ประตู (GPIO6)</option>
        </select>
        {PRESETS[servo].map((p) => (
          <button key={p.label} className="button secondary" disabled={!enabled} onClick={() => onSend(servo, p.angle)}>{p.label}</button>
        ))}
      </div>
      <div className="control-buttons">
        <input type="range" min={0} max={180} value={angle} disabled={!enabled} onChange={(e) => setAngle(Number(e.target.value))} aria-label="มุม" />
        <button className="button secondary" disabled={!enabled} onClick={() => onSend(servo, angle)}>ส่ง {angle}°</button>
      </div>
    </div>
  );
}
