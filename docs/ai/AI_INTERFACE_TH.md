# จุดเชื่อมกับทีม AI

อ้างอิง AI_TEAM_HANDOFF_PROMPT_TH.md ที่รากโปรเจกต์ backend ไม่ implement OCR/LLM/registry resolver ซ้ำ ผู้เรียกจริงคือ vision worker `ai/mini_sorting_ai/worker.py` (รันด้วย `ai/run_worker.py`) ซึ่งรันบน**คอม** ตาม D026 เพราะ PaddleOCR segfault บน Pi 5

## ทำงานอย่างไร

1. ระหว่างพักและไม่มี job ค้าง สลับโหมดที่หน้าเว็บ → ตั้งค่า → "เปลี่ยนเป็น AI" (หรือ `POST /api/settings {"mode":"ai"}`) ไม่ต้อง restart
2. เมื่อวางกล่องนิ่งจะได้ WAIT_VISION แทน WAIT_DECISION
3. worker เรียก GET http://<IP Pi>:5000/api/ai/pending ถ้าไม่มีงานได้ {"job":null}
4. เมื่อมีงาน worker ขอภาพจาก backend ด้วย `POST /api/camera/capture {"job_id","vision_attempt"}` (backend เป็นเจ้าของกล้อง ถ่ายใหม่ทุกครั้ง เก็บ `backend/data/images/<job>_a<n>.jpg` และตอบ JPEG + header `X-Image-Path`) แล้ว OCR (OpenCV + PaddleOCR) → Gemini → resolver และ POST JSON ไป /api/ai/result; ถ่ายภาพ/OCR ไม่ได้ส่ง `PIPELINE_ERROR`
5. ทั้ง job_id และ vision_attempt ต้องตรงงานที่รออยู่ หาก timeout/retry ไปแล้วไม่รับผลเก่ามาสั่ง Servo

## ตัวอย่าง pending

```json
{"job":{"job_id":"JOB-example","vision_attempt":1,"weight_g":123.4,"height_mm":65,"capture_required":true}}
```

## ตัวอย่าง result หลัง deterministic resolver

```json
{
  "job_id":"JOB-example",
  "vision_attempt":1,
  "outcome":"RESOLVED",
  "resolved_room":"202",
  "resolved_floor":2,
  "target_bin":"A",
  "reason_code":"RESOLVED_ROOM_AND_NAME",
  "tracking_id":null,
  "registry_version":"demo-v1",
  "a_max_floor":3,
  "artifacts":{"image_path":"path-managed-by-ai-team"}
}
```

นี่เป็นตัวอย่าง schema ไม่ใช่ผล AI จริง Backend เชื่อใจทีม AI resolver ที่รับผิดชอบตรวจทะเบียน ต้องไม่ส่งผลดิบจาก LLM เป็น RESOLVED โดยข้ามกฎ

outcome: RESOLVED(A/B), HOLD(HOLD), RETRY_CAPTURE(null), SERVICE_ERROR(null), PIPELINE_ERROR(null)

- SERVICE_ERROR → PAUSED_AI ค้างงาน ไม่แปลงเป็น HOLD
- RETRY_CAPTURE → เพิ่ม attempt แบบจำกัด; ครบแล้ว HOLD
- PIPELINE_ERROR → FAULT ให้ตรวจปัญหา
- missing tracking_id ไม่ขวางการคัด
- โหมดนี้ยังใช้คนย้ายกล่องผ่าน IR จึง passage_simulated=true แม้ AI จริง

ต้องเก็บ snapshot ทะเบียน/ชั้นคั่นชุดเดิมในฝั่ง AI ตลอด job การอัปโหลด/preview CSV และการจัดเก็บภาพ/แสดงภาพในเว็บเป็นงานต่อเชื่อมก่อนรุ่นส่งงาน ไม่อยู่ใน BENCH ชุดแรก

อย่ารัน client AI หลายตัวรับ job เดียวกัน การเรียก pending เป็นการดูงาน ไม่ใช่ distributed job claim; เริ่มจาก worker เดียวและจำคู่ (job_id,vision_attempt) ที่ทำไปแล้ว


## Endpoint ที่เพิ่ม 25 พ.ย.

| Method/Path | อยู่ที่ | ใช้ทำอะไร |
|---|---|---|
| `POST /api/camera/capture` | Flask บน Pi | worker ขอภาพสดของ job ที่ `WAIT_VISION` ตรง job_id/vision_attempt เท่านั้น |
| `GET /api/camera/job/<job_id>/<n>.jpg` | Flask บน Pi | ภาพที่ใช้อ่านของ job/attempt (หน้า VisionPanel) |
| `GET /api/camera/snapshot.jpg`, `/api/camera/status` | Flask บน Pi | ภาพพรีวิวบน Dashboard และสถานะกล้อง |
| `POST /api/settings {"mode":"bench"/"ai"}` | Flask บน Pi | สลับโหมด เฉพาะตอนพักและไม่มี job |
| `POST /api/ai/test?ai=0/1[&capture=1]` | `ai/run_test_server.py` บนคอม :5100 (Next rewrite) | หน้า /ocr-test: ภาพเดียว → OCR → Gemini → ทะเบียนตัวอย่าง ไม่สร้าง job/ไม่ขยับกลไก; Flask บน Pi ก็มี route เดียวกันแต่รัน Paddle ใน child process ซึ่ง segfault บน Pi 5 |

ชื่อ/ห้องผู้รับไม่ถูกเก็บใน job (เก็บเฉพาะ `VISION_PUBLIC_FIELDS`) แต่หน้า /ocr-test แสดงข้อความ OCR และฟิลด์ที่แยกได้ จึงใช้ฉลากข้อมูลสมมติเท่านั้น
