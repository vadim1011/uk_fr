#!/bin/sh
# При первом запуске заполняет пустую БД, затем стартует сайт.
set +e
python - <<'PY'
import time, sys
from db import get_conn
for i in range(30):
    try:
        get_conn().close(); break
    except Exception:
        print("Жду базу данных..."); time.sleep(2)
else:
    sys.exit("БД недоступна")
conn = get_conn(); cur = conn.cursor()
cur.execute("SELECT count(*) FROM articles"); n = cur.fetchone()[0]; conn.close()
sys.exit(0 if n else 10)
PY
rc=$?
[ "$rc" = "1" ] && exit 1
if [ "$rc" = "10" ]; then
  echo "БД пуста — загружаю справочник и демо-статистику"
  python consultant_parser.py --mode seed
  python load_stats.py --demo --year 2024
fi
exec gunicorn -b 0.0.0.0:5000 -w 2 app:app
