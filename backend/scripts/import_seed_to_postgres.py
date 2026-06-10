#!/usr/bin/env python3

"""Import the local SQLite seed database into the Postgres development database.

This script is intended for development only. It reads the SQLite seed file at
backend/database/database.db, truncates the matching Postgres tables, copies the
seed rows across, and resets the audit_events identity sequence.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.security import hash_password


BACKEND_DIR = Path(__file__).resolve().parents[1]
SQLITE_DB = BACKEND_DIR / "database" / "database.db"
POSTGRES_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/ai_assessment",
)
SEED_ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@admin.com")
SEED_ADMIN_NAME = os.getenv("SEED_ADMIN_NAME", "Admin")
SEED_ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "admin")


TABLES_IN_TRUNCATE_ORDER = [
    "audit_events",
    "chat_messages",
    "overlap_signals",
    "evidence",
    "recordings",
    "assessments",
    "student_projects",
    "students",
    "projects",
    "modules",
    "teachers",
    "departments",
    "file_records",
]

TABLES_IN_INSERT_ORDER = [
    "departments",
    "teachers",
    "file_records",
    "modules",
    "projects",
    "students",
    "student_projects",
    "assessments",
    "recordings",
    "chat_messages",
    "audit_events",
    "evidence",
    "overlap_signals",
]

BOOLEAN_COLUMNS = {
    "teachers": {"is_admin", "is_seed"},
    "students": {"consent_given"},
    "assessments": {"consent_recorded"},
}


def parse_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        text_value = value.strip()
        if text_value in {"true", "false"}:
            return text_value == "true"
        return value
    return value


def load_sqlite_rows(sqlite_conn: sqlite3.Connection, table: str):
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.execute(f"SELECT * FROM {table}")
    rows = []
    bool_columns = BOOLEAN_COLUMNS.get(table, set())
    for row in cursor.fetchall():
        parsed_row = {}
        for key in row.keys():
            value = parse_value(row[key])
            if key in bool_columns and value is not None:
                value = bool(value)
            parsed_row[key] = value
        rows.append(parsed_row)
    return rows


def truncate_postgres(engine) -> None:
    statement = "TRUNCATE TABLE " + ", ".join(TABLES_IN_TRUNCATE_ORDER) + " RESTART IDENTITY CASCADE"
    with engine.begin() as connection:
        connection.execute(text(statement))


def insert_rows(engine, table: str, rows: list[dict]) -> None:
    if not rows:
        return

    columns = list(rows[0].keys())
    column_sql = ", ".join(columns)
    value_sql = ", ".join(f":{column}" for column in columns)
    statement = text(f"INSERT INTO {table} ({column_sql}) VALUES ({value_sql})")

    with engine.begin() as connection:
        for row in rows:
            connection.execute(statement, row)


def reset_audit_sequence(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "SELECT setval("
                "  pg_get_serial_sequence('audit_events', 'id'),"
                "  COALESCE((SELECT MAX(id) FROM audit_events), 1),"
                "  true"
                ")"
            )
        )


def ensure_seed_admin(engine) -> None:
    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT 1 FROM teachers WHERE email = :email"),
            {"email": SEED_ADMIN_EMAIL},
        ).scalar()
        if existing:
            return

        connection.execute(
            text(
                "INSERT INTO teachers (id, name, email, password_hash, is_admin, is_seed, created_at) "
                "VALUES (:id, :name, :email, :password_hash, :is_admin, :is_seed, NOW())"
            ),
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "name": SEED_ADMIN_NAME,
                "email": SEED_ADMIN_EMAIL,
                "password_hash": hash_password(SEED_ADMIN_PASSWORD),
                "is_admin": True,
                "is_seed": True,
            },
        )


def main() -> None:
    if not SQLITE_DB.exists():
        raise SystemExit(f"SQLite seed database not found: {SQLITE_DB}")

    sqlite_conn = sqlite3.connect(SQLITE_DB)
    postgres_engine = create_engine(POSTGRES_URL)

    print(f"Importing seed DB from {SQLITE_DB}")
    truncate_postgres(postgres_engine)

    for table in TABLES_IN_INSERT_ORDER:
        rows = load_sqlite_rows(sqlite_conn, table)
        insert_rows(postgres_engine, table, rows)
        print(f"Imported {len(rows):>4} rows into {table}")

    ensure_seed_admin(postgres_engine)
    print(f"Ensured protected seed admin account exists: {SEED_ADMIN_EMAIL}")
    reset_audit_sequence(postgres_engine)
    print("Reset audit_events sequence")

    sqlite_conn.close()
    print("Import complete")


if __name__ == "__main__":
    main()