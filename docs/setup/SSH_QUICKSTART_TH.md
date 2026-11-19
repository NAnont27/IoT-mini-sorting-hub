# SSH และรันชุดทดสอบ — โครง monorepo

อัปเดต 16 พ.ย. 2026 สำหรับ source ใหม่ใน ~/mini-sorting-hub; เครื่อง Pi ที่ยังใช้ ~/mini-sorting-hub/bench เดิมไม่ได้เปลี่ยนตามไฟล์ในคอมโดยอัตโนมัติ ดู [Migration](MIGRATION_TH.md)

## 1. เข้า Pi จาก PowerShell

```powershell
ssh nanont@pi-673305942.local
```

ถ้า .local ไม่ได้ให้ใช้ IP จริงของ Pi ไม่ต้องใส่รหัสผ่านลงคำสั่ง ขณะพิมพ์รหัสผ่านจะไม่เห็นตัวอักษร ครั้งแรกตรวจ host key ให้ตรงเครื่อง

## 2. รันทดสอบแยกชิ้นบน Pi

หลังติดตั้ง .venv/requirements ตาม [คู่มือ BENCH](BENCH_SETUP_TH.md) แล้ว เลือกทดสอบทีละตัว อย่าเปิด gateway รวมแข่งกันอ่าน I2C

AS5600:

```bash
cd ~/mini-sorting-hub
.venv/bin/python gateway/bench/as5600_test.py
```

BH1750:

```bash
cd ~/mini-sorting-hub
.venv/bin/python gateway/bench/bh1750_test.py
```

หยุดด้วย Ctrl+C; ตรวจบัสเมื่อมีปัญหา:

```bash
sudo i2cdetect -y 1
```

BH1750 ต้องเห็น 23 และ AS5600 ต้องเห็น 36 ผล scan ไม่ใช่หลักฐานว่าอ่านมุม/แสงถูกต้องแล้ว

## 3. สอง SSH terminal บน Pi และ PowerShell บนคอม

Backend:

```bash
cd ~/mini-sorting-hub
.venv/bin/python -m backend.app
```

Gateway อีก terminal:

```bash
cd ~/mini-sorting-hub
.venv/bin/python gateway/gateway_sensors.py
```

Frontend รันบนคอม Windows ใน PowerShell อีกหน้า ไม่ใช่ SSH terminal:

```powershell
Set-Location C:/Users/nanon/Desktop/CU/IoT/Project/frontend
npm run dev
```

ติดตั้งด้วย npm ci ครั้งแรก และตั้ง frontend/.env.local ให้ BACKEND_URL=http://pi-673305942.local:5000 ก่อน ถ้า .local ไม่ resolve ให้ใช้ IP จริงของ Pi

เปิด http://localhost:3000 บนคอม ส่วน :5000 เป็น Flask API บน Pi ไม่มี Node.js/Next.js บน Pi ตามแบบที่เลือก

SSH ใหม่ไม่ต้องติดตั้ง packages ซ้ำ แต่ต้องรัน backend/gateway บน Pi ใหม่ถ้า process หยุด/reboot ส่วน frontend เปิดใหม่บนคอม อ่าน frontend/README.md สำหรับโหมด production

## 4. Influx ผ่าน SSH tunnel

จาก PowerShell อีกหน้าต่าง:

```powershell
ssh -L 8086:127.0.0.1:8086 nanont@pi-673305942.local
```

เปิด http://localhost:8086 สำหรับจัดการ Influx ไม่ใส่ token ในแชต/คำสั่งที่เผยแพร่ และไม่ลบ Docker volume ระหว่างทดสอบ
