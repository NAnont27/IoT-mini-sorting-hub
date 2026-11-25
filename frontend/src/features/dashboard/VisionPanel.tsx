"use client";

import type { Job } from "@/types/hub";

// AI-mode view of the active job: the label image the vision worker used and the public
// AI result. Recipient name/room text is deliberately not sent by the backend.
const outcomeLabels: Record<string, string> = {
  RESOLVED: "หาปลายทางได้",
  HOLD: "ส่งเข้า HOLD",
  RETRY_CAPTURE: "ขอถ่ายภาพใหม่",
  SERVICE_ERROR: "AI ใช้ไม่ได้ (พักรอลองใหม่)",
  PIPELINE_ERROR: "ระบบภาพ/OCR ผิดพลาด",
};

export function VisionPanel({ job }: { job: Job }) {
  const attempt = typeof job.vision_attempt === "number" ? job.vision_attempt : 1;
  const result = (job.vision_result ?? null) as Record<string, unknown> | null;
  const waiting = job.state === "WAIT_VISION";
  return (
    <div className="vision-panel" style={{ display: "grid", gap: 12, marginTop: 16 }}>
      <div className="section-heading"><div><p className="eyebrow">AI VISION</p><h3>ภาพฉลากและผล AI · ครั้งที่ {attempt}</h3></div></div>
      {/* eslint-disable-next-line @next/next/no-img-element -- per-job image served by backend */}
      <img
        key={`${job.job_id}-${attempt}-${waiting}-${Boolean(result)}`}
        src={`/api/camera/job/${job.job_id}/${attempt}.jpg`}
        alt="ภาพฉลากที่ใช้อ่าน"
        style={{ width: "100%", maxWidth: 640, borderRadius: 12, background: "#111" }}
        onError={(event) => { event.currentTarget.style.display = "none"; }}
      />
      {waiting && !result && <p className="muted">กำลังถ่ายภาพ อ่าน OCR และส่ง Gemini…</p>}
      {result && (
        <dl className="job-facts">
          <div><dt>ผล</dt><dd>{outcomeLabels[String(result.outcome)] ?? String(result.outcome)}</dd></div>
          <div><dt>ช่อง</dt><dd>{String(result.target_bin ?? "—")}</dd></div>
          <div><dt>ชั้น</dt><dd>{String(result.resolved_floor ?? "—")}</dd></div>
          <div><dt>เหตุผล</dt><dd><code>{String(result.reason_code ?? "—")}</code></dd></div>
        </dl>
      )}
    </div>
  );
}
