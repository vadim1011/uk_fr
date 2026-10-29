"""Общее подключение к PostgreSQL. Параметры берутся из переменных окружения."""
import os
import psycopg2
import psycopg2.extras


def get_conn():
    return psycopg2.connect(
        dbname=os.environ.get("DB_NAME", "jurist_laws"),
        user=os.environ.get("DB_USER", "jurist_user"),
        password=os.environ.get("DB_PASSWORD", "jurist_password"),
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        connect_timeout=5,
    )


def dict_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
