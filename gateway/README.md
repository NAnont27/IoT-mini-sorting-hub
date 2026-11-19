# Gateway — Raspberry Pi 5

`gateway_sensors.py` อ่าน AS5600/BH1750 บน I2C ของ Pi แล้วส่ง `sorter/gateway` ผ่าน MQTT ส่วน `bench/` ใช้ทดสอบทีละอุปกรณ์

จากราก repo ติดตั้ง `gateway/requirements.txt` ใน `.venv` ตาม README หลัก คัดลอก `gateway/.env.example` เป็น `gateway/.env` และใส่ MQTT credentials ที่ตรง broker

```bash
.venv/bin/python gateway/gateway_sensors.py
```

อ่านค่าจาก `gateway/.env` แยกจาก backend ไม่ต้องเก็บ Influx token ฝั่งนี้

ทดสอบแยกชิ้นบน Pi ขณะหยุด gateway รวมแล้ว:

```bash
.venv/bin/python gateway/bench/as5600_test.py
.venv/bin/python gateway/bench/bh1750_test.py
```

เลือกทำทีละคำสั่ง หยุดด้วย Ctrl+C ไม่ให้หลายโปรแกรมอ่าน I2C แข่งกัน Windows ใช้ตรวจ syntax ได้ แต่ไม่มี /dev/i2c-1 สำหรับวัดเซนเซอร์จริง

กล้อง/OCR/Gemini เป็นงาน AI team ยังไม่เพิ่ม worker จำลองหรือโค้ดสั่ง Servo ใน Gateway ดู [AI interface](../docs/ai/AI_INTERFACE_TH.md)
