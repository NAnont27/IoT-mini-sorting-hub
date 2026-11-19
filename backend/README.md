# Backend — Flask / MQTT / State Machine

- `app/hub.py`: HTTP API และ MQTT client
- `app/controller.py`: เจ้าของ state/interlock และการเลือกคิวคำสั่ง
- `app/store.py`: SQLite jobs/events และ InfluxDB v2 telemetry
- `app/__main__.py`: entry point
- `tests/`: state machine, วงจร R ที่คำนวณ และ API tests แบบ mock

จากราก repo ใช้ Python environment `.venv` ตาม README หลัก คัดลอก `.env.example` เป็น `backend/.env` และ `config.example.json` เป็น `backend/config.json` เมื่อยังไม่มีค่าเดิม

```bash
.venv/bin/python -m backend.app
```

บน Windows ใช้ `.venv\Scripts\python.exe -m backend.app`

API อยู่พอร์ต 5000; `/` คืนข้อมูล service ส่วนหน้า dashboard อยู่ Next.js พอร์ต 3000 ไม่มี Flask template แล้ว

`config.json` และ `data/hub.sqlite3` อิงโฟลเดอร์ backend เสมอ ไม่ขึ้นกับ directory ที่รัน ใช้คำสั่ง module ตามด้านบน ไม่รัน app/hub.py แบบไฟล์เดี่ยว เพราะใช้ package imports

ต้องมี MQTT_USER/PASSWORD ที่ถูกต้องและ broker ที่เข้าถึงได้ ระบบยังพักและไม่ผ่าน readiness จนกว่าจะมีข้อมูลเซนเซอร์จริง ไม่เริ่มกลไกเองจากการเปิดหน้าเว็บ

รันเพียงหนึ่ง instance ไม่ใช้ Flask reloader หรือหลาย worker คำตอบ API ไม่ใช่หลักฐานว่ากล่องผ่าน IR แล้ว

ดู [คู่มือ BENCH](../docs/setup/BENCH_SETUP_TH.md) และ [AI API](../docs/ai/AI_INTERFACE_TH.md)
