import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "autopulse.db"
ANALYSIS_OUTPUT_DIR = PROJECT_ROOT / "data" / "analysis_output"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def query(sql: str, conn: sqlite3.Connection = None) -> pd.DataFrame:
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    df = pd.read_sql(sql, conn)
    if own_conn:
        conn.close()
    return df


def save_analysis_output(df: pd.DataFrame, name: str) -> Path:
    ANALYSIS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = ANALYSIS_OUTPUT_DIR / f"{name}.csv"
    df.to_csv(path, index=False)
    return path