r"""รัน vision worker โดยโหลด ai/.env ก่อน (ไม่พิมพ์ค่า key)

บนคอม (D026) จากราก repo:
  .venv\Scripts\python.exe ai\run_worker.py --backend http://<IP Pi>:5000
"""

import sys

from run_with_env import ENV_FILE, load_env

if __name__ == "__main__":
    load_env(ENV_FILE)
    from mini_sorting_ai.worker import main

    sys.exit(main(sys.argv[1:]))
