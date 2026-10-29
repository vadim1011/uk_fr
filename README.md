# Информационная система «УК РФ»

Учебный проект по базам данных. Пользователь вводит номер статьи Уголовного кодекса РФ (или слово из её названия) и получает:

- **что значит статья** — краткое пояснение и полный текст (если спарсен с consultant.ru);
- **наказание** — текст санкции и извлечённые пределы лишения свободы («от X до Y лет»);
- **судебную практику** — сколько лиц привлечено, сколько осуждено к реальному сроку, условно, к иным мерам и сколько оправдано / дел прекращено (круговая диаграмма и полосы);
- **текстовый отчёт** по статье для скачивания.

## Стек

| Слой | Технология |
|---|---|
| База данных | PostgreSQL 16 в Docker, просмотр через DBeaver |
| Сервер | Python 3.12, Flask, gunicorn |
| Парсер | requests + BeautifulSoup (consultant.ru) |
| Интерфейс | HTML + CSS + JavaScript (без внешних библиотек) |

## Структура проекта

```
├── app.py                  # веб-сервер и API
├── consultant_parser.py    # парсер consultant.ru и загрузка статей в БД
├── load_stats.py           # загрузка судебной статистики (CSV / демо)
├── sanction.py             # извлечение «от X до Y лет» из текста санкции
├── db.py                   # подключение к PostgreSQL
├── init.sql                # схема БД (создаётся автоматически)
├── templates/index.html    # страница сайта
├── data/
│   ├── seed_articles.json  # справочник статей (работает без интернета)
│   └── court_stats.csv     # сюда кладутся РЕАЛЬНЫЕ данные судстатистики
├── Dockerfile, docker-compose.yml, entrypoint.sh, requirements.txt
```

## Схема базы данных

```
articles (1) ────────< court_practice (N)
 article_number  UNIQUE        article_number → articles
 title, summary, content       year, charged, prison, suspended,
 punishment                    other_punishment, acquitted_terminated,
 prison_min_years / max_years  is_demo, source
 source ('seed'|'consultant')  UNIQUE (article_number, year)
                               CHECK: prison+suspended+other_punishment+acquitted_terminated = charged
```

Связь «один ко многим»: у статьи может быть статистика за несколько лет, сайт показывает последний год.

## Быстрый запуск (всё в Docker)

```bash
docker compose up -d --build
```

Сайт: http://localhost:5000. При первом старте пустая база сама заполняется справочником статей и демо-статистикой.

## Запуск для разработки (VS Code)

```bash
docker compose up -d db                 # только база данных
python -m venv .venv
.venv\Scripts\activate                  # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python consultant_parser.py --mode seed # статьи из справочника
python load_stats.py --demo --year 2024 # демо-статистика
python app.py                           # http://localhost:5000
```

## Парсер consultant.ru

```bash
python consultant_parser.py --mode merge       # справочник + тексты статей с consultant.ru
python consultant_parser.py --mode consultant  # только consultant.ru
python consultant_parser.py --selftest         # проверка разбора текста без интернета и БД
```

Парсер обходит «Особенную часть» УК РФ (разделы → главы → страницы), вырезает блоки «Статья N. Название», собирает текст и строки с санкцией («наказывается…»), затем вычисляет пределы лишения свободы. Между запросами пауза 1,2 с. Если сайт недоступен или ограничил доступ, остаются данные справочника. Соблюдайте условия доступа consultant.ru и используйте парсер в учебных целях.

## Судебная статистика: важно

Таблица `court_practice` содержит поле `is_demo`. Команда `--demo` создаёт **учебные, сгенерированные числа**, и сайт явно помечает их предупреждением. Это не реальная статистика.

Реальные данные загружаются из CSV:

```
article_number,year,charged,prison,suspended,other_punishment,acquitted_terminated,source
105,2024,5700,4100,300,200,1100,Судебный департамент при ВС РФ, форма 10.1
```

```bash
python load_stats.py --csv data/court_stats.csv
```

Строки с неверной суммой отклоняются, а реальные данные заменяют демо-данные той же статьи и года. Источник цифр: отчёты Судебного департамента при Верховном Суде РФ о числе осуждённых по статьям УК РФ. В апреле 2026 г. публикация этой статистики на сайте департамента была приостановлена, поэтому цифры берите из ранее скачанных отчётов или архивных копий и всегда указывайте источник в колонке `source`.

## Подключение DBeaver

`Database → New Connection → PostgreSQL`: host `localhost`, port `5432`, database `jurist_laws`, user `jurist_user`, password `jurist_password`.

Полезные запросы:

```sql
SELECT a.article_number, a.title, c.charged, c.prison, c.is_demo
FROM articles a JOIN court_practice c USING (article_number)
ORDER BY c.charged DESC LIMIT 10;

SELECT count(*) FROM articles;
```

## Частые проблемы

| Проблема | Решение |
|---|---|
| `port 5432 is already allocated` | остановите старый контейнер БД: `docker ps`, затем `docker stop <имя>` |
| Ошибки «column ... does not exist» после старой версии проекта | старая схема в томе: `docker compose down -v`, затем `docker compose up -d --build` |
| Сайт пишет «База данных недоступна» | `docker compose ps`, дождитесь статуса `healthy` у `db` |
| Парсер ничего не нашёл | сайт мог изменить вёрстку или ограничить доступ; работает режим `--mode seed` |
