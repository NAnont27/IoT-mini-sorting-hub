# Startup — เปิดระบบใหม่ (รอบถัดไป)

อัปเดต 25 พ.ย. 2026 · ใช้เมื่อเคยติดตั้งครบแล้ว (คู่มือ BENCH ขั้น 8–13 และหัวข้อ 18 สำหรับโหมด AI) ถ้าไม่ได้แก้โค้ด/config **ไม่ต้อง** `apt`, `pip`, `npm ci` หรือ upload firmware ใหม่

| เครื่อง | รันอะไร |
|---|---|
| Pi | Mosquitto, InfluxDB (Docker), backend :5000 (controller + กล้อง), gateway |
| คอม | Next.js :3000; โหมด AI: vision worker; หน้า `/ocr-test`: AI test service :5100 (D026 — PaddleOCR ใช้บน Pi ไม่ได้) |
| ESP32 | firmware `hub_node` (upload จากคอม) |

## 1. เปิดไฟตามลำดับ

1. เปิด Pi รอบูตประมาณ 1 นาที
2. เสียบ USB ESP32
3. เปิด Adapter 5V **หลัง** ESP32 มีไฟ
4. เปิด hotspot (iPhone: Maximize Compatibility) ให้ Pi, ESP32 และคอมอยู่ Wi-Fi เดียวกัน

## 2. เช็คบริการบน Pi

จากคอม (PowerShell):

```powershell
ssh nanont@pi-673305942.local
```

บน Pi:

```bash
systemctl is-active mosquitto
sudo docker ps | grep mini-sort-influx
hostname -I
```

- Mosquitto ต้อง `active`; Influx ต้อง `Up` — ถ้าไม่ขึ้น: `sudo docker start mini-sort-influx`
- ดู IP Pi ตัว `172.20.10.x` (ไม่ใช่ `172.17.0.1` ของ Docker) ถ้าเลขเปลี่ยนจากรอบก่อน ให้แก้ `MQTT_HOST` ใน `secrets.h` แล้ว upload firmware ใหม่, แก้ `BACKEND_URL` ใน `frontend/.env.local` และใช้ IP ใหม่ใน `--backend` ของข้อ 6

## 3. ถ้าแก้ source บนคอม — ส่งขึ้น Pi ก่อน (PowerShell ที่ราก Project)

ส่งเฉพาะส่วนที่แก้ ใช้ path ปลายทางตามนี้ (อย่าส่ง `backend/app` ไปที่ `~/mini-sorting-hub/` ตรง ๆ จะได้โฟลเดอร์ `app` ผิดที่):

```powershell
scp -r backend/app nanont@pi-673305942.local:~/mini-sorting-hub/backend/
```

```powershell
scp -r gateway nanont@pi-673305942.local:~/mini-sorting-hub/
```

ไม่ต้องส่ง `ai/` ขึ้น Pi แล้ว (D026) แก้ firmware ต้อง upload ผ่าน Arduino IDE แยก

## 4. Backend — Pi SSH หน้าต่างที่ 1

```bash
cd ~/mini-sorting-hub && .venv/bin/python -m backend.app
```

## 5. Gateway — Pi SSH หน้าต่างที่ 2

```bash
cd ~/mini-sorting-hub && .venv/bin/python gateway/gateway_sensors.py
```

## 6. คอม — PowerShell (เปิดค้างไว้ทุกหน้าต่าง)

Frontend:

```powershell
Set-Location C:/Users/nanon/Desktop/CU/IoT/Project/frontend
npm run dev
```

AI test service สำหรับหน้า `/ocr-test` (PowerShell ใหม่ ที่ราก Project):

```powershell
.venv\Scripts\python.exe ai\run_test_server.py --backend http://<IP Pi>:5000
```

Vision worker เฉพาะโหมด AI (PowerShell ใหม่ ที่ราก Project):

```powershell
.venv\Scripts\python.exe ai\run_worker.py --backend http://<IP Pi>:5000
```

- ต้องมี `ai/.env` (Gemini key/model) บนคอม; `<IP Pi>` ใช้ค่าเดียวกับ `BACKEND_URL` ไม่ใส่ `< >`
- เปิด http://localhost:3000 (Dashboard) และ http://localhost:3000/ocr-test (ทดสอบ OCR)
- แก้ `next.config.ts` หรือ `.env.local` แล้วต้อง restart `npm run dev`
- กล่องแรก/ภาพแรกช้าเพราะโหลดโมเดล OCR

## 7. ESP32 — Arduino IDE Serial Monitor 115200 (New Line)

- ควรเห็นข้อความ help แล้ว `WIFI CONNECTED ip=...` และ `MQTT CONNECTED`
- ใช้พอร์ต USB/สายที่ส่งข้อมูลได้ ถ้าขึ้นแค่ `ESP-ROM...` ให้สลับพอร์ต/สาย
- พิมพ์ `S` ดูค่าเซนเซอร์ Node ทั้งหมด; ถ้า backend เปิดทีหลัง ESP32 จะต่อ MQTT ใหม่เอง หรือกด RST

## 8. ตรวจบนเว็บ

- สถานะ LIVE, Influx OK, มีข้อมูลจาก Node/Gateway และภาพกล้อง
- ดูข้อมูลดิบบน Pi: `mosquitto_sub -h 127.0.0.1 -u hub -P '<รหัส>' -t 'sorter/#' -v`

## 9. เลือกโหมด

- **BENCH:** กดเริ่ม → วางกล่อง → เลือก A/B/HOLD บนเว็บ
- **AI:** worker (ข้อ 6) ต้องรันอยู่ → พักเครื่อง → ตั้งค่า → "เปลี่ยนเป็น AI" (ต้องไม่มี job) → กดเริ่ม → วางกล่องติดฉลากข้อมูลสมมติ ภาพและผล AI แสดงในงานปัจจุบัน

## ทางเลือก: เปิดหน้า InfluxDB บนคอม

ใช้เมื่ออยากดูข้อมูลใน Influx UI (บัญชี/org/bucket/token สร้างไว้แล้ว ไม่ต้องสร้างใหม่) PowerShell ใหม่ เปิดค้างไว้:

```powershell
ssh -L 8086:127.0.0.1:8086 nanont@pi-673305942.local
```

แล้วเปิด http://localhost:8086 ถ้าพอร์ต 8086 บนคอมถูกใช้ ให้ใช้ `-L 18086:127.0.0.1:8086` แล้วเปิด http://localhost:18086

## ข้อควรรู้

- `BENCH_SKIP_SENSOR_CHECKS=1` ยังเปิดใน `backend/.env` บน Pi — ผลระหว่างนี้ไม่ใช่หลักฐาน ปิดเมื่อ E18/SRF05/HX711/AS5600 ผ่าน: `sed -i '/^BENCH_SKIP_SENSOR_CHECKS=/d' backend/.env` แล้ว restart backend
- ปิด Adapter แล้ว IR ถาดจะอ่านเป็น "มีกล่อง" หลอก — เปิด Adapter ไว้ระหว่างใช้งาน
- ระหว่างโหมด AI คอมต้องเปิด worker ไว้ ถ้าไม่ตอบเกิน 60 วินาที งานจะเข้า PAUSED_AI รอกด "ลอง AI ใหม่"
- ปิดระบบ: ปิด Adapter ก่อน → ถอด USB ESP32 → Ctrl+C ที่ worker / AI test service / frontend / gateway / backend
- ห้ามรัน backend หลายชุดพร้อมกัน และห้ามรันโปรแกรมอื่นที่ใช้กล้องพร้อม backend
