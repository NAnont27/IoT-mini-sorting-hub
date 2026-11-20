# Mini Sorting Hub — คู่มือ BENCH v2 ฉบับอัปเดต

อัปเดต 20 พฤศจิกายน 2026 | โครง monorepo | Next.js บนคอม + Backend/Gateway บน Pi | **D011: E18 ตัวเดียวที่ถาด**

**ผังปัจจุบัน v2: ไม่ใช้ PC817** ใช้ **E18 ตัวเดียวที่ถาด (GPIO11)** ผ่านวงจร R 1kΩ/10kΩ/15kΩ และตั้งขารับ IR เป็น INPUT ส่วนปุ่ม GPIO10 ยังคง INPUT_PULLUP ภาพปัจจุบันอยู่ที่ `docs/hardware/wiring_v2/`

ผู้ใช้เลือก **BENCH: เลือก A/B/HOLD บนเว็บก่อน** แล้วค่อยเชื่อม AI ภายหลัง โค้ดในชุดนี้เป็น HW/System จริง: MQTT, Pi sensors, firmware, state machine, SQLite, InfluxDB adapter และ Dashboard ไม่ได้แอบแทน OCR/Gemini ด้วยข้อมูลจำลอง

เอกสารหลักของโปรเจกต์ยังเป็น `docs/project/PROJECT_BRIEF_TH.md` ชุดนี้เพิ่ม implementation สำหรับการทดสอบบนโต๊ะ ไม่เปลี่ยนขอบเขตรุ่นส่งงาน

## อ่านก่อนเริ่ม — ฉบับนี้ใช้กับโครงใหม่

คู่มือนี้อัปเดตจาก README_TH.md ใน ZIP BENCH v2 เดิม โดยคงขั้นตอนต่อสาย/สอบเทียบ/ทดสอบ และเปลี่ยน path กับคำสั่งให้ตรง source ปัจจุบัน ไม่ใช่คู่มือสำหรับแตก ZIP v2 เก่าแล้วรันตาม path ใหม่ทันที

| เครื่อง | ส่วนที่ทำงาน | พอร์ต/จุดเปิด |
|---|---|---|
| คอม Windows | frontend: Next.js และ npm; Arduino IDE ใช้ Upload firmware | หน้าเว็บ http://localhost:3000 |
| Raspberry Pi | backend + gateway + Mosquitto + InfluxDB/SQLite | Flask API :5000, MQTT :1883, Influx localhost:8086 |
| ESP32-S3-N16R8 | firmware รวม, อ่าน Node sensors และคุม Servo/LED/ปุ่ม | รับคำสั่งผ่าน MQTT |

