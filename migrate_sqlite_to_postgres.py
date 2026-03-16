"""
One-time migration script: copies all data from the local SQLite database
into a PostgreSQL database.

Usage:
    1. Set DATABASE_URL in your .env to the PostgreSQL connection string.
    2. Run: python migrate_sqlite_to_postgres.py

The script reads from studio_manager.db (SQLite) and writes to the
PostgreSQL database defined by DATABASE_URL.
"""

import sqlite3
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import text

SQLITE_PATH = Path(__file__).parent / "studio_manager.db"

TABLES_IN_ORDER = [
    "users",
    "clients",
    "leads",
    "lead_activities",
    "lead_stage_history",
    "projects",
    "stage_logs",
    "client_activities",
    "project_activities",
    "design_revisions",
    "project_brief_files",
    "design_files",
    "design_file_feedback",
    "production_files",
    "tasks",
    "quotations",
    "quote_items",
    "quote_sundries",
    "social_posts",
    "system_logs",
]


def get_postgres_url() -> str:
    from app.config import settings
    url = settings.DATABASE_URL
    if "sqlite" in url:
        print("ERROR: DATABASE_URL still points to SQLite.")
        print("Set DATABASE_URL to your PostgreSQL URL in .env before running this script.")
        sys.exit(1)
    return url


def migrate():
    if not SQLITE_PATH.exists():
        print(f"ERROR: SQLite database not found at {SQLITE_PATH}")
        sys.exit(1)

    pg_url = get_postgres_url()
    pg_engine = sa.create_engine(pg_url)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    print(f"Source:      {SQLITE_PATH}")
    print(f"Destination: {pg_url}\n")

    with pg_engine.begin() as pg_conn:
        # Disable FK checks during bulk insert
        pg_conn.execute(text("SET session_replication_role = 'replica';"))

        for table in TABLES_IN_ORDER:
            rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608
            if not rows:
                print(f"  {table}: 0 rows (skipped)")
                continue

            sqlite_columns = set(rows[0].keys())

            # Fetch columns that actually exist in PostgreSQL
            pg_col_rows = pg_conn.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = :t"
            ), {"t": table}).fetchall()
            pg_columns = {r[0] for r in pg_col_rows}
            bool_cols = {r[0] for r in pg_col_rows if r[1] == "boolean"}

            # Only insert columns present in both SQLite and PostgreSQL
            columns = [c for c in sqlite_columns if c in pg_columns]

            col_list = ", ".join(f'"{c}"' for c in columns)
            placeholders = ", ".join(f":{c}" for c in columns)
            insert_sql = text(f'INSERT INTO {table} ({col_list}) VALUES ({placeholders})')  # noqa: S608

            data = []
            for row in rows:
                r = {c: dict(row)[c] for c in columns}
                for col in bool_cols:
                    if col in r and r[col] is not None:
                        r[col] = bool(r[col])
                data.append(r)
            pg_conn.execute(insert_sql, data)
            print(f"  {table}: {len(data)} rows migrated")

            # Reset the sequence so new inserts don't collide with existing IDs
            if "id" in columns:
                pg_conn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"(SELECT MAX(id) FROM {table}));"
                ))

        # Re-enable FK checks
        pg_conn.execute(text("SET session_replication_role = 'origin';"))

    sqlite_conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    migrate()
