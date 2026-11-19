/** Browser requests stay same-origin; Next.js proxies /api to Flask. */
export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(12_000)]) : AbortSignal.timeout(12_000),
  });
  const text = await response.text();
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(`Backend ไม่ส่ง JSON (HTTP ${response.status}) ตรวจ Flask และ BACKEND_URL`);
  }
  if (!response.ok) {
    const error = data && typeof data === "object" && "error" in data ? String(data.error) : response.statusText;
    throw new Error(error || `HTTP ${response.status}`);
  }
  return data as T;
}
