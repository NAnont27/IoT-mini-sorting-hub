# สถานะการตรวจ Mini Sorting Hub

อัปเดต **20 พฤศจิกายน 2026** หลังปรับ operator console และเพิ่ม HTTP boundary validation

## ตรวจผ่านในเครื่องพัฒนา Windows

| การตรวจ | ผลและขอบเขต |
|---|---|
| Backend unittest | **31 ผ่าน**: state machine 20 + คำนวณวงจร R 3 + HTTP API/package/boundary validation 8 |
| Frontend lint | npm run lint ผ่าน ไม่มี error/warning |
| Frontend TypeScript | npm run typecheck ผ่าน และตรวจ TypeScript ระหว่าง build ผ่าน |
| Production build | npm run build ผ่านด้วย Next.js 16.4.6, React 19.3.0, Webpack และ Tailwind PostCSS |
| Local HTTP preview | Next.js dev server ตอบ `GET /` เป็น 200; เครื่องมือ browser preview หมดเวลาจึงยังไม่มี screenshot/visual QA จาก browser ในรอบ 20 พ.ย. |
| Production HTTP smoke | หน้า HTML และ /api proxy จาก Next.js :3000 ไป Flask :5000 ผ่าน GET/POST: status, pause, resume ถูกบล็อกเมื่อไม่มีเซนเซอร์, jobs, history fallback และ AI pending |
| เอกสาร | ตรวจ UTF-8, code fences และ local Markdown links ไม่มีพาธหาย |
| Git ignore | ตัด .env/config จริง/secrets.h, data, .venv, node_modules, .next, archive และ artifacts; ไฟล์ example/lockfileเข้า Git ได้ |

HTTP smoke ใช้ Flask API และ SQLite ชั่วคราวจริง แต่ **mock MQTT client และหยุด background workers** ไม่เชื่อมต่อ Pi/ESP32 หรือเปิดมอเตอร์ เซิร์ฟเวอร์ทดสอบหยุดหลังตรวจแล้ว

Tests state machine ตรวจ ACK ไม่เท่ากับถึงช่อง, มุมผิด/เก่า, กล่องผิดช่อง/ผิดลำดับ, pause, Node reboot, timeout, duplicate passage, reset ขณะยังมีของ, AI outage และผล AI เก่า ส่วน API tests ตรวจ entry point, status, pending, readiness, การบันทึก settings, JSON body, action ที่ขาด, setting ที่ไม่รู้จัก และขอบเขตคำค้น

## ข้อจำกัดการ build และ dependency

- Turbopack ของ scaffold ล้มขณะสร้าง worker บน Windows ที่ใช้ทดสอบ แม้ลองรันนอก sandbox จึงใช้ Webpack ผ่าน next dev/build --webpack และ Tailwind PostCSS ซึ่ง Next.js รองรับ ผล production build ผ่าน
- npm audit พบ **7 moderate เฉพาะ dependency ของเครื่องมือ lint ฝั่ง dev** จาก minimatch ผ่าน typescript-eslint; npm audit fix/update แบบไม่ force ยังไม่แก้รายการนี้ ไม่ฝืน override ข้าม major เพื่อซ่อนผลตรวจ
- npm audit --omit=dev ณ วันที่ตรวจพบ **0 vulnerabilities** ตรวจใหม่เมื่อติดตั้ง/อัปเดต dependency ไม่ถือว่าผลนี้รับรองในอนาคต

## ยังไม่ยืนยันบนอุปกรณ์จริง

- compile/upload firmware ด้วย Arduino toolchain และ libraries จริง
- Pi–Mosquitto–InfluxDB–ESP32 ผ่าน Wi-Fi/MQTT ทั้งระบบ; HTTP smoke ด้านบนไม่ใช่ผล integration นี้
- การวัดแรงดัน IR, calibration, ToF, การรับโหลด Servo และ IR ถาดตัวเดียว (D011) ขณะวาง/ยกกล่องจริง
- การย้าย config/data จริงจาก Pi เดิม และการเชื่อม Next.js บนคอมไป Flask บน Pi ผ่าน LAN จริง
- กล้องจริงบน Pi กับ OCR/Gemini บนคอมผ่าน LAN, CSV ทะเบียนจริง และการคัดกล่องด้วยโครงจริง (25 พ.ย. ตรวจในเครื่องแล้วเท่านั้น: PaddleOCR อ่านฉลากสมมติสังเคราะห์ถูกครบ conf 0.96, ~2.8–3.8 s/ภาพ; Gemini จริง → RESOLVED/A; E2E backend (MQTT จำลอง) + worker → controller POSITION/A; PaddlePaddle บน Pi 5 segfault จึงย้าย OCR ไปคอม D026)
- ความแม่นยำ เวลา throughput และผลเทียบการคัดโดยเจ้าหน้าที่

วงจร R v2 ใช้สมมติฐานไฟ 5V ±5%, R ±5%, GPIO VDD 3.3V และ NPN LOW ≤0.4V ในการคำนวณ ไม่ใช่ผลวัดเซนเซอร์ผู้ใช้

ทำตาม [คู่มือ BENCH](../setup/BENCH_SETUP_TH.md) ทีละช่วง และ [Migration](../setup/MIGRATION_TH.md) หากย้ายจากโครงเดิม อย่าใช้ unit tests/build หรือ BENCH แบบมือย้ายเป็นหลักฐานว่ากลไก/AI ทำงานครบแล้ว
