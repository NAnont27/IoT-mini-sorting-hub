# จุดเชื่อมกับทีม AI — ยังไม่เปิดใช้ใน BENCH

อ้างอิง AI_TEAM_HANDOFF_PROMPT_TH.md ที่รากโปรเจกต์ โค้ดนี้ไม่ implement OCR/LLM/registry resolver ซ้ำ

## ทำงานอย่างไร

1. ระหว่างหยุดระบบและไม่มี job ค้าง ทีมแก้ backend/config.json ให้ mode=ai แล้ว restart backend ด้วยคำสั่งจากราก repo: `.venv/bin/python -m backend.app`
2. เมื่อวางกล่องนิ่งจะได้ WAIT_VISION แทน WAIT_DECISION
3. ทีม AI เรียก GET http://127.0.0.1:5000/api/ai/pending ถ้าไม่มีงานได้ {"job":null}
4. เมื่อมีงาน ให้รับ job_id และ vision_attempt ถ่ายภาพด้วยโมดูลกล้องของทีม AI ทำ OCR/Gemini/resolver ตามกฎเดิม แล้ว POST JSON ไป /api/ai/result
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
