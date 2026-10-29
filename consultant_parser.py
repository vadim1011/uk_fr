"""
Парсер статей УК РФ с consultant.ru и загрузка в PostgreSQL.

Режимы (--mode):
  seed        — загрузить подготовленный справочник data/seed_articles.json (работает без интернета);
  consultant  — собрать тексты статей с consultant.ru (раздел «Особенная часть»);
  merge       — (по умолчанию) сначала seed, затем поверх него данные с consultant.ru.

Проверка логики разбора без интернета:  python consultant_parser.py --selftest
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from db import get_conn
from sanction import parse_prison

BASE = "https://www.consultant.ru"
DOC_ID = "cons_doc_LAW_10699"
START_URL = f"{BASE}/document/{DOC_ID}/c35309e0a5b0291571f5f963bce56146e227835e/"  # «Особенная часть»
LINK_RE = re.compile(rf"/document/{DOC_ID}/[0-9a-f]{{40}}/?$")
HEADING_RE = re.compile(r"^Статья\s+(\d+(?:\.\d+)?)\.\s*(.+?)\s*$")
NOISE_RE = re.compile(r"^(КонсультантПлюс|Информация об изменениях|Список изменяющих|\(в ред\.|\(п\. .* в ред\.|"
                      r"Примечание|Открыть|Содержание|Назад|Вперёд)", re.I)
SEED_PATH = Path(__file__).parent / "data" / "seed_articles.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (educational DB project; contact: student)"}


# ---------- разбор текста ----------
def extract_articles(text):
    """Из сплошного текста страницы достаёт {номер: {title, content, punishment}}."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    found, cur = {}, None
    for line in lines:
        m = HEADING_RE.match(line)
        if m and len(line) < 300:
            cur = m.group(1)
            found.setdefault(cur, {"title": m.group(2), "body": []})
            continue
        if cur and not NOISE_RE.match(line):
            found[cur]["body"].append(line)
    result = {}
    for num, d in found.items():
        body = d["body"]
        if not body or body[0].lower().startswith("утратил"):
            continue
        sanction_lines = [l for l in body if re.search(r"наказыва\w+|наказание", l, re.I)]
        result[num] = {"title": d["title"], "content": "\n".join(body),
                       "punishment": "\n".join(sanction_lines) or None}
    return result


def page_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    node = soup.select_one(".document-page__content") or soup.body or soup
    return node.get_text("\n")


# ---------- сетевая часть ----------
def fetch(url, retries=3, delay=1.5):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200 and len(r.text) > 2000:
                return r.text
            print(f"  ! {r.status_code} {url}")
        except requests.RequestException as e:
            print(f"  ! ошибка сети: {e}")
        time.sleep(delay * (i + 1))
    return None


def crawl(max_pages=300, delay=1.2):
    """Обход от «Особенной части»: разделы -> главы -> страницы со статьями."""
    seen, queue, articles = set(), [(START_URL, 0)], {}
    while queue and len(seen) < max_pages:
        url, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        html = fetch(url)
        time.sleep(delay)
        if not html:
            continue
        got = extract_articles(page_text(html))
        for num, d in got.items():
            if num not in articles or len(d["content"]) > len(articles[num]["content"]):
                articles[num] = d
        print(f"[{len(seen)}] depth={depth} статей на странице: {len(got)} (всего {len(articles)})")
        if depth < 3:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                link = a["href"] if a["href"].startswith("http") else BASE + a["href"]
                link = link.split("#")[0].replace("http://", "https://")
                if LINK_RE.search(link) and link not in seen:
                    queue.append((link, depth + 1))
    return articles


# ---------- запись в БД ----------
UPSERT = """
INSERT INTO articles (article_number, title, url, summary, content, punishment,
                      prison_min_years, prison_max_years, source, updated_at)
VALUES (%(num)s, %(title)s, %(url)s, %(summary)s, %(content)s, %(punishment)s,
        %(pmin)s, %(pmax)s, %(source)s, now())
ON CONFLICT (article_number) DO UPDATE SET
    title = EXCLUDED.title, url = EXCLUDED.url,
    summary = COALESCE(EXCLUDED.summary, articles.summary),
    content = COALESCE(EXCLUDED.content, articles.content),
    punishment = COALESCE(EXCLUDED.punishment, articles.punishment),
    prison_min_years = EXCLUDED.prison_min_years, prison_max_years = EXCLUDED.prison_max_years,
    source = EXCLUDED.source, updated_at = now();
"""


def save(rows):
    conn = get_conn()
    with conn, conn.cursor() as cur:
        for r in rows:
            r["pmin"], r["pmax"] = parse_prison(r.get("punishment"))
            cur.execute(UPSERT, r)
    conn.close()


def seed_rows():
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return [{"num": d["article_number"], "title": d["title"],
             "url": f"{BASE}/document/{DOC_ID}/", "summary": d["summary"],
             "content": None, "punishment": d["punishment"], "source": "seed"} for d in data]


def consultant_rows(articles):
    return [{"num": n, "title": d["title"], "url": f"{BASE}/document/{DOC_ID}/",
             "summary": None, "content": d["content"], "punishment": d["punishment"],
             "source": "consultant"} for n, d in articles.items()]


SELFTEST_TEXT = """Статья 105. Убийство
1. Убийство, то есть умышленное причинение смерти другому человеку, -
наказывается лишением свободы на срок от шести до пятнадцати лет с ограничением свободы на срок до двух лет.
КонсультантПлюс: примечание.
Статья 106. Убийство матерью новорожденного ребенка
Убийство матерью новорожденного ребенка во время или сразу после родов, - наказывается лишением свободы на срок до пяти лет.
Статья 107. Утратила силу"""


def selftest():
    res = extract_articles(SELFTEST_TEXT)
    assert set(res) == {"105", "106"}, res.keys()
    assert parse_prison(res["105"]["punishment"]) == (6, 15)
    assert parse_prison(res["106"]["punishment"]) == (0, 5)
    print("selftest OK:", {k: parse_prison(v["punishment"]) for k, v in res.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["seed", "consultant", "merge"], default="merge")
    ap.add_argument("--max-pages", type=int, default=300)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.mode in ("seed", "merge"):
        rows = seed_rows()
        save(rows)
        print(f"Справочник загружен: {len(rows)} статей.")
    if args.mode in ("consultant", "merge"):
        arts = crawl(max_pages=args.max_pages)
        if not arts:
            print("С consultant.ru ничего не получено (сайт мог ограничить доступ). Остались данные справочника.")
            return
        save(consultant_rows(arts))
        print(f"С consultant.ru обновлено статей: {len(arts)}")


if __name__ == "__main__":
    sys.exit(main())
