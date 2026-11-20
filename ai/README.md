# โมดูล AI — Mini Sorting Hub

สถานะ: **resolver + extraction + CLI ใช้งานได้** เรียก Gemini จริงได้แล้วจาก CLI (ตรวจด้วยข้อความ OCR สมมติ 2 ชุด) ยังไม่มีกล้องหรือ OCR ในโฟลเดอร์นี้ ต้องใส่ข้อความ OCR เอง และยังไม่ได้เชื่อมกับ Backend จริง

## ขั้นตอนการประมวลผล

```
ข้อความ OCR → prompt → Gemini → JSON → ตรวจ schema → ตรวจว่าค่ามีอยู่ใน OCR → resolver (ทะเบียน) → envelope
```

## ไฟล์สำคัญ

| ไฟล์ | หน้าที่ |
|---|---|
| `mini_sorting_ai/registry.py` | โหลด CSV ทะเบียนและ config เป็น snapshot ตรวจค่าว่าง, resident_id ซ้ำ, ห้องที่ map หลายชั้น, ชั้นนอก valid_floors |
| `mini_sorting_ai/prompt.py` | สร้าง prompt ห่อข้อความ OCR ด้วยขอบเขตกันการปลอมคำสั่ง |
| `mini_sorting_ai/gemini_client.py` | `GeminiClient` เรียก Gemini (อ่าน key/โมเดลจาก env, retry จำกัด) และ `MockClient` (แสดง source=mock) |
| `mini_sorting_ai/extraction_schema.py` | ตรวจรูปแบบ JSON ของผล AI |
| `mini_sorting_ai/extraction.py` | `extract_recipient()` ต่อ prompt → client → schema → ตรวจหลักฐานกับ OCR |
| `mini_sorting_ai/resolver.py` | กฎ A/B/HOLD/RETRY_CAPTURE และ envelope ตาม `docs/ai/AI_INTERFACE_TH.md` |
| `mini_sorting_ai/pipeline.py` | `process_ocr_text()` รวม extraction และ resolver ให้ได้ envelope ของ Backend |
| `mini_sorting_ai/cli.py` | CLI รับไฟล์ OCR แล้วพิมพ์ envelope JSON |
| `run_with_env.py` | เหมือน CLI แต่โหลด `ai/.env` ให้อัตโนมัติ (ไม่พิมพ์ key) |
| `fixtures/` | ทะเบียนสมมติ, ข้อความ OCR ตัวอย่าง และผลจำลอง |
| `.env.example` | ตัวอย่างค่า environment (ไม่มี key จริง) |

## ตั้งค่า (ทำครั้งเดียว)

1. ติดตั้ง SDK (ต้องใช้เฉพาะตอนเรียก Gemini จริง เทสต์และ mock ไม่ต้องใช้):

   ```powershell
   pip install google-genai
   ```

2. สร้างไฟล์ `ai/.env` จาก `ai/.env.example` แล้วใส่ค่าในเครื่องเท่านั้น

   ```
   GEMINI_API_KEY=<key ของคุณ>
   GEMINI_MODEL=<ชื่อโมเดลที่ยืนยันจากบัญชีของคุณ>
   ```

   `ai/.env` อยู่ใน `.gitignore` แล้ว ห้าม commit หรือใส่ key ในไฟล์อื่น
   ตอนนี้ใช้ `gemini-3.6-flash` ตามผลค้นหาที่ยังไม่ได้ยืนยันจากหน้าทางการโดยตรง ให้ตรวจในรายการโมเดลของ AI Studio ก่อน

## วิธีรัน (PowerShell, จากรากรีโพ `IoT-mini-sorting-hub`)

**ก. รันเทสต์ ไม่ใช้ key**

```powershell
python -m unittest discover -s ai/tests -v
```

ผลที่ถูกต้อง: `Ran 77 tests ... OK`

**ข. รันกับ Gemini จริง**

```powershell
$env:PYTHONIOENCODING = "utf-8"
python ai/run_with_env.py --ocr ai/fixtures/ocr_demo.txt --job-id JOB-0001
```

