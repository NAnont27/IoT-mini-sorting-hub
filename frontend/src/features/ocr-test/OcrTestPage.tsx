"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

// Test bench for the AI team: one image -> PaddleOCR -> Gemini extraction -> demo registry.
// Calls Flask POST /api/ai/test; it never creates jobs or moves motors.

interface OcrLine { text: string; confidence: number }
interface TestReport {
  ocr: { engine: string; text: string; mean_confidence: number | null; dropped_low_confidence: number; lines: OcrLine[] };
  timings_ms: Record<string, number | null>;
  extraction: { status: string; reason: string | null; source: string | null; fields: Record<string, unknown> | null; grounding_issues: string[] } | null;
  resolution: { outcome: string; target_bin: string | null; resolved_room: string | null; resolved_floor: number | null; reason_code: string; evidence?: unknown } | null;
  ai_error: string | null;
  registry: string;
}

const fieldLabels: Record<string, string> = {
  recipient_name_raw: "ชื่อผู้รับ", recipient_room: "ห้อง", recipient_floor: "ชั้น",
  tracking_id: "เลขพัสดุ", source_excerpt: "ข้อความที่ใช้อ้างอิง", issues: "ข้อสังเกตของ AI",
};

function ms(value: number | null | undefined) {
  return typeof value === "number" ? `${(value / 1000).toFixed(2)} s` : "—";
}

