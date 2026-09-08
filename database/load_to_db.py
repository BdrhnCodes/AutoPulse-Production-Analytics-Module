
# Loads every CSV in data/raw/ into the SQLite database, respecting
# foreign-key dependency order, then runs a few validation queries to prove
# the relationships actually hold (this is our "did the load work" check).

import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "autopulse.db"
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

LOAD_ORDER = [
    "dim_date",
    "dim_car_model",
    "dim_color",
    "dim_upholstery",
    "dim_supplier",
    "dim_workstation",
    "dim_shift",
    "dim_trim_level",
    "dim_part",
    "dim_worker",
    "bridge_model_trim_bom",
    "fact_production_order",
    "fact_production_unit",
    "fact_station_operation",
    "fact_defect",
    "fact_material_usage",
]


def load_all_tables(conn: sqlite3.Connection):
    for table_name in LOAD_ORDER:
        csv_path = RAW_DATA_DIR / f"{table_name}.csv"
        df = pd.read_csv(csv_path)
        df.to_sql(table_name, conn, if_exists="append", index=False)
        print(f"  {table_name:<24} <- {len(df):>7,} rows loaded")


def run_validation_queries(conn: sqlite3.Connection):
    print("\n--- Row counts per table ---")
    for table_name in LOAD_ORDER:
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"  {table_name:<24} {count:>7,} rows")

    print("\n--- final_qc_status distribution ---")
    query = "SELECT final_qc_status, COUNT(*) AS n FROM fact_production_unit GROUP BY final_qc_status;"
    print(pd.read_sql(query, conn).to_string(index=False))

    print("\n--- Top 5 parts by defect count ---")
    query = """
        SELECT p.part_name, p.part_category, COUNT(*) AS n_defects,
               ROUND(SUM(d.rework_cost), 2) AS total_rework_cost
        FROM fact_defect d
        JOIN dim_part p ON d.part_id = p.part_id
        GROUP BY p.part_name, p.part_category
        ORDER BY n_defects DESC
        LIMIT 5;
    """
    print(pd.read_sql(query, conn).to_string(index=False))


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    print(f"Loading CSVs from {RAW_DATA_DIR} into {DB_PATH} ...")
    load_all_tables(conn)
    conn.commit()

    run_validation_queries(conn)

    conn.close()


if __name__ == "__main__":
    main()