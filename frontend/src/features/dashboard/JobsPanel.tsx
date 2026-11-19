"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { Job } from "@/types/hub";

export function JobsPanel() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const data = await api<Job[]>(`/api/jobs?q=${encodeURIComponent(search)}`, undefined, controller.signal);
        if (!controller.signal.aborted) { setJobs(data); setError(""); }
      } catch (error) {
        if (!controller.signal.aborted) setError(error instanceof Error ? error.message : "โหลดรายการไม่ได้");
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(poll, 5000);
      }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [search, revision]);

  return <section className="panel">
    <h2>ประวัติการคัดแยก</h2>
    <form className="actions" onSubmit={(e) => { e.preventDefault(); setSearch(query); setRevision((n) => n + 1); }}>
      <label className="grow">ค้นหางาน <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="job_id / ชื่อ / ห้อง / ข้อมูลในงาน" /></label>
      <button type="submit">ค้นหา</button>
    </form>
    {error && <p role="alert" className="error">{error} · รายการด้านล่างอาจเป็นข้อมูลเก่า</p>}
    <div className="table-scroll"><table>
      <thead><tr><th>เวลา</th><th>งาน / โหมด</th><th>ช่อง</th><th>ผล</th><th>เหตุผล</th></tr></thead>
      <tbody>{jobs.map((job) => <tr key={job.job_id}>
        <td>{new Date(job.created).toLocaleString("th-TH", { timeZone: "Asia/Bangkok" })}</td>
        <td><code>{job.job_id}</code><br /><small>{job.mode.toUpperCase()}</small></td>
        <td>{job.target_bin ?? "—"}</td><td>{job.result ?? job.state}</td><td>{job.reason ?? "—"}</td>
      </tr>)}</tbody>
    </table></div>
    {!jobs.length && !error && <p className="muted">ยังไม่มีรายการ</p>}
  </section>;
}