export function OcrTestPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [useAi, setUseAi] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<TestReport | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);

  // Release the object URL when it is replaced or the page unmounts.
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  function choose(next: File | null) {
    setFile(next);
    setReport(null);
    setPreview(next ? URL.createObjectURL(next) : null);
  }

  async function run(capture: boolean) {
    setBusy(true); setError(null); setReport(null);
    const started = performance.now();
    try {
      const query = `ai=${useAi ? 1 : 0}${capture ? "&capture=1" : ""}`;
      const response = await fetch(`/api/ai/test?${query}`, {
        method: "POST",
        headers: capture || !file ? undefined : { "Content-Type": file.type || "application/octet-stream" },
        body: capture || !file ? undefined : file,
        cache: "no-store",
        signal: AbortSignal.timeout(130_000),
      });
      const data = await response.json().catch(() => ({ error: `Backend ไม่ส่ง JSON (HTTP ${response.status})` }));
      if (!response.ok) throw new Error(data.error ?? `HTTP ${response.status}`);
      setReport(data as TestReport);
      if (capture) setPreview(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setElapsed(performance.now() - started);
      setBusy(false);
    }
  }

  const fields = report?.extraction?.fields ?? null;
  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 16px", display: "grid", gap: 20 }}>
      <header className="section-heading">
        <div><p className="eyebrow">AI TEST BENCH</p><h1>ทดสอบ OCR และ Extraction</h1>
          <p className="muted">ภาพ → OpenCV + PaddleOCR → Gemini → ทะเบียนตัวอย่าง (ไม่สร้าง job และไม่ขยับกลไก) · ใช้ฉลากข้อมูลสมมติเท่านั้น</p></div>
        <Link className="button secondary" href="/">← กลับหน้าควบคุม</Link>
      </header>

      <section className="content-section" style={{ display: "grid", gap: 12 }}>
        <div className="actions" style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
          <input type="file" accept="image/jpeg,image/png" disabled={busy} onChange={(e) => choose(e.target.files?.[0] ?? null)} />
          <button className="button" disabled={busy || !file} onClick={() => void run(false)}>อ่านภาพที่อัปโหลด</button>
          <button className="button secondary" disabled={busy} onClick={() => void run(true)}>ถ่ายจากกล้อง Pi แล้วอ่าน</button>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}><input type="checkbox" checked={useAi} disabled={busy} onChange={(e) => setUseAi(e.target.checked)} />ส่ง Gemini ด้วย (ปิด = OCR อย่างเดียว ไม่ใช้โควต้า)</label>
        </div>
        {busy && <p className="muted">กำลังประมวลผล… ครั้งแรกบน Pi อาจนานเพราะโหลดโมเดล OCR</p>}
        {error && <p className="danger-text">⚠ {error}</p>}
        {elapsed !== null && !busy && <p className="refresh-note">เวลารวมจากหน้าเว็บ {ms(elapsed)}</p>}
        {/* eslint-disable-next-line @next/next/no-img-element -- local preview of the uploaded file */}
        {preview && <img src={preview} alt="ภาพที่เลือก" style={{ maxWidth: "100%", maxHeight: 360, objectFit: "contain", borderRadius: 12 }} />}
      </section>

      {report && (
        <>
          <section className="content-section" style={{ display: "grid", gap: 12 }}>
            <div className="section-heading"><div><p className="eyebrow">1 · OCR ({report.ocr.engine})</p><h2>ข้อความที่อ่านได้</h2></div>
              <span className="summary-chip ready">ความมั่นใจเฉลี่ย {report.ocr.mean_confidence ?? "—"}</span></div>
            {report.ocr.lines.length === 0 ? <p className="muted">ไม่พบข้อความ (ในระบบจริงจะเป็น RETRY_CAPTURE)</p> : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead><tr><th style={{ textAlign: "left" }}>บรรทัด</th><th style={{ textAlign: "right" }}>ความมั่นใจ</th></tr></thead>
                <tbody>{report.ocr.lines.map((line, index) => (
                  <tr key={index} style={{ borderTop: "1px solid rgba(127,127,127,.25)" }}>
                    <td style={{ padding: "6px 0" }}>{line.text}</td>
                    <td style={{ textAlign: "right", color: line.confidence < 0.8 ? "#c2410c" : undefined }}>{line.confidence.toFixed(3)}</td>
                  </tr>))}</tbody>
              </table>)}
            {report.ocr.dropped_low_confidence > 0 && <p className="muted">ตัดบรรทัดความมั่นใจต่ำออก {report.ocr.dropped_low_confidence} บรรทัด</p>}
          </section>

          <section className="content-section" style={{ display: "grid", gap: 12 }}>
            <div className="section-heading"><div><p className="eyebrow">2 · EXTRACTION (GEMINI)</p><h2>ข้อมูลผู้รับที่ AI แยกได้</h2></div>
              {report.extraction && <span className={`summary-chip ${report.extraction.status === "OK" ? "ready" : "needs-attention"}`}>{report.extraction.status}{report.extraction.source ? ` · ${report.extraction.source}` : ""}</span>}</div>
            {!useAi && !report.extraction && <p className="muted">ปิดการส่ง Gemini ไว้</p>}
            {report.ai_error && <p className="danger-text">AI ใช้ไม่ได้: {report.ai_error} (ตรวจ ai/.env บนเครื่องที่รัน backend)</p>}
            {report.extraction?.reason && <p className="muted">เหตุผล: <code>{report.extraction.reason}</code></p>}
            {fields && (
              <dl className="job-facts">{Object.entries(fields).map(([key, value]) => (
                <div key={key}><dt>{fieldLabels[key] ?? key}</dt><dd>{Array.isArray(value) ? (value.length ? value.join(", ") : "—") : String(value ?? "—")}</dd></div>))}</dl>)}
            {report.extraction && report.extraction.grounding_issues.length > 0 && (
              <p className="danger-text">ค่าที่ไม่พบในข้อความ OCR: {report.extraction.grounding_issues.join(", ")}</p>)}
          </section>

          <section className="content-section" style={{ display: "grid", gap: 12 }}>
            <div className="section-heading"><div><p className="eyebrow">3 · RESOLVE</p><h2>ผลเทียบทะเบียน → ช่อง</h2></div></div>
            {report.resolution ? (
              <dl className="job-facts">
                <div><dt>ผล</dt><dd>{report.resolution.outcome}</dd></div>
                <div><dt>ช่อง</dt><dd>{report.resolution.target_bin ?? "—"}</dd></div>
                <div><dt>ห้อง / ชั้น</dt><dd>{report.resolution.resolved_room ?? "—"} / {report.resolution.resolved_floor ?? "—"}</dd></div>
                <div><dt>เหตุผล</dt><dd><code>{report.resolution.reason_code}</code></dd></div>
              </dl>) : <p className="muted">ยังไม่มีผล (ต้องได้ extraction = OK ก่อน)</p>}
            <p className="refresh-note">ทะเบียน: {report.registry} · เวลา preprocess {ms(report.timings_ms.preprocess)} · OCR {ms(report.timings_ms.ocr)} · AI {ms(report.timings_ms.ai)} · resolve {ms(report.timings_ms.resolve)}</p>
          </section>
        </>
      )}
    </main>
  );
}