**Pi รับ source แค่ backend/ และ gateway/** ไม่ต้องมี frontend, Node.js, node_modules หรือ .next ส่วนบนคอม npm ci สร้าง node_modules และ npm run build สร้าง .next เอง

พาธ source ใน backticks ให้นับจากราก Project; คำสั่งแต่ละช่วงระบุว่ารันใน PowerShell บนคอมหรือ SSH บน Pi ใช้ `nanont@pi-673305942.local` ตาม terminal ที่ผู้ใช้เคยยืนยัน หาก .local ไม่ resolve ให้แทนด้วย IP LAN จริงของ Pi ทุกตำแหน่งที่เกี่ยวข้อง

```text
คอม: Project/                    Pi: ~/mini-sorting-hub/
├── frontend/                    ├── backend/
├── firmware/                    ├── gateway/
├── backend/   -- ส่ง source --> └── .venv/  (สร้างใหม่บน Pi)
├── gateway/   -- ส่ง source -->
└── docs/
```

ก่อนเริ่มระบบใหม่ ให้หยุด controller/gateway เก่าและปิดกำลัง Servo ระหว่างแก้สาย/ส่ง source เก็บ .env, config.json และข้อมูลจริงเดิมไว้ตาม [Migration](MIGRATION_TH.md) ไม่มีคำสั่งในเอกสารนี้ถูกนำไปรันบน Pi ให้อัตโนมัติ

## 1. ทำอะไรได้ และอะไรยังไม่ใช่ผลทดสอบจริง

- อ่านเซนเซอร์จริง 5 ชนิด: ESP32 อ่านน้ำหนัก/ระยะ/IR; Pi อ่านมุม/แสงโดยตรง
- สั่ง MG996R และ MG90S คนละขา มีปุ่มพักและไฟสถานะ
- วางกล่องบนชุดชั่ง เมื่อค่านิ่งและระบบพร้อมจะสร้าง job แล้วรอเลือกช่องบนเว็บ
- สั่ง Servo ราง → รอ AS5600 ยืนยันมุม → สั่ง Servo ประตู
- **E18 ที่ถาดตรวจตอนวางกล่อง** (D011) หลังเปิดประตู คนยกกล่องออกจากถาดแทนรางจริง ระบบนับสำเร็จเมื่อ IR ถาดว่างและน้ำหนักกลับต่ำกว่า min_weight_g
- **ไม่มี IR ที่ช่อง A/B/HOLD** ระบบจึงตรวจกล่องผิดช่องหรือติดในรางไม่ได้ job บันทึก `destination_sensed=false`
- บันทึกผลเป็น BENCH / passage_simulated=true ไม่ถือเป็นผลทดสอบคัดกล่องทางกลจริง
- ถ้าแม่เหล็กยังไม่ยึดกับแกนราง ให้หมุนแม่เหล็กด้วยมือไปตำแหน่งที่จำไว้ การผ่านมุมในโหมดนี้เป็นการจำลอง feedback ทางกล ต้องบันทึกตามจริง
- ToF/AS5600 ที่ไม่มีค่าถูกต้องและสดจะทำให้ readiness ไม่ผ่าน แม้บัดกรีแล้วก็ต้องตรวจการอ่านจริง ห้ามกรอกค่าปลอมเพื่อข้าม
- ยังไม่ได้รันกับฮาร์ดแวร์ของผู้ใช้หรือ compiler Arduino ในเครื่องนี้ ต้องทำ commissioning ตามลำดับด้านล่าง

## 2. โฟลว์ครบหนึ่งรอบ

```text
เริ่มโปรแกรม → PAUSED_OPERATOR
  ↓ ตรวจ Node/Pi sensors online + สอบเทียบ + ตั้งขีดจำกัด + จำมุม A/B/HOLD
กดเริ่มบนเว็บ → IDLE (พร้อม)
  ↓ วางกล่องทีละชิ้น: IR ถาดเห็นกล่อง + น้ำหนัก ≥ min_weight_g และนิ่ง
สร้าง job_id → WAIT_DECISION
  ↓ เลือก A/B/HOLD บนเว็บสำหรับ job นี้เท่านั้น
POSITION → ESP32 สั่ง Servo ราง → ACK คำสั่ง
  ↓ Pi อ่าน AS5600: มุมถูกช่วงและนิ่งตาม dwell
RELEASE → ESP32 เปิด Servo ประตู
VERIFY_EXIT
  ↓ ยกกล่องออกจากถาด: IR ถาดว่าง + น้ำหนัก < min_weight_g
WAIT_CLEAR → COMPLETE command → ปิด Servo ประตู → ACK
บันทึก SORTED_A / SORTED_B / HOLD_DELIVERED แบบ BENCH → IDLE
```

เงื่อนไขผิดพลาด:

- มุมไม่ถึง/มุมเก่า/แม่เหล็กใช้ไม่ได้ → ไม่เปิดประตู
- กล่องหายจาก IR ถาดก่อนเปิดประตู → FAULT `PARCEL_MISSING_BEFORE_RELEASE`
- ยกกล่องออกไม่ทันภายในเวลา → FAULT `PASSAGE_OR_CLEAR_TIMEOUT`
- ไม่มีการตรวจผิดช่อง (D011) — ต้องระบุเป็นข้อจำกัดในรายงาน
- MQTT/Node/Pi sensor ขาดหายระหว่าง job → FAULT; ไม่เดาว่าสำเร็จ
- หลัง fault คนเอากล่องออก ตรวจถาดและ IR ถาดว่าง แล้วกดเคลียร์ ระบบปิดประตูและกลับพักก่อน
- พักก่อนปล่อย → คงงานไว้ ไม่ปล่อย; พักหลังปล่อย → คงเส้นทางเดิมจนจบ/ผิดพลาด แล้วพักรับชิ้นถัดไป
- ปุ่มพักไม่ใช่ Emergency Stop; การตัดกำลังจริงคือถอดแหล่งจ่าย Servo

## 3. เตรียมจุดจ่ายไฟ — สำคัญก่อนรวมสาย

**ถอดไฟ Pi, USB ESP32 และ Adapter Servo ทุกครั้งก่อนเปลี่ยนสาย** ใช้ขั้วต่อ/ฉนวน ไม่ปล่อยปลายทองแดงแตะกัน

```text
แหล่งจ่าย Pi ที่เหมาะสม → USB-C Pi
USB คอม/แหล่งจ่าย USB → ESP32
Adapter DC 5V 5A → รางจ่ายกำลัง Servo + E18

Adapter ขั้วลบ ─── ESP32 GND
Pi GND ─────────── ESP32 GND

ห้ามผูก +5V ของ Adapter เข้ากับ +5V ของ Pi หรือ ESP32 ที่มี USB เลี้ยงอยู่
```

- รอบรวมสอง Servo ใช้ Adapter 5V 5A แยก ไม่ดึงกำลังมอเตอร์จาก 3V3/5V ของ ESP32 หรือ Pi
- Adapter P0384 หัว 5.5×2.5 มม. ใช้แจ็กตัวเมีย/สายตัวเมียสำเร็จรูปที่พิกัดกระแสเหมาะสม
- เดินไฟมอเตอร์ผ่านสายและขั้วแยกกำลังที่เหมาะสม ไม่ผ่านเบรดบอร์ดเส้นเล็ก จุดกระจาย GND ควรกลับแหล่งจ่าย ไม่ให้กระแสมอเตอร์วิ่งผ่านสาย GND เซนเซอร์
- วัด +5V/ขั้วให้ถูกก่อนเสียบอุปกรณ์ ถ้ามี capacitor 470–1000 µF ≥10V ใช้คร่อมราง Servo ใกล้จุดจ่ายได้ โดยต่อขั้วให้ถูก แต่ไม่ใช้แทนแหล่งจ่าย/สายที่เหมาะสม
- เซนเซอร์ low-current และวงจรสัญญาณใช้เบรดบอร์ดได้ จุดบัดกรีต้องแน่น

## 4. Pin map ESP32-S3 — ใช้เลข GPIO ที่พิมพ์บนบอร์ด

| หน้าที่ | GPIO | รายละเอียด |
|---|---:|---|
| HX711 DT/DOUT | 4 | HX711 VCC=3V3, GND ร่วม |
| HX711 SCK | 5 | ใช้ขา A+/A− ของ HX711 รับ Load cell |
| Servo ประตู MG90S | 6 | สายส้ม; แดง=Adapter +5V, น้ำตาล=GND |
| Servo ราง MG996R | 7 | สายส้ม; แดง=Adapter +5V, น้ำตาล=GND |
| ToF SDA | 8 | GY-530 V2 VCC=3V3, GND ร่วม |
| ToF SCL | 9 | XSHUT/INT ยังไม่ต่อ |
| ปุ่มพัก/เริ่มต่อ | 10 | ปุ่ม NO ระหว่าง GPIO10 กับ GND; INPUT_PULLUP |
| IR ถาด (`tray`) | 11 | E18 ตัวเดียว ผ่านวงจร R แบ่งแรงดันด้านล่าง; INPUT |
| ว่าง | 12 / 13 / 14 | ไม่ใช้แล้วตาม D011 ถอดสายเดิมออก |
| ไฟเขียว | 15 | GPIO → R 330Ω → LED anode, cathode → GND |
| ไฟเหลือง | 16 | ต่อ R/LED แบบเดียวกัน |
| ไฟแดง | 17 | ต่อ R/LED แบบเดียวกัน |

**ถอดสายพ่วง GPIO6–GPIO7 ที่เคยใช้ตรวจพัลส์ออก** ตอนนี้ทั้งสองขาเป็น output ของ Servo คนละตัว ห้ามเชื่อมเข้าด้วยกัน

ไฟสถานะในโค้ด: เขียว=IDLE พร้อม, เหลืองติด=กำลังทำงาน, เหลืองกระพริบ=พัก/blocked/offline, แดง=fault/AI ขัดข้อง

Load cell สี่สายตามรุ่นที่เคยทดสอบ: แดง E+, ดำ E−, เขียว A+, ขาว A− ตรวจเอกสารของตัวจริงหากสีไม่ตรง แผ่นรับของต้องรับแรงผ่านปลาย Load cell ที่ยึดถูกวิธี ไม่วางทั้งแท่งแนบโต๊ะแล้วสอบเทียบ

GPIO35/36/37 ไม่ใช้ เพราะโมดูล S3 แบบ Octal memory บางรุ่นสงวนขาเหล่านี้สำหรับหน่วยความจำ GPIO19/20 เว้นไว้ให้ USB

## 5. E18-D80NK ตัวเดียวที่ถาด — ทำสัญญาณให้เหมาะกับ 3.3V ก่อน

สีตามฉลากของผู้ใช้: **น้ำตาล=+5V, น้ำเงิน=GND, ดำ=OUT (NPN NO)** การอ่าน 0/1 ได้ครั้งหนึ่งยังไม่พิสูจน์ว่าแรงดันปลอดภัย ต้องไม่ปล่อย output 5V เข้า GPIO

**ใช้วงจรตัวต้านทานต่อไปนี้เป็น baseline v2 แทน PC817** สำหรับเซนเซอร์ NPN NO 5V ตามฉลากของผู้ใช้ ใช้ 1 ชุดสำหรับ E18 ที่ถาด:

```text
Adapter +5V ───────────── น้ำตาล E18
Adapter GND ──────────── น้ำเงิน E18 และ ESP32 GND

Adapter +5V ── R1 1kΩ ──● A ── R2 10kΩ ──● B ── GPIO11
                        │                  │
                   ดำ OUT E18          R3 15kΩ
                                           │
                                          GND
```

จุด A คือสายดำเซนเซอร์ **ไม่ใช่ขา GPIO** จุด B หลัง R2 คือจุดรับเข้า ESP32 โดยมี R3 ลง GND ห้ามสลับจุดนี้ และห้ามใส่แค่ R อนุกรมตัวเดียวแทนวงจรแบ่งแรงดัน

- R1 ทำ pull-up ให้ NPN open-collector; R2/R3 แบ่งระดับแรงดันลง ขณะ HIGH คำนวณได้ประมาณ 2.885V เมื่อ OUT ลอย หรือประมาณ 3.0V เมื่อ OUT ถูกดึงเป็น 5V โดยวงจรภายใน
- เมื่อพบวัตถุ OUT ลง LOW จุด B ควรลงใกล้ 0V ค่า LOW = DETECTED เหมือนเดิม
- ใช้ไฟ 5V แบบ regulated ตามแผน ไม่ใช้วงจรนี้กับเซนเซอร์ 12/24V
- ตัวต้านทาน 1/4W ใช้ได้ เลือก tolerance 1% หากมี; ต้องวัดจุด B ก่อนต่อ GPIO ให้ HIGH เหมาะสมราว 2.8–3.1V และ LOW ต่ำกว่า 0.8V แรงดันต้องไม่เกิน 3.3V ในช่วงทดสอบ
- ใช้ชุดเดียวที่ GPIO11 ไม่ต่อสายดำ/จุด A/จุด B เข้าขาอื่น ร่วมกันได้เฉพาะราง +5V และ GND
- ใน firmware ตั้ง GPIO11 เป็น INPUT (ไม่เปิด internal pull-up); ปุ่มพัก GPIO10 ยังคง INPUT_PULLUP
- เปิดไฟ ESP32 ก่อน Adapter เซนเซอร์/Servo และปิด Adapter ก่อนถอด USB ESP32 ไม่ปล่อยเอาต์พุตเซนเซอร์มีไฟเข้าขาของ ESP32 ที่ปิดอยู่

| R สำหรับวงจรปัจจุบัน | จำนวน |
|---|---:|
| 1kΩ | 1 |
| 10kΩ | 1 |
| 15kΩ | 1 |
| 330Ω สำหรับ LED สถานะ | 3 |
| รวม | 6 ตัว |

ทดสอบ E18 ตัวเดียวก่อนรวม flow ด้วย `../firmware/bench/07_e18_detection/07_e18_detection.ino` (07c สำหรับสี่ตัวเป็นของเดิม ไม่ใช้แล้ว)

ก่อนรวม flow ให้ดูหน้าเว็บช่อง **IR ถาด**: ถาดว่างต้องเป็น "ว่าง" (`tray=false`) และวางกล่องต้องเป็น "มีกล่อง" (`tray=true`) ถ้าถอด Adapter ค่าจะเป็น true หลอกเพราะ R3 ดึงลง GND จึงต้องเปิด Adapter ไว้ตลอด

## 6. Pi: BH1750 + AS5600 ต่อร่วมบัส I2C

เลขฝั่ง Pi คือ **ตำแหน่งขาจริงของหัว 40 ขา** ไม่ใช่ GPIO number

| Raspberry Pi | BH1750 | AS5600 |
|---|---|---|
| pin1: 3.3V | VCC | VCC ของโมดูลที่รองรับ 3.3V |
| pin6: GND | GND และ ADDR | GND |
| pin3: SDA / GPIO2 | SDA | SDA |
| pin5: SCL / GPIO3 | SCL | SCL |

ใช้จุดแยกสาย/เบรดบอร์ดสัญญาณต่อแบบขนาน **ไม่ใช้คนละขา Pi สำหรับแต่ละเซนเซอร์** AS5600 OUT/DIR/PGO ยังไม่ใช้ อย่าส่งไฟหรือ pull-up 5V เข้าบัส Pi

AS5600 ต้องใช้แม่เหล็ก Diametric ตรงศูนย์กลางชิป เริ่ม air gap 1–2 มม. ปรับจน angle_valid=true หมุนอยู่เหนือชิป ไม่เลื่อนแม่เหล็กวนรอบบอร์ด ค่ามุม 359°→0° เป็นการวนปกติ

Camera Module 3 อยู่ในขอบเขตทีม AI ใช้สาย 15→22 pin สำหรับ Pi5 ต่อเฉพาะตอน Pi ถอดไฟ ไม่ต้องใช้กล้องเพื่อผ่าน BENCH ขั้นนี้ และห้ามรายงาน BENCH เป็น camera/OCR/AI ครบ Criteria

## 7. โครงสร้างซอฟต์แวร์และการเชื่อมสองเครื่อง

```text
ESP32 -- Wi-Fi MQTT --> Mosquitto บน Pi
                               ↕
Pi gateway/gateway_sensors.py -- MQTT --> backend/app/hub.py
                                          ├─ controller.py: state/interlock
                                          ├─ SQLite: backend/data/hub.sqlite3
                                          ├─ InfluxDB v2: telemetry
                                          └─ Flask API :5000
                                                ↕ HTTP ผ่าน LAN
คอม: frontend Next.js :3000 -- /api proxy ตาม BACKEND_URL
          ↕
Browser บนคอม: http://localhost:3000
```

หัวข้อ MQTT: sorter/weight, sorter/height, sorter/passage, sorter/gateway, sorter/cmd, sorter/ack, sorter/actuator, sorter/status, sorter/vision

Backend เริ่มจากราก repo ด้วย python -m backend.app ไม่รัน hub.py แบบไฟล์เดี่ยว; Gateway อ่าน gateway/.env ส่วน Backend อ่าน backend/.env; Browser ไม่ต่อ MQTT และไม่มี token ฐานข้อมูลใน client

คำสั่งใช้ command_id, active job, Node boot session และ expiry ตาม uptime ของ Node ไม่ retain คำสั่ง MQTT ACK/DONE ไม่ใช่หลักฐานว่ามุมหรือพัสดุถึงช่อง

ESP32 publish QoS0 ตาม PubSubClient จึงส่ง passage event ring ล่าสุด 16 รายการซ้ำใน snapshot ทุก 0.5s ให้ backend deduplicate ถ้าหายเกิน buffer ไม่เดาว่าสำเร็จ การสื่อสารขาดกลางงานต้อง fault ไม่มี persistent offline event journal บน ESP32 ในรุ่นนี้

## 8. ส่ง source ใหม่เข้า Pi — ไม่ต้องมี commit ก่อน

ใช้ source จากโครงใหม่ใน Project ไม่ใช้ ZIP v2 เก่าซึ่งมี bench_hub รูปแบบเดิม ขั้นนี้ส่งเฉพาะ source/example ไม่ส่ง .env/config.json/data จริงหรือ firmware

ก่อนส่งให้หยุด backend/gateway เดิมบน Pi ด้วย Ctrl+C และปิด Adapter Servo เมื่อจะต่อ/แก้สาย เปิด PowerShell บนคอม:

```powershell
Set-Location C:/Users/nanon/Desktop/CU/IoT/Project
ssh nanont@pi-673305942.local "mkdir -p ~/mini-sorting-hub/backend/app ~/mini-sorting-hub/backend/tests ~/mini-sorting-hub/gateway/bench"
scp backend/__init__.py backend/requirements.txt backend/config.example.json backend/.env.example nanont@pi-673305942.local:~/mini-sorting-hub/backend/
scp backend/app/__init__.py backend/app/__main__.py backend/app/hub.py backend/app/controller.py backend/app/store.py nanont@pi-673305942.local:~/mini-sorting-hub/backend/app/
scp backend/tests/test_api.py backend/tests/test_controller.py backend/tests/test_e18_interface.py nanont@pi-673305942.local:~/mini-sorting-hub/backend/tests/
scp gateway/gateway_sensors.py gateway/requirements.txt gateway/.env.example nanont@pi-673305942.local:~/mini-sorting-hub/gateway/
scp gateway/bench/as5600_test.py gateway/bench/bh1750_test.py nanont@pi-673305942.local:~/mini-sorting-hub/gateway/bench/
ssh nanont@pi-673305942.local
```

เช็กว่า scp แต่ละคำสั่งจบโดยไม่มี error ก่อนทำคำสั่งถัดไป หาก .local ใช้ไม่ได้ให้ใช้ IP จริงแทน ไม่พิมพ์เครื่องหมาย < > ครอบ IP

ตอนนี้เข้า SSH บน Pi แล้ว:

```bash
cd ~/mini-sorting-hub
uname -m
cat /etc/os-release
ls backend/app gateway
```

ควรเห็น source ภายใต้ backend/app กับ gateway ไม่จำเป็นต้องมี frontend บน Pi ระบบ Influx Docker ในคู่มือต้องใช้ OS 64-bit (aarch64); หากเป็น 32-bit ให้ตรวจ environment ไม่แฟลช OS ทับงานเดิมโดยไม่สำรอง

หากย้ายจาก bench_hub เดิม ให้ทำตาม [Migration](MIGRATION_TH.md) เพื่อย้าย config/data และคง MQTT credentials เดิม ขั้น scp นี้ไม่เขียนทับไฟล์ .env, config.json หรือ data และไม่ flash ESP32

ภายหลังเมื่อมี Git commit แล้วจะใช้ git archive ส่ง source snapshot แทน scp รายไฟล์ก็ได้ ตาม [คู่มือ Git](GIT_TH.md) แต่ไม่จำเป็นสำหรับขั้นตอนข้างต้น

## 9. ติดตั้งบริการบน Pi ครั้งแรก

ถ้ามี Mosquitto/Influx เดิมอยู่แล้ว ให้ใช้ของเดิมที่ตั้งถูกแทน อย่าสร้าง listener/container ชนพอร์ตเดิม

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients i2c-tools python3-venv unzip docker.io
sudo raspi-config nonint do_i2c 0
sudo systemctl enable --now mosquitto docker
```

ตั้ง MQTT user `hub` และรหัสผ่านที่ทีมเลือก ไม่ต้องใส่รหัสผ่านใน command line:

```bash
sudo touch /etc/mosquitto/hub.passwd
sudo mosquitto_passwd /etc/mosquitto/hub.passwd hub
sudo chown root:mosquitto /etc/mosquitto/hub.passwd
sudo chmod 640 /etc/mosquitto/hub.passwd
```

เพิ่ม listener สำหรับ LAN ที่ใช้ทดสอบ (กรณี Broker ใหม่ ไม่มี listener 1883 เดิม):

```bash
sudo tee /etc/mosquitto/conf.d/mini-hub.conf > /dev/null <<'CONF'
listener 1883
allow_anonymous false
password_file /etc/mosquitto/hub.passwd
CONF
sudo systemctl restart mosquitto
sudo systemctl status mosquitto --no-pager
```

ถ้า restart ไม่ผ่านให้ดู `sudo journalctl -u mosquitto -n 40 --no-pager` ไม่ปิด authentication เพื่อแก้ปัญหา ชุดนี้ใช้เฉพาะ LAN ของทีม ไม่มี TLS/ระบบผู้ใช้หน้าเว็บ และไม่ให้เปิดพอร์ตออกอินเทอร์เน็ต

รีบูตครั้งเดียวหลังเปิด I2C ถ้าจำเป็น แล้ว SSH กลับมา:

```bash
sudo reboot
```

ตรวจทั้งสอง Gateway sensors หลัง SSH ใหม่:

```bash
sudo i2cdetect -y 1
```

ควรเห็น 23 และ 36 ไม่เห็นตัวใดให้แก้สายนั้นก่อน

## 10. InfluxDB v2 — ต้องเก็บ/ดึงย้อนหลังจริง

ใช้ Docker tag `2.7` ชัดเจน ไม่ใช้ latest เพราะ InfluxDB 3 มี API ต่างกัน หากมี container ชื่อนี้แล้วใช้ `sudo docker start mini-sort-influx` แทนการสร้างซ้ำ

```bash
sudo docker run -d \
  --name mini-sort-influx \
  --restart unless-stopped \
  -p 127.0.0.1:8086:8086 \
  -v mini-sort-influx-data:/var/lib/influxdb2 \
  -v mini-sort-influx-config:/etc/influxdb2 \
  influxdb:2.7
```

เปิด PowerShell อีกหน้าบนคอม ทำ SSH tunnel (ปล่อยหน้าต่างนี้เปิดไว้):

```powershell
ssh -L 8086:127.0.0.1:8086 USERNAME@HOSTNAME.local
```

เปิด browser บนคอม `http://localhost:8086` สร้างบัญชี Influx, Organization=`mini-sort`, Bucket=`bench` แล้วสร้าง API token ที่อ่าน/เขียน bucket นี้ได้ เก็บ token ไว้ใน .env บน Pi ไม่ส่งลงแชตหรือ commit

## 11. ตั้งค่า Python Backend และ Gateway บน Pi

ใช้ virtual environment ที่ราก repo ร่วมกันสำหรับ Python สองส่วน:

```bash
cd ~/mini-sorting-hub
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt -r gateway/requirements.txt
cp -n backend/.env.example backend/.env
cp -n backend/config.example.json backend/config.json
cp -n gateway/.env.example gateway/.env
chmod 600 backend/.env gateway/.env
nano backend/.env
nano gateway/.env
```

MQTT_PASSWORD ของ backend และ gateway ต้องตรงกับ broker; ทั้งสองใช้ MQTT_HOST=127.0.0.1 หากรันบน Pi เดียวกัน ส่วน ESP32 ต้องใช้ LAN IP ของ Pi

backend/.env เก็บ Influx token ด้วย ส่วน gateway/.env ใช้เฉพาะ MQTT credentials ไม่ต้องมี token ของฐานข้อมูล

หากมีค่าจากระบบเดิม ให้อ่าน MIGRATION_TH.md ก่อน ไม่ใช้ config example เขียนทับ calibration/config/data เดิม

ค่า max_weight_g/max_height_mm/target angles ใน example เริ่ม null เพื่อบังคับ commissioning ไม่ใส่ค่าหลอกเพื่อข้าม readiness

INFLUX_ENABLED=0 ใช้ bring-up ชั่วคราวได้ แต่ต้องแสดง DISABLED/fallback และยังไม่ผ่านเกณฑ์ InfluxDB ก่อนเก็บผลจริงต้อง write/query Influx สำเร็จ

## 12. อัปโหลด firmware ESP32-S3

บนคอมเปิด `firmware/esp32/hub_node/hub_node.ino` ใน Arduino IDE แล้วเลือก ESP32S3 Dev Module และพอร์ตของบอร์ด ตั้งค่าตามที่อัปโหลดทดสอบได้แล้ว (N16R8 มี Flash16MB/PSRAM8MB; ถ้าใช้ PSRAM ต้องเลือกชนิดให้ตรงโมดูล)

Library Manager ติดตั้ง:

- HX711 Arduino Library — bogde/Bogdan Necula
- Adafruit VL53L0X และ dependencies
- ESP32Servo — madhephaestus
- PubSubClient — Nick O'Leary
- ArduinoJson **เวอร์ชัน 7** (โค้ดใช้ JsonDocument แบบ v7)

คัดลอก secrets.example.h เป็น secrets.h ในโฟลเดอร์เดียวกับ .ino ใส่ Wi-Fi 2.4GHz, รหัสผ่าน, MQTT_HOST=IPจริงของ Pi, MQTT_USER=hub และ MQTT_PASSWORD ให้ตรง Broker

เริ่มอัปโหลดโดยยังปิดไฟ Adapter Servo แต่ ESP32 ใช้ USB ได้ เมื่อ wiring ยืนยันแล้วจึงเปิด Adapter Servo ตัว Servo จะไปตำแหน่งเริ่มต้นทันที ต้องไม่มีราง/โหลดที่อาจชนหรือหนีบในขั้นนี้

Serial 115200 ควรเห็น HUB NODE BENCH READY และ MQTT CONNECTED อย่าใช้ Wi-Fi หอที่แยก client จน Pi/ESP32 ติดต่อกันไม่ได้ ใช้เครือข่ายทีมที่อนุญาตการเชื่อมต่อกัน

## 13. รัน Backend/Gateway บน Pi และ Frontend บนคอม

ผู้ใช้ยืนยันให้ Next.js รันบนคอม ไม่ติดตั้ง frontend, Node.js, node_modules หรือ .next บน Pi

SSH terminal ที่ 1 บน Pi:

```bash
cd ~/mini-sorting-hub
.venv/bin/python -m backend.app
```

SSH terminal ที่ 2 บน Pi:

```bash
cd ~/mini-sorting-hub
.venv/bin/python gateway/gateway_sensors.py
```

หากไม่มีสิทธิ์ /dev/i2c-1 ให้ตั้งสิทธิ์กลุ่ม i2c ตาม OS หรือใช้ sudo กับ path Python ของ .venv สำหรับทดสอบ ไม่รัน standalone sensor test แข่งกับ gateway

บนคอม Windows ต้องมี Node.js >=20.9 และ npm เปิด PowerShell ที่ frontend:

```powershell
Set-Location C:/Users/nanon/Desktop/CU/IoT/Project/frontend
npm ci
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
notepad .env.local
```

ตั้งค่า BACKEND_URL=http://pi-673305942.local:5000 หาก hostname นี้ไม่ resolve ให้ใช้ IP LAN จริงของ Pi แทน 127.0.0.1/localhost ที่คอมจะหมายถึงคอมเอง

รันโหมดพัฒนาใน PowerShell เดิม:

```powershell
npm run dev
```

เปิด http://localhost:3000 บนคอม สำหรับ production ใช้ npm run build และ npm run start บนคอมเช่นกัน เปลี่ยน BACKEND_URL แล้ว restart dev หรือ rebuild production

- Browser เรียก /api ผ่าน Next.js proxy บนคอม ไป Flask บน Pi :5000 ไม่ต่อ MQTT จาก browser
- Pi และคอมต้องติดต่อกันผ่าน LAN ได้; backend ต้องรับที่ WEB_HOST=0.0.0.0 ตาม example และพอร์ต 5000 ต้องเข้าถึงจากคอมได้
- ห้ามเปิด backend หลายชุด/reloader/หลาย worker เพราะมี controller แข่งกัน
- Pi ยังไม่ตั้ง systemd ของ backend/gateway ต้องรันใหม่เมื่อหยุด/reboot ส่วน Next.js เปิดใหม่บนคอม; Mosquitto/Influx เป็น service ตามคู่มือเดิม
- ใช้เฉพาะเครือข่ายทีมที่เชื่อถือได้ ยังไม่มี login/CSRF ไม่เปิดบริการกลไกสู่สาธารณะ

## 14. สอบเทียบก่อนกดเริ่ม — ไม่มีค่า counts/g ที่เดาสำเร็จรูป

ตั้ง Serial Monitor เป็น Newline และให้เว็บอยู่ PAUSED_OPERATOR ไม่มี active job ระหว่างสอบเทียบ

1. ยึด Load cell/ถาดทดลองให้ถูก รอค่าดิบค่อนข้างนิ่ง ถาดว่างแล้วส่ง `T` ต้องเห็น TARE_SAVED
2. วางน้ำหนักอ้างอิงที่ชั่งมาแล้ว รอประมาณ 2 วินาที เช่น **ถ้าน้ำหนักจริง 100 g** จึงส่ง `C 100` ต้องเห็น SCALE_SAVED อย่าใช้ 100 ถ้าไม่ได้ชั่งจริง
3. เอาออกแล้วดู weight_g ใกล้ศูนย์ วางของอ้างอิงซ้ำเพื่อตรวจความถูกต้อง
4. ติด ToF ให้นิ่งเหนือถาดทดลอง ตั้งฉากกับผิวถาด วัดได้จริง ถาดว่างแล้วส่ง `H` ต้องเห็น EMPTY_DISTANCE_SAVED
5. วางกล่องวัด height_mm เทียบไม้บรรทัด ห้ามใช้การถือเซนเซอร์ขยับในโหมดอัตโนมัติ เพราะ d_empty จะไม่คงที่ ถ้าต่อกับถาดเอียงต้องวางแนววัดตามแนวตั้งฉากถาดตามเอกสารหลัก
6. หาก ToF เริ่มต้นไม่สำเร็จ แก้สาย/บัดกรีแล้วส่ง `R` เพื่อลอง init ใหม่; ถ้าไม่ผ่าน readiness ต้องค้างไว้ ไม่ข้าม

ค่าชั่ง/ระยะอ้างอิงเก็บใน Preferences ของ ESP32 เปิดใหม่ยังอยู่ ต้องสอบเทียบใหม่เมื่อเปลี่ยนฐาน/ถาด/ตำแหน่ง ToF หรือแฟลชล้าง NVS

STABILITY_G=5 และ WINDOW=10 เป็นค่าเริ่มต้นสำหรับ bench ใน firmware ไม่ใช่เกณฑ์ที่ยืนยันแล้ว ต้องดู noise แล้วปรับตามผลจริง น้ำหนักสูงสุดไม่ใช่ 5kg ตามชื่อ Load cell เพราะพิกัดรวมถาดและกลไก

## 15. ตั้งขีดจำกัดและมุมบนเว็บ

ขณะพัก ไม่มีงานค้าง:

- ตั้งน้ำหนักสูงสุดและความสูงสูงสุดจากชุดทดลองที่รองรับจริง ขีดจำกัดต้องมากกว่า min_weight_g=20g ของ bench นี้ หากต้องทดลองของเบากว่าให้ปรับ min_weight_g ใน config และสอบเทียบให้เหมาะสมก่อนเริ่ม
- ตั้งแม่เหล็กมือที่ตำแหน่งตัวอย่าง A → กดจำมุม A ทำซ้ำ B/HOLD เว้นมุมให้ช่วง tolerance ไม่ทับกัน
- เขียนค่าที่จำลงกระดาษข้างจุดทดลอง จะได้หมุนกลับได้ถูกเมื่อรัน
- ถ้า AS5600 ต่อกับแกน Servo จริงแล้ว ให้จำมุมจากแกนจริงที่สัมพันธ์กับ CHUTE_ANGLES ใน firmware (ค่าเริ่มต้นคำสั่ง A60/B90/HOLD120) ห้ามสมมติว่าตัวเลข AS5600 จะเท่ากับคำสั่ง Servo เพราะจุดศูนย์/ทิศหมุนอาจต่างกัน
- หน้าเว็บจะไม่อนุญาตเปลี่ยน settings กลาง job

## 16. ทดสอบครบ flow บนโต๊ะครั้งแรก

1. IR ถาดว่าง; ถาดชั่งว่าง; หน้าเว็บไม่มี readiness errors; InfluxDB เป็น OK เมื่อเริ่มส่งข้อมูล
2. กดเริ่ม → IDLE
3. วางกล่องที่อยู่ในขอบเขตให้ IR ถาดเห็น รอ stable → WAIT_DECISION
4. กด A → MG996R ขยับ → POSITION
5. ในกรณีแม่เหล็กยังไม่ติดแกน ให้หมุนแม่เหล็กด้วยมือไปค่าที่จำเป็น A รักษาศูนย์กลาง/ระยะจนผ่าน angle dwell; ต้องประกาศว่า feedback จำลองด้วยมือ
6. MG90S เปิด → RELEASE/VERIFY_EXIT
7. ยกกล่องออกจากถาด ให้ IR ถาดว่างและน้ำหนักกลับศูนย์
8. ปิดประตู → COMPLETE → ประวัติเพิ่ม SORTED_A แบบ BENCH (`destination_sensed=false`)
9. ทดลอง B/HOLD, ยกกล่องออกก่อนเปิดประตู, ไม่ยกออกจนหมดเวลา, ปุ่มพัก และปิด gateway service ระหว่าง job ผลต้องตรงเงื่อนไขผิดพลาด

ถ้าขึ้น FAULT ให้เอากล่องออกและเคลียร์จริงก่อนกดปุ่มยืนยันบนเว็บ งานที่ fault จะคงเป็น fault ไม่เปลี่ยนเป็นคัดสำเร็จเพราะกดเคลียร์

## 17. ตรวจฐานข้อมูลและรันซ้ำในวันถัดไป

- กราฟย้อนหลังบนเว็บต้องแสดง source=InfluxDB หาก query ไม่ผ่านจะขึ้น error ไม่เปลี่ยนเป็นกราฟจำลองเงียบ ๆ
- ค้นประวัติบนเว็บจาก SQLite ได้หลังเปิด hub ใหม่ job_id เป็นคีย์หลัก ไม่บังคับ tracking_id
- ข้อมูล jobs/events อยู่ใน backend/data/hub.sqlite3 ส่วน Influx อยู่ Docker named volume อย่าลบข้อมูลหรือ volume ระหว่างทดสอบ
- หาก Backend ถูกปิดกลาง job เมื่อเปิดใหม่จะบันทึก INTERRUPTED/FAULT และให้คนเคลียร์ ไม่เดินต่อจากสถานะเก่าเอง
- วันถัดไปเปิด Pi/ESP32/Adapter ตามลำดับปลอดภัย รัน Backend/Gateway บน Pi และ Next.js บนคอมตามหัวข้อ 13 แล้ว commissioning checks ก่อนเริ่มเสมอ ไม่ต้อง apt/pip ใหม่ทุกครั้ง

## 18. เชื่อมทีม AI ภายหลัง

อ่าน `docs/ai/AI_INTERFACE_TH.md` แยก มี GET pending และ POST result ใช้ job_id/vision_attempt กันผลเก่า แต่ **ตอนนี้คง mode=bench ตามที่ผู้ใช้เลือก** ไม่มีการอ้างว่าเลือกบนเว็บเป็น AI

ก่อนส่งงานจริงต้องเชื่อมกล้อง/OCR/Gemini/resolver, CSV preview/activation และชั้นคั่นจากแผนหลัก รวมการแสดงภาพ/ข้อมูลผู้รับบนเว็บ รุ่น bench นี้ยังไม่มี UI นำเข้า CSV หรือแสดงรูปฉลาก และยังไม่ใช่ระบบครบ Criteria พร้อมส่ง

## 19. ตรวจซอฟต์แวร์และข้อจำกัด

ที่ราก repo บน Pi:

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
```

Frontend ตรวจบนคอมในโฟลเดอร์ frontend:

```powershell
npm run lint
npm run typecheck
npm run build
```

ผลตรวจ source ที่ยืนยันก่อนจัดทำเอกสารนี้: backend 28 tests และ frontend lint/typecheck/build ผ่าน; HTTP proxy smoke ผ่านกับ mock MQTT/SQLite ชั่วคราว และ rebuild proxy ไป Pi แล้ว แต่ยังไม่ยืนยันเชื่อม Pi/ฮาร์ดแวร์จริง ดู [VALIDATION_TH.md](../testing/VALIDATION_TH.md) การทดสอบด้วย mock/ข้อมูลจำลองไม่แทนการวัดไฟ การ compile Arduino Wi-Fi จริง หรือ Servo/เซนเซอร์จริง

ยังไม่มี login/CSRF; firmware ไม่ใช่ real-time safety controller; event ring มีขอบเขต; เมื่อ link/ไฟหายต้องอาศัยกลไกจริงที่เหมาะสม ไม่รับรองว่าประตูปิดเอง และห้ามใช้ BENCH เป็นหลักฐานคัดกล่องจริง/AI ครบ

## 20. แหล่งอ้างอิงที่ใช้เลือก API/ขา

- [ESP32-S3 pin map / memory-reserved pins](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.0.html)
- [HX711 library](https://github.com/bogde/HX711)
- [Adafruit VL53L0X API](https://github.com/adafruit/Adafruit_VL53L0X)
- [ESP32Servo](https://github.com/madhephaestus/ESP32Servo)
- [PubSubClient](https://github.com/knolleary/pubsubclient)
- [Paho callback API v2](https://eclipse.dev/paho/files/paho.mqtt.python/html/migrations.html)
- [AS5600 mounting](https://learn.adafruit.com/adafruit-as5600-magnetic-angle-sensor?view=all)
- [ESP32-S3 electrical input limits](https://documentation.espressif.com/esp32-s3_datasheet_en.pdf) — ใช้ตรวจระดับ HIGH/LOW ของ interface v2
- [Mosquitto authentication](https://mosquitto.org/documentation/authentication-methods/)
- [InfluxDB v2 Docker](https://docs.influxdata.com/influxdb/v2/install/?t=Docker)
