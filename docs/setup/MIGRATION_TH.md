# ย้ายจาก bench_hub เป็น monorepo

อัปเดต 16 พ.ย. 2026 ตามคำขอให้จัด frontend/backend/firmware และเปลี่ยนหน้าเว็บเป็น Next.js

## ตำแหน่งใหม่

| เดิม | ใหม่ |
|---|---|
| bench_hub/hub.py, controller.py, store.py | backend/app/ |
| bench_hub/tests/ | backend/tests/ |
| bench_hub/templates/index.html | frontend/src/features/dashboard/ และ src/app/ |
| bench_hub/gateway_sensors.py | gateway/gateway_sensors.py |
| bench_hub/firmware/hub_node/ | firmware/esp32/hub_node/ |
| firmware/bench/, gateway/bench/ | คงตำแหน่งเดิม |
| คู่มือและเอกสารที่ราก | docs/project/, docs/setup/, docs/ai/, docs/testing/ |
| wiring_diagrams_v2/ | docs/hardware/wiring_v2/ |
| rubric PDF | docs/references/ |
| ZIP v1/v2 | artifacts/legacy/ — ไม่รวมใน Git |
| ภาพวงจร v1, tmp, ไฟล์ bench_hub ที่เหลือ | archive/ — ไม่รวมใน Git |

ถาด Servo GPIO sensor protocol และกฎการคัดไม่ได้เปลี่ยนจากการจัดโครงนี้ เปลี่ยนเฉพาะ package imports, ตำแหน่งไฟล์ และ Next.js ที่เสิร์ฟหน้าเว็บ

## บนคอมกับบน Pi เป็นคนละชุดไฟล์

การย้ายครั้งนี้ทำใน workspace บนคอม **ไม่ได้ย้ายไฟล์หรืออัปโหลด firmware ในอุปกรณ์ผู้ใช้** และ ZIP เดิมไม่ได้อัปเดตตาม source ใหม่

บน Pi ต้องหยุด hub/gateway เก่าด้วย Ctrl+C และปิด Adapter Servo ก่อนส่ง source ใหม่ อย่าเปิด controller สองชุดพร้อมกัน ไม่ลบข้อมูล/ค่าจริงเดิม

## ย้ายค่าจาก Pi เดิมเมื่อมีอยู่

จาก ~/mini-sorting-hub หลังวาง source ใหม่แล้ว ตัวอย่างด้านล่างคัดลอกเฉพาะเมื่อปลายทางยังไม่มี ไม่เขียนทับค่าที่ตั้งแล้ว:

```bash
if [ -f bench_hub/.env ] && [ ! -e backend/.env ]; then
  cp bench_hub/.env backend/.env
  chmod 600 backend/.env
fi
if [ -f bench_hub/config.json ] && [ ! -e backend/config.json ]; then
  cp bench_hub/config.json backend/config.json
fi
if [ -d bench_hub/data ] && [ ! -e backend/data ]; then
  cp -a bench_hub/data backend/data
fi
cp -n gateway/.env.example gateway/.env
chmod 600 gateway/.env
```

แก้ gateway/.env ให้ MQTT_HOST/USER/PASSWORD ตรงกับ backend และ broker โดยไม่ต้องคัดลอก Influx token มาด้วย ส่วน firmware หากมี secrets.h เดิม ให้ย้ายเฉพาะในเครื่องไปอยู่ข้าง .ino ใหม่ ห้าม commit

ถ้าชุดเดิมใช้โฟลเดอร์ ~/mini-sorting-hub/bench จากการทดสอบแยกชิ้น ให้เก็บไว้ได้ ไม่ใช้ .venv หรือ path เดิมแทน environment ของ repo ใหม่

## ติดตั้งและรันใหม่

สร้าง .venv ที่ราก repo และติดตั้ง requirements ของ backend/gateway ตาม [คู่มือ BENCH](BENCH_SETUP_TH.md) ไม่คัดลอก Windows .venv หรือ node_modules ไป Pi

คำสั่ง entry point ใหม่จากราก repo:

```bash
.venv/bin/python -m backend.app
```

```bash
.venv/bin/python gateway/gateway_sensors.py
```

Next.js อยู่ frontend และ **รันบนคอมเท่านั้นตามที่เลือก** ไม่ต้องย้าย frontend หรือติดตั้ง Node.js/npm บน Pi อ่าน frontend/README.md ในชุด source บนคอม หน้าเว็บ http://localhost:3000 ส่ง API ไป Pi :5000 ตาม BACKEND_URL ส่วน `/` ของ Flask คืน JSON

การย้ายโครง source อย่างเดียวไม่จำเป็นต้องล้าง NVS หรือสอบเทียบใหม่ หากมีการเปลี่ยนฐาน/ถาด/ตำแหน่งเซนเซอร์จึงสอบเทียบตามคู่มือ และหากโค้ด firmware เปลี่ยนพฤติกรรมต้อง compile/upload ใหม่
