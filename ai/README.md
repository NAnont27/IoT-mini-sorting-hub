# โมดูล AI — Mini Sorting Hub

สถานะ: **ขั้นแรก: resolver ตามกฎทะเบียน** (ยังไม่มีกล้อง OCR หรือ Gemini ในโฟลเดอร์นี้)

## สิ่งที่มีแล้ว

- `mini_sorting_ai/registry.py` โหลด CSV ทะเบียนและ config เป็น snapshot อ่านอย่างเดียว ตรวจค่าว่าง, resident_id ซ้ำ, ห้องที่ map ได้มากกว่าหนึ่งชั้น และชั้นนอก valid_floors
- `mini_sorting_ai/resolver.py` กฎ A/B/HOLD/RETRY_CAPTURE ตาม `docs/ai/AI_INTERFACE_TH.md` พร้อม envelope และ `service_error` / `pipeline_error`
- `tests/test_resolver.py` ทดสอบกฎสำคัญ (ห้อง A/B, ชั้นนอกตาราง, ชื่อซ้ำ, ชื่อขัดกัน, เลขห้องผู้ส่ง, ข้อมูลไม่พอ, schema ผิด)
- `fixtures/registry_demo.csv` และ `config.example.json` เป็นข้อมูลสมมติสำหรับ demo

## รันทดสอบ (stdlib อย่างเดียว ไม่ต้องติดตั้งแพ็กเกจ)

จากรากรีโพ:

```powershell
python -m unittest discover -s ai/tests -v
```

## ขอบเขตที่ยังไม่ทำ

- ยังไม่มี `process_label()` (รวมภาพ → OCR → Gemini → resolver) จะเพิ่มเมื่อ resolver ผ่านเทสต์
- ยังไม่มี Gemini adapter; ต้องตรวจเอกสาร SDK/โมเดลปัจจุบันก่อนเขียน และไม่ใส่ API key ในโค้ด
- ยังไม่มี camera adapter บน Pi
- ค่า `a_max_floor` และ `valid_floors` ใน config เป็นค่าสมมติ ยังไม่ใช่ค่าที่ทีมล็อกแล้ว
