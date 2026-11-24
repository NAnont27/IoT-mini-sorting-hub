# Startup — เปิดระบบ BENCH ใหม่ (รอบถัดไป)

ใช้เมื่อเคยติดตั้งครบแล้ว (คู่มือ BENCH ขั้น 8–13) ถ้าไม่ได้แก้โค้ด/config **ไม่ต้อง** `apt`, `pip`, `npm ci` หรือ upload firmware ใหม่

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
- ดู IP Pi ตัว `172.20.10.x` (ไม่ใช่ `172.17.0.1` ของ Docker) ถ้าเลขเปลี่ยนจากรอบก่อน ให้แก้ `MQTT_HOST` ใน `secrets.h` แล้ว upload firmware ใหม่ และแก้ `BACKEND_URL` ใน `frontend/.env.local`

## 3. Backend — Pi SSH หน้าต่างที่ 1

```bash
cd ~/mini-sorting-hub && .venv/bin/python -m backend.app
```

## 4. Gateway — Pi SSH หน้าต่างที่ 2

```bash
cd ~/mini-sorting-hub && .venv/bin/python gateway/gateway_sensors.py
```

## 5. Frontend — PowerShell บนคอม

```powershell
Set-Location C:/Users/nanon/Desktop/CU/IoT/Project/frontend
npm run dev
```

เปิด http://localhost:3000

## 6. ESP32 — Arduino IDE Serial Monitor 115200

- ควรเห็น `WIFI CONNECTED ip=...` แล้ว `MQTT CONNECTED`
- ถ้า backend เปิดทีหลัง ESP32 จะต่อ MQTT ใหม่เอง หรือกด RST

## 7. ตรวจบนเว็บ

- สถานะ LIVE, Influx OK, มีข้อมูลจาก Node/Gateway
- ดูข้อมูลดิบบน Pi: `mosquitto_sub -h 127.0.0.1 -u hub -P '<รหัส>' -t 'sorter/#' -v`

## ข้อควรรู้

- `BENCH_SKIP_SENSOR_CHECKS=1` ยังเปิดใน `backend/.env` บน Pi — ผลระหว่างนี้ไม่ใช่หลักฐาน ปิดเมื่อ E18/SRF05/HX711/AS5600 ผ่าน: `sed -i '/^BENCH_SKIP_SENSOR_CHECKS=/d' backend/.env` แล้ว restart backend
- แก้ไฟล์ backend บนคอม → `scp` ขึ้น Pi ก่อนรันข้อ 3
- ปิดระบบ: ปิด Adapter ก่อน → ถอด USB ESP32 → Ctrl+C ที่ backend / gateway / frontend
- ห้ามรัน backend หลายชุดพร้อมกัน
