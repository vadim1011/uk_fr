"""
Загрузка судебной статистики в таблицу court_practice.

  python load_stats.py --csv data/court_stats.csv   — РЕАЛЬНЫЕ данные (is_demo = FALSE)
  python load_stats.py --demo [--year 2024]         — УЧЕБНЫЕ данные для всех статей (is_demo = TRUE)

Формат CSV (UTF-8, разделитель запятая):
  article_number,year,charged,prison,suspended,other_punishment,acquitted_terminated,source
Условие: prison + suspended + other_punishment + acquitted_terminated = charged.
Реальные строки перезаписывают демо-строки той же статьи и года; демо реальные не трогает.
"""
import argparse
import csv
import hashlib
import random

from db import get_conn

UPSERT = """
INSERT INTO court_practice (article_number, year, charged, prison, suspended,
                            other_punishment, acquitted_terminated, is_demo, source)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (article_number, year) DO UPDATE SET
    charged=EXCLUDED.charged, prison=EXCLUDED.prison, suspended=EXCLUDED.suspended,
    other_punishment=EXCLUDED.other_punishment, acquitted_terminated=EXCLUDED.acquitted_terminated,
    is_demo=EXCLUDED.is_demo, source=EXCLUDED.source
WHERE court_practice.is_demo = TRUE OR EXCLUDED.is_demo = FALSE;
"""
# ^ демо-строка не затирает реальную: обновляем, только если старая строка демо ИЛИ новая реальная


def load_csv(path):
    conn, ok, bad = get_conn(), 0, 0
    conn.autocommit = True  # ошибка в одной строке не откатывает остальные
    with conn.cursor() as cur, open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                v = [int(row[k]) for k in ("year", "charged", "prison", "suspended",
                                           "other_punishment", "acquitted_terminated")]
                if v[2] + v[3] + v[4] + v[5] != v[1]:
                    raise ValueError("сумма категорий не равна числу привлечённых")
                cur.execute(UPSERT, (row["article_number"].strip(), v[0], v[1], v[2], v[3], v[4], v[5],
                                     False, row.get("source") or "csv"))
                ok += 1
            except Exception as e:
                bad += 1
                print(f"  ! строка {row}: {e}")
    conn.close()
    print(f"Загружено: {ok}, отклонено: {bad}")


def load_demo(year):
    conn = get_conn()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT article_number FROM articles")
        nums = [r[0] for r in cur.fetchall()]
        for n in nums:
            rnd = random.Random(int(hashlib.md5(n.encode()).hexdigest(), 16))  # детерминированно
            charged = rnd.randint(80, 4000)
            p = rnd.randint(20, 45); s = rnd.randint(20, 35); a = rnd.randint(1, 8)  # сумма < 100%, остаток = иные наказания
            prison, susp, acq = charged * p // 100, charged * s // 100, charged * a // 100
            other = charged - prison - susp - acq
            cur.execute(UPSERT, (n, year, charged, prison, susp, other, acq, True, "DEMO: сгенерировано"))
    conn.close()
    print(f"Демо-статистика создана для {len(nums)} статей (год {year}).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--year", type=int, default=2024)
    a = ap.parse_args()
    if a.csv:
        load_csv(a.csv)
    if a.demo:
        load_demo(a.year)
    if not a.csv and not a.demo:
        ap.print_help()
