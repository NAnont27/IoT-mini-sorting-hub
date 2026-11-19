# Git สำหรับทีม Mini Sorting Hub

ตรวจสถานะ **20 พฤศจิกายน 2026**: Git ในเครื่องเป็น branch main มี 82 ไฟล์ staged แต่ยังมีเอกสารที่แก้หลัง staging และไฟล์ audit ใหม่ ต้อง git add อีกรอบก่อน commit ล่าสุดยังไม่มี commit หรือ remote คำสั่งในคู่มือนี้เป็นวิธีให้ผู้ใช้รัน ไม่ได้ทำการอัปโหลดให้แล้ว

## อะไรเก็บใน Git

- source ใน frontend/backend/gateway/firmware, docs, README และ AGENTS.md
- package.json และ package-lock.json เพื่อติดตั้ง dependency ให้เหมือนกัน
- .env.example, config.example.json และ secrets.example.h ที่ไม่มีรหัสจริง

ไฟล์ค่าจริง, รูปฉลากผู้พัก, data, .venv, node_modules, .next, archive และ artifacts ถูก ignore ไว้ อย่าใช้ git add -f เพื่อฝืนเพิ่ม

## ตรวจและสร้าง commit แรก

เปิด PowerShell ที่รากโปรเจกต์ ไม่ต้อง git init ซ้ำ:

```powershell
Set-Location C:/Users/nanon/Desktop/CU/IoT/Project
git status --short --branch
git add --dry-run .
```

ตรวจรายการก่อนเพิ่ม แล้วจึง:

```powershell
git add .
git diff --cached --stat
git diff --cached --check
git commit -m "refactor: organize mini sorting hub monorepo"
```

ดู diff ส่วนที่แก้ก่อน commit เพิ่มด้วย git diff --cached หากต้องการอ่านเนื้อหา ใช้ identity ที่ตั้งไว้ใน Git ของผู้ใช้ ไม่ใส่ชื่อ/อีเมลคนอื่นเพื่อให้ commit ผ่าน

หาก commit ไปแล้วแก้ไฟล์เพิ่มเติม ต้อง git add/commit รอบใหม่ ไฟล์ที่แก้ในคอมไม่อัปเดต GitHub/Pi/ESP32 ให้เอง

## สร้าง repository บน GitHub

เปิด https://github.com/new ในบัญชีของตัวเอง ตั้งชื่อเช่น mini-sorting-hub และเลือก Private หากใช้เฉพาะทีม จากนั้นสร้าง repository เปล่า **ไม่เพิ่ม README, .gitignore หรือ License ในหน้าเว็บรอบนี้** เพราะมี local repository และไฟล์อยู่แล้ว

คัดลอก HTTPS URL ของ repository ที่สร้างจริง ไม่ใช้ URL ตัวอย่างสั่ง push โดยไม่เปลี่ยนค่า

## ล็อกอินและ push ครั้งแรก

เครื่องนี้มี GitHub CLI แล้ว หากต้องล็อกอินใหม่ เปิด PowerShell:

```powershell
gh auth login
```

เลือก GitHub.com → HTTPS → Login with a web browser และทำตามรหัส/หน้าต่างที่โปรแกรมให้ ไม่ส่ง token หรือรหัสยืนยันให้ผู้อื่น จากนั้นเชื่อม Git กับ credential ของ CLI:

```powershell
gh auth setup-git
```

ที่รากโปรเจกต์ หลัง commit แรกสำเร็จแล้ว แทน YOUR_USERNAME ด้วยเจ้าของ repo จริง และเปลี่ยนชื่อ repo ถ้าใช้ชื่ออื่น:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/mini-sorting-hub.git
git remote -v
git push -u origin main
```

ตรวจ remote ให้เป็น repository ของตัวเองก่อน push เมื่อสำเร็จ refresh หน้า GitHub จะเห็น frontend/backend/gateway/firmware/docs โดยไม่มี .env/node_modules/.next/ข้อมูลจริง

หากมี origin อยู่แล้วให้ตรวจ URL ก่อน ไม่สั่ง add ซ้ำหรือเปลี่ยน remote โดยเดา หาก push ไม่ผ่านอย่าใช้ --force เพื่อแก้ ให้ตรวจ error และ remote history ก่อน

## อัปเดตไฟล์รอบถัดไป

```powershell
git add .
git diff --cached --stat
git commit -m "docs: update project guide"
git push
```

เปลี่ยน commit message ให้ตรงงานจริง การ push source ไม่ deploy หรือ flash Pi/ESP32 ให้อัตโนมัติ

อ้างอิง [GitHub: Adding locally hosted code](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github?platform=windows)

## ทำงานในทีมภายหลัง

เมื่อมี remote แล้ว ให้แต่ละงานใช้ branch ของตัวเอง เช่น feat/ocr-pipeline หรือ fix/ir-passage และทำ PR กลับ main ตรวจโค้ด/ผลทดสอบก่อนรวม

ผู้ใช้ถามวิธีนำขึ้น GitHub แล้ว แต่ยังไม่มี URL repository และยังไม่ได้สั่งให้ agent สร้าง/commit/push ให้ การเลือกบัญชี/สิทธิ์และรันคำสั่งข้างต้นยังเป็นขั้นตอนที่ต้องทำจริง

## ทำ source ZIP จาก commit

หลังมี commit แล้ว สั่งที่ราก repo:

```powershell
New-Item -ItemType Directory -Path artifacts -Force
git archive --format=zip --output=artifacts/mini-sorting-hub-source.zip HEAD
```

ZIP รวมเฉพาะ source ที่ commit แล้ว ไม่มี uncommitted changes และไม่รวมไฟล์ที่ถูก ignore อ่าน [คู่มือติดตั้ง Pi](BENCH_SETUP_TH.md) สำหรับส่งขึ้นเครื่องทดสอบ
