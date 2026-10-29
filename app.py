"""Информационная система «УК РФ»: поиск статьи, наказание, судебная практика."""
import re
from flask import Flask, Response, jsonify, render_template, request

from db import dict_cursor, get_conn

app = Flask(__name__)
app.json.ensure_ascii = False


def normalize(q):
    """'ст. 105', 'Статья 110,1', ' 228.1 ' -> '105' / '110.1' / '228.1'; иначе None."""
    m = re.search(r"\d+(?:[.,]\d+)?", q or "")
    return m.group(0).replace(",", ".") if m else None


def load_article(num):
    conn = get_conn()
    try:
        with dict_cursor(conn) as cur:
            cur.execute("""SELECT article_number, title, url, summary, content, punishment,
                                  prison_min_years, prison_max_years, source
                           FROM articles WHERE article_number = %s""", (num,))
            art = cur.fetchone()
            if not art:
                return None, None
            cur.execute("""SELECT year, charged, prison, suspended, other_punishment,
                                  acquitted_terminated, is_demo, source
                           FROM court_practice WHERE article_number = %s
                           ORDER BY year DESC LIMIT 1""", (num,))
            stat = cur.fetchone()
    finally:
        conn.close()
    for k in ("prison_min_years", "prison_max_years"):
        if art[k] is not None:
            art[k] = float(art[k])
    if stat and stat["charged"]:
        stat["percent"] = {k: round(stat[k] * 100 / stat["charged"], 1)
                           for k in ("prison", "suspended", "other_punishment", "acquitted_terminated")}
    return art, stat


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/article")
def api_article():
    raw = request.args.get("q", "")
    num = normalize(raw)
    try:
        if not num:  # поиск по названию: «кража», «взятк»
            conn = get_conn()
            with dict_cursor(conn) as cur:
                cur.execute("""SELECT article_number, title FROM articles WHERE title ILIKE %s
                               ORDER BY string_to_array(article_number, '.')::numeric[] LIMIT 10""",
                            (f"%{raw.strip()}%",))
                found = cur.fetchall()
            conn.close()
            if not raw.strip() or not found:
                return jsonify(status="not_found", message="Ничего не найдено. Введите номер статьи или слово из названия"), 404
            if len(found) > 1:
                return jsonify(status="choose", items=found)
            num = found[0]["article_number"]
        art, stat = load_article(num)
    except Exception as e:  # БД недоступна
        app.logger.error("DB error: %s", e)
        return jsonify(status="db_error", message="База данных недоступна"), 503
    if not art:
        return jsonify(status="not_found", message=f"Статья {num} отсутствует в базе"), 404
    return jsonify(status="ok", article=art, stats=stat)


@app.route("/api/suggest")
def api_suggest():
    """Подсказки по названию («убий» -> 105, 106 ...) для поля поиска."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify([])
    try:
        conn = get_conn()
        with dict_cursor(conn) as cur:
            cur.execute("""SELECT article_number, title FROM articles
                           WHERE title ILIKE %s OR article_number LIKE %s
                           ORDER BY string_to_array(article_number, '.')::numeric[] LIMIT 8""",
                        (f"%{q}%", f"{q}%"))
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        app.logger.error("suggest error: %s", e)
        return jsonify([])


@app.route("/download/<num>")
def download(num):
    num = normalize(num)
    art, stat = load_article(num) if num else (None, None)
    if not art:
        return Response("Статья не найдена", status=404, mimetype="text/plain; charset=utf-8")
    lines = ["ОТЧЁТ ПО СТАТЬЕ УК РФ", "=" * 44,
             f"Статья {art['article_number']}. {art['title']}", "",
             "ЧТО ЗНАЧИТ:", art["summary"] or art["content"] or "нет данных", "",
             "НАКАЗАНИЕ:", art["punishment"] or "нет данных"]
    if art["prison_max_years"] is not None:
        lines.append(f"Лишение свободы: от {art['prison_min_years']:g} до {art['prison_max_years']:g} лет")
    lines += ["", f"СУДЕБНАЯ ПРАКТИКА{' (РЕАЛЬНАЯ СТАТИСТИКА)' if stat and stat['is_demo'] else ''}:"]
    if stat:
        p = stat["percent"]
        lines += [f"Год: {stat['year']}", f"Привлечено лиц: {stat['charged']}",
                  f"Реальное лишение свободы: {stat['prison']} ({p['prison']}%)",
                  f"Условное осуждение: {stat['suspended']} ({p['suspended']}%)",
                  f"Иные наказания: {stat['other_punishment']} ({p['other_punishment']}%)",
                  f"Оправдано / прекращено: {stat['acquitted_terminated']} ({p['acquitted_terminated']}%)"]
    else:
        lines.append("Данные не загружены.")
    lines += ["", "=" * 44, "Сгенерировано информационной системой."]
    return Response("\n".join(lines), mimetype="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=Report_{num}.txt"})


@app.route("/health")
def health():
    try:
        conn = get_conn(); conn.close()
        return jsonify(status="ok")
    except Exception:
        return jsonify(status="db_down"), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
