# Creates (or resets) the SQLite database and applies sql/01_schema.sql.

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "autopulse.db"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "01_schema.sql"
VIEWS_PATH = PROJECT_ROOT / "sql" / "02_views_reporting.sql"

def build_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        print(f"Removing existing database at {DB_PATH} ...")
        DB_PATH.unlink()

    print(f"Connecting to {DB_PATH} ...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    print(f"Applying schema from {SCHEMA_PATH} ...")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()

    if VIEWS_PATH.exists():
        print(f"Applying reporting views from {VIEWS_PATH} ...")
        with open(VIEWS_PATH, "r", encoding="utf-8") as f:
            views_sql = f.read()
        conn.executescript(views_sql)
        conn.commit()

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    ).fetchall()
    print(f"\n{len(tables)} tables created:")
    for (name,) in tables:
        print(f"  - {name}")

    conn.close()
    return DB_PATH


if __name__ == "__main__":
    build_database()
