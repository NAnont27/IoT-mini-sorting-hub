# Frontend — Next.js Dashboard

Next.js App Router + TypeScript + Tailwind CSS โดยใช้ Webpack และ Tailwind PostCSS สำหรับ dev/build

```text
src/
├── app/                         # routes, layout, globals.css
├── features/dashboard/          # Dashboard, SettingsPanel, JobsPanel, HistoryPanel
├── lib/api/client.ts            # HTTP client / errors / timeout
└── types/hub.ts                  # response and domain types
```

## เริ่มพัฒนา

ผู้ใช้เลือกให้ Next.js รันบน **คอม Windows** ส่วน Flask/Gateway อยู่ **Pi** ต้องมี Node.js >=20.9 และ npm บนคอม เปิด PowerShell ใน frontend:

```powershell
npm ci
```

คัดลอก .env.example เป็น .env.local หากยังไม่มีค่าจริง แก้ BACKEND_URL ให้ตรงเครื่องที่รัน Flask:

```dotenv
BACKEND_URL=http://pi-673305942.local:5000
```

ถ้า hostname .local ไม่ resolve บนคอม ให้เปลี่ยนเป็น IP LAN จริงของ Pi; localhost ในช่องนี้หมายถึงคอม ไม่ใช่ Pi ไม่ต้องติดตั้ง Node.js/npm หรือส่ง frontend ไป Pi

```powershell
npm run dev
```

เปิด http://localhost:3000; หากต้องเข้าจากเครื่องอื่นใน LAN ใช้ npm run dev -- --hostname 0.0.0.0

Frontend เรียก /api ผ่าน Next.js rewrites ไป backend ไม่ต้องส่งรหัส MQTT/Influx เข้า browser และไม่ต้องเพิ่ม CORS แบบเปิดกว้าง

## ตรวจและรัน production

```powershell
npm run lint
npm run typecheck
npm run build
npm run start -- --hostname 0.0.0.0
```

เปลี่ยน BACKEND_URL แล้ว restart dev; production ต้อง build ใหม่เพราะค่า rewrite ถูกกำหนดขณะ build

ใช้ Webpack เพราะ Turbopack ของชุดตั้งต้นล้มขณะสร้าง worker บนเครื่อง Windows ที่ใช้พัฒนา การเปลี่ยน bundler ไม่เปลี่ยน Next.js หรือ API ของโปรเจกต์

## ฟังก์ชันที่ย้ายมาจากหน้าเดิม

- Operator console แบบ responsive มี sidebar, สรุปสถานะ/readiness และการเชื่อมต่อ Backend
- การ์ด telemetry สำหรับน้ำหนัก ความสูง มุมราง แสง และทางผ่าน IR (polling ประมาณ 1s หลัง request จบ)
- พัก/เริ่มต่อ เลือก A/B/HOLD เมื่องานอยู่ WAIT_DECISION ลอง AI ใหม่ และ reset fault หลังผู้ใช้ยืนยันเคลียร์จริง
- ตั้งขีดจำกัดและจำมุมจาก AS5600 ผ่าน backend
- ค้นประวัติ jobs (polling ประมาณ 5s หลัง request จบ)
- โหลดกราฟจาก InfluxDB หรือแสดง SQLite fallback ตามสถานะจริง

การเลือกช่องและส่ง API ไม่ใช่ผลคัดสำเร็จ Backend/firmware ต้องตรวจมุมและ IR เหมือนเดิม ไม่มีการเพิ่ม CSV/camera/AI จำลองเพียงเพื่อให้หน้าเว็บดูครบ

## อ้างอิง

- [Next.js installation](https://nextjs.org/docs/app/getting-started/installation)
- [Next.js rewrites](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites)
- [Next.js Webpack support](https://nextjs.org/docs/app/guides/upgrading/version-16)
- [Tailwind PostCSS](https://tailwindcss.com/docs/installation/using-postcss)
- [ผลตรวจและข้อจำกัด](../docs/testing/VALIDATION_TH.md)
