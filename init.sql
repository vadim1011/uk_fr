-- Схема БД. Выполняется автоматически при первом запуске контейнера PostgreSQL.
CREATE TABLE IF NOT EXISTS articles (
    id               SERIAL PRIMARY KEY,
    article_number   VARCHAR(20) UNIQUE NOT NULL,          -- '105', '110.1'
    title            TEXT        NOT NULL,                 -- название статьи
    url              TEXT,                                 -- источник
    summary          TEXT,                                 -- краткое пояснение «что значит»
    content          TEXT,                                 -- полный текст статьи (если спарсен)
    punishment       TEXT,                                 -- санкция словами
    prison_min_years NUMERIC(5,2),                         -- нижний предел лишения свободы, лет
    prison_max_years NUMERIC(5,2),                         -- верхний предел лишения свободы, лет
    source           VARCHAR(20) NOT NULL DEFAULT 'seed',  -- 'seed' | 'consultant'
    updated_at       TIMESTAMP   NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS court_practice (
    id                   SERIAL PRIMARY KEY,
    article_number       VARCHAR(20) NOT NULL REFERENCES articles(article_number) ON DELETE CASCADE,
    year                 INT     NOT NULL,
    charged              INT     NOT NULL CHECK (charged >= 0),   -- привлечено (всего лиц)
    prison               INT     NOT NULL CHECK (prison >= 0),    -- реальное лишение свободы
    suspended            INT     NOT NULL CHECK (suspended >= 0), -- условное осуждение
    other_punishment     INT     NOT NULL CHECK (other_punishment >= 0), -- штраф, работы и т.п.
    acquitted_terminated INT     NOT NULL CHECK (acquitted_terminated >= 0), -- оправдано / дело прекращено
    is_demo              BOOLEAN NOT NULL DEFAULT FALSE,          -- TRUE = учебные данные, не реальные
    source               TEXT,
    UNIQUE (article_number, year),
    CHECK (prison + suspended + other_punishment + acquitted_terminated = charged)
);

CREATE INDEX IF NOT EXISTS idx_practice_article ON court_practice(article_number, year DESC);
