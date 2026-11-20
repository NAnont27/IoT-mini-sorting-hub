"""รัน CLI โดยโหลดค่าจาก ai/.env ก่อน (ไม่พิมพ์ค่า key ออกมา)

ตัวอย่าง:
  python ai/run_with_env.py --ocr ai/fixtures/ocr_demo.txt --job-id JOB-0001
"""

import os
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(AI_ROOT))

ENV_FILE = AI_ROOT / ".env"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


if __name__ == "__main__":
    load_env(ENV_FILE)
    from mini_sorting_ai.cli import main

    # path ของ --ocr อ้างอิงจากโฟลเดอร์ที่รันคำสั่ง (เช่น ai/fixtures/ocr_demo.txt จากรากรีโพ)
    sys.exit(main(sys.argv[1:]))
