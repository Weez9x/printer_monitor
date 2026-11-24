import sqlite3
from contextlib import contextmanager
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().with_name("printers.db")


@contextmanager
def connect():
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    # SQLite создаёт файл сам при первом запуске — отдельный сервер БД не нужен.
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS printers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ip TEXT NOT NULL,
                port INTEGER NOT NULL DEFAULT 9100,
                snmp_enabled INTEGER NOT NULL DEFAULT 1,
                snmp_port INTEGER NOT NULL DEFAULT 161
            )
            """
        )


def list_printers():
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, name, ip, port, snmp_enabled, snmp_port "
            "FROM printers ORDER BY name COLLATE NOCASE, id"
        ).fetchall()
    return [dict(row) for row in rows]


def add_printer(name, ip, port, snmp_enabled, snmp_port):
    name = name.strip()
    ip = ip.strip()
    if not name or not ip:
        raise ValueError("Укажите имя и IP-адрес принтера")
    if not 1 <= int(port) <= 65535:
        raise ValueError("Порт печати должен быть от 1 до 65535")
    if not 1 <= int(snmp_port) <= 65535:
        raise ValueError("SNMP-порт должен быть от 1 до 65535")
    with connect() as connection:
        connection.execute(
            "INSERT INTO printers (name, ip, port, snmp_enabled, snmp_port) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, ip, int(port), int(bool(snmp_enabled)), int(snmp_port)),
        )
    return list_printers()


def delete_printer(printer_id):
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM printers WHERE id = ?", (int(printer_id),)
        )
        if cursor.rowcount == 0:
            raise ValueError("Такого принтера уже нет в базе")
    return list_printers()
