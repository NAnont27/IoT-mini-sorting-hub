# Firmware — ESP32-S3-N16R8

- `esp32/hub_node/hub_node.ino`: โปรแกรมรวม BENCH v2
- `esp32/hub_node/secrets.example.h`: แม่แบบ Wi-Fi/MQTT config
- `bench/`: ทดสอบ Serial, HX711, ToF, Servo, ปุ่ม, E18 และสอบเทียบ

เปิดไฟล์ `.ino` ใน Arduino IDE บนคอม คัดลอก `secrets.example.h` เป็น `secrets.h` ในโฟลเดอร์เดียวกัน ใส่ค่าจริงเฉพาะในเครื่อง และ Upload ลง ESP32

Libraries: HX711 (bogde), Adafruit VL53L0X, ESP32Servo, PubSubClient และ ArduinoJson **7**; Preferences มาจาก ESP32 core

ผังขาและไฟคงเดิม: IR GPIO11–14 ใช้ INPUT ผ่าน R v2; ปุ่ม GPIO10 ใช้ INPUT_PULLUP; Servo GPIO6/7 แยกกันและใช้ไฟภายนอก

ดู [คู่มือต่อสาย/สอบเทียบ](../docs/setup/BENCH_SETUP_TH.md) และ [ผังล่าสุด](../docs/hardware/wiring_v2/README_TH.md)

ส่งไฟล์ไป Pi หรือเปลี่ยนโครงโฟลเดอร์ไม่ใช่การ flash firmware ค่า Preferences บน ESP32 ไม่เปลี่ยนจากการย้าย source นี้
