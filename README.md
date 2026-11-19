# Mini Sorting Hub

โปรเจกต์ IoT Systems and Digital Solutions สำหรับคัดพัสดุขาเข้าหอพัก ทีม 6 คน แบ่ง AI 3 คน และ HW/System 3 คน

**สถานะ: BENCH v2** — เลือก A/B/HOLD บนเว็บและย้ายกล่องผ่าน IR ด้วยมือก่อนรวม AI/ประกอบโครง กลไกและเซนเซอร์ยังต้องยืนยันบนอุปกรณ์จริง

## โครงสร้าง

```text
Project/
├── frontend/          # Next.js App Router + TypeScript + Tailwind
│   └── src/           # app, features/dashboard, lib/api, types
├── backend/           # Flask API, controller, SQLite/InfluxDB
│   ├── app/
│   └── tests/
├── gateway/           # Pi อ่าน BH1750/AS5600 + standalone tests
├── firmware/          # ESP32-S3: โปรแกรมรวมและทดสอบแยกชิ้น
│   ├── esp32/hub_node/
│   └── bench/
├── docs/              # project, setup, ai, hardware, testing, references
├── archive/           # ของเดิมเก็บไว้ในเครื่อง ไม่เข้า Git
├── artifacts/         # ZIP เก่า/ไฟล์ส่งมอบ ไม่เข้า Git
├── AGENTS.md          # บริบท สถานะ การตัดสินใจ และบันทึกงาน
├── .gitignore
└── .gitattributes
```

## เริ่มอ่าน

- [ขอบเขตและ Criteria](docs/project/PROJECT_BRIEF_TH.md)
- [คู่มือต่อสายและติดตั้งบน Pi](docs/setup/BENCH_SETUP_TH.md)
- [ย้ายจากโครง bench_hub เดิม](docs/setup/MIGRATION_TH.md)
- [ผังวงจรปัจจุบัน](docs/hardware/wiring_v2/README_TH.md)
- [จุดเชื่อมทีม AI](docs/ai/AI_INTERFACE_TH.md)
- [ผลตรวจและข้อจำกัด](docs/testing/VALIDATION_TH.md)
- [ตรวจครบทุกข้อของ Metric และ MQTT](docs/testing/METRIC_AUDIT_TH.md)
- [คู่มือ Git สำหรับทีม](docs/setup/GIT_TH.md)

## รันตามแบบที่เลือก — คอม + Pi

| เครื่อง | ส่วนที่รัน |
|---|---|
| คอม Windows | frontend: Next.js / Node.js / npm |
| Raspberry Pi | backend, gateway, Mosquitto, InfluxDB และ SQLite |
| ESP32 | firmware ที่ Upload จากคอม |

Pi รับ source backend/ และ gateway/ ใต้ ~/mini-sorting-hub/; ไม่ต้องส่ง frontend/node_modules/.next ไป Pi อ่าน [คู่มือ Pi](docs/setup/BENCH_SETUP_TH.md)

บน Pi เปิด SSH สอง terminal จากราก repo:

```bash
cd ~/mini-sorting-hub
.venv/bin/python -m backend.app
```

```bash
cd ~/mini-sorting-hub
.venv/bin/python gateway/gateway_sensors.py
```

บนคอม เปิด PowerShell:

```powershell
Set-Location C:/Users/nanon/Desktop/CU/IoT/Project/frontend
npm ci
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm run dev
```

ตั้ง frontend/.env.local ให้ BACKEND_URL=http://pi-673305942.local:5000 หาก .local ไม่ resolve ให้ใช้ IP LAN จริงของ Pi แล้ว restart dev; production ต้อง build ใหม่เมื่อเปลี่ยน target

เปิด http://localhost:3000 บนคอม Browser ส่ง /api ผ่าน Next.js proxy ไป Flask บน Pi :5000; Pi ไม่ต้องมี Node.js หรือ Next.js ทั้งสองเครื่องต้องอยู่เครือข่ายที่ติดต่อกันได้

## ตรวจงาน

สำหรับผู้พัฒนาที่จะรัน Python tests บนคอม ให้สร้าง .venv และติดตั้ง backend/requirements.txt ก่อน (ไม่ต้องเปิด backend บนคอม):

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

ใน frontend:

```powershell
npm run lint
npm run typecheck
npm run build
```

บน Pi ใช้ `.venv/bin/python` แทน `.venv\Scripts\python.exe` และดูคำสั่งติดตั้ง Mosquitto/Influx ในคู่มือ ไม่สั่ง Servo หรือ GPIO จากหน้า Next.js โดยตรง

## Git

เตรียม repository ในเครื่อง branch `main` ตามที่ผู้ใช้เลือก ยังไม่ผูก remote หรือ push ขึ้น GitHub ใช้ [คู่มือ Git](docs/setup/GIT_TH.md) เมื่อต้องการสร้าง commit แรก

`.env`, `config.json`, `secrets.h`, ข้อมูลจริง, virtual environments, node_modules, build output และ ZIP ไม่เข้า Git ส่วนไฟล์ example, source และ `frontend/package-lock.json` ต้องเก็บใน Git