**ค. รันด้วยผลจำลอง ไม่ใช้ key**

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m mini_sorting_ai.cli --ocr ai/fixtures/ocr_demo.txt --job-id JOB-0001 --mock-response ai/fixtures/mock_response_demo.json
```

หรือรันจากโฟลเดอร์ `ai` โดยเปลี่ยน path เป็น `fixtures/ocr_demo.txt` ถ้า import ไม่เจอ

**ใช้ฉลากของคุณเอง**
- เขียนข้อความ OCR ลงไฟล์ UTF-8 เช่น `ai/fixtures/my_label.txt`
- เปลี่ยน `--ocr` และ `--job-id` ตามต้องการ
- ใช้ข้อมูลสมมติเท่านั้น เพราะ free tier อาจนำเนื้อหาไปปรับปรุงผลิตภัณฑ์

## อ่านผลลัพธ์

| ฟิลด์ | ความหมาย |
|---|---|
| `outcome` | `RESOLVED` = หาปลายทางได้, `HOLD` = รอตรวจ, `RETRY_CAPTURE` = ขอถ่ายซ้ำ, `SERVICE_ERROR` = AI ใช้ไม่ได้, `PIPELINE_ERROR` = config/ไฟล์ผิด |
| `target_bin` | `A`, `B`, `HOLD` หรือ `null` |
| `reason_code` | เหตุผลการตัดสิน เช่น `RESOLVED_ROOM_AND_NAME`, `HOLD_CONFLICT_ROOM_NAME` |
| `extraction_source` | `gemini` = เรียกจริงแล้วได้ผลตอบ, `mock` = ผลจำลอง (ห้ามรายงานเป็นผล Gemini) |
| `grounding_issues` | ค่าที่ AI ตอบแต่ไม่พบในข้อความ OCR และถูกตัดทิ้ง |
| `timings_ms.resolve` | เวลาเฉพาะขั้น resolver ยังไม่มีเวลาของขั้น AI และ OCR |

**exit code**
- `0` = ได้ผลตัดสินปกติ (`RESOLVED`, `HOLD`, `RETRY_CAPTURE`)
- `1` = `SERVICE_ERROR` เช่น ไม่มี key, key ผิด หรือ AI ตอบผิดรูปแบบ
- `2` = ไฟล์ทะเบียน/config/OCR อ่านไม่ได้ (`PIPELINE_ERROR`)

## ปัญหาที่พบบ่อย

| อาการ | สาเหตุและวิธีแก้ |
|---|---|
| `ModuleNotFoundError: google` | ยังไม่ได้ `pip install google-genai` |
| `AI_NOT_CONFIGURED_KEY` | ไม่มี `GEMINI_API_KEY` ใน `ai/.env` |
| `AI_NOT_CONFIGURED_MODEL` | ไม่มี `GEMINI_MODEL` ใน `ai/.env` |
| `AI_UNAVAILABLE` | key ผิด, โมเดลไม่มีในบัญชี หรือเน็ตมีปัญหา ตรวจ key/โมเดลก่อน |
| `AI_INVALID_RESPONSE` | Gemini ตอบไม่เป็น JSON หรือไม่ผ่าน schema |
| ภาษาไทยเป็นตัวอักษรแปลกบนคอนโซล | ตั้ง `$env:PYTHONIOENCODING = "utf-8"` ก่อนรัน |
| ผลเป็น `mock` ทั้งที่ตั้งใจเรียกจริง | คุณใช้ `--mock-response` อยู่ ให้ลบออก |

## ขอบเขตที่ยังไม่ทำ

- ยังไม่มี OCR และยังไม่มี camera adapter บน Pi
- ยังไม่มีการวัดเวลาของขั้น AI และ API รวม และยังไม่มีชุดภาพฉลากพร้อมเฉลยสำหรับวัด accuracy
- ยังไม่ได้เชื่อม `/api/ai/pending` และ `/api/ai/result` ของ Backend
- CLI ยังไม่ retry เมื่อ `RETRY_CAPTURE` (Backend เป็นผู้คุมจำนวนรอบ)
- ค่า `a_max_floor` และ `valid_floors` ใน config เป็นค่าสมมติ ยังไม่ใช่ค่าที่ทีมล็อกแล้ว
