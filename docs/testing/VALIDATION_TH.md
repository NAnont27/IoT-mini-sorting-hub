# สถานะการตรวจ Mini Sorting Hub

อัปเดต **16 พฤศจิกายน 2026** หลังจัด monorepo และย้ายหน้าเว็บเป็น Next.js

## ตรวจผ่านในเครื่องพัฒนา Windows

| การตรวจ | ผลและขอบเขต |
|---|---|
| Backend unittest | **28 ผ่าน**: state machine 20 + คำนวณวงจร R 3 + HTTP API/package migration 5 |
| Frontend lint | npm run lint ผ่าน |
| Frontend TypeScript | npm run typecheck ผ่าน และตรวจ TypeScript ระหว่าง build ผ่าน |
| Production build | npm run build ผ่านด้วย Next.js 16.4.6, React 19.3.0, Webpack และ Tailwind PostCSS |
| Production HTTP smoke | หน้า HTML และ /api proxy จาก Next.js :3000 ไป Flask :5000 ผ่าน GET/POST: status, pause, resume ถูกบล็อกเมื่อไม่มีเซนเซอร์, jobs, history fallback และ AI pending |
| เอกสาร | ตรวจ UTF-8, code fences และ local Markdown links ไม่มีพาธหาย |
| Git ignore | ตัด .env/config จริง/secrets.h, data, .venv, node_modules, .next, archive และ artifacts; ไฟล์ example/lockfileเข้า Git ได้ |

HTTP smoke ใช้ Flask API และ SQLite ชั่วคราวจริง แต่ **mock MQTT client และหยุด background workers** ไม่เชื่อมต่อ Pi/ESP32 หรือเปิดมอเตอร์ เซิร์ฟเวอร์ทดสอบหยุดหลังตรวจแล้ว

Tests state machine ตรวจ ACK ไม่เท่ากับถึงช่อง, มุมผิด/เก่า, กล่องผิดช่อง/ผิดลำดับ, pause, Node reboot, timeout, duplicate passage, reset ขณะยังมีของ, AI outage และผล AI เก่า ส่วน API tests ตรวจ entry point ใหม่, status, pending, readiness และการบันทึก settings ใน backend

## ข้อจำกัดการ build และ dependency

- Turbopack ของ scaffold ล้มขณะสร้าง worker บน Windows ที่ใช้ทดสอบ แม้ลองรันนอก sandbox จึงใช้ Webpack ผ่าน next dev/build --webpack และ Tailwind PostCSS ซึ่ง Next.js รองรับ ผล production build ผ่าน
- npm audit พบ **7 moderate เฉพาะ dependency ของเครื่องมือ lint ฝั่ง dev** จาก minimatch ผ่าน typescript-eslint; npm audit fix/update แบบไม่ force ยังไม่แก้รายการนี้ ไม่ฝืน override ข้าม major เพื่อซ่อนผลตรวจ
- npm audit --omit=dev ณ วันที่ตรวจพบ **0 vulnerabilities** ตรวจใหม่เมื่อติดตั้ง/อัปเดต dependency ไม่ถือว่าผลนี้รับรองในอนาคต

## ยังไม่ยืนยันบนอุปกรณ์จริง

- compile/upload firmware ด้วย Arduino toolchain และ libraries จริง
- Pi–Mosquitto–InfluxDB–ESP32 ผ่าน Wi-Fi/MQTT ทั้งระบบ; HTTP smoke ด้านบนไม่ใช่ผล integration นี้
- การวัดแรงดัน IR, calibration, ToF, การรับโหลด Servo และ IR สี่ตัวพร้อมกัน
- การย้าย config/data จริงจาก Pi เดิมและรัน Next.js production บน Pi
- กล้อง/OCR/Gemini/resolver/CSV และการคัดกล่องด้วยโครงจริง
- ความแม่นยำ เวลา throughput และผลเทียบการคัดโดยเจ้าหน้าที่

วงจร R v2 ใช้สมมติฐานไฟ 5V ±5%, R ±5%, GPIO VDD 3.3V และ NPN LOW ≤0.4V ในการคำนวณ ไม่ใช่ผลวัดเซนเซอร์ผู้ใช้

ทำตาม [คู่มือ BENCH](../setup/BENCH_SETUP_TH.md) ทีละช่วง และ [Migration](../setup/MIGRATION_TH.md) หากย้ายจากโครงเดิม อย่าใช้ unit tests/build หรือ BENCH แบบมือย้ายเป็นหลักฐานว่ากลไก/AI ทำงานครบแล้ว
