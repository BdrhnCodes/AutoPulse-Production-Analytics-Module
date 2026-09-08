"""
Exports the 5 reporting views and key analysis outputs into
data/powerbi_export/ as flat CSVs -- the folder Power BI connects to.
"""

import shutil
from pathlib import Path

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))
from db_utils import get_connection, query

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = PROJECT_ROOT / "data" / "powerbi_export"
ANALYSIS_OUTPUT_DIR = PROJECT_ROOT / "data" / "analysis_output"

VIEWS_TO_EXPORT = [
    "vw_unit_summary",
    "vw_station_performance",
    "vw_defect_pareto",
    "vw_cost_breakdown",
    "vw_oee_daily",
]

ANALYSIS_FILES_TO_COPY = [
    "labor_time_station_summary.csv",
    "cost_by_model_trim.csv",
    "cost_monthly_trend.csv",
    "defect_pareto_by_part.csv",
    "defect_trend_monthly.csv",
    "oee_line_monthly.csv",
    "defect_feature_importance.csv",
    "high_risk_combinations.csv",
]


def export_views(conn):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    for view_name in VIEWS_TO_EXPORT:
        df = query(f"SELECT * FROM {view_name}", conn)
        path = EXPORT_DIR / f"{view_name}.csv"
        df.to_csv(path, index=False)
        print(f"  {view_name:<26} -> {len(df):>8,} rows -> {path.name}")


def copy_analysis_outputs():
    for filename in ANALYSIS_FILES_TO_COPY:
        src = ANALYSIS_OUTPUT_DIR / filename
        if not src.exists():
            print(f"  [skip] {filename} not found -- run the corresponding analysis script first")
            continue
        dst = EXPORT_DIR / filename
        shutil.copy(src, dst)
        n_rows = len(pd.read_csv(dst))
        print(f"  {filename:<34} -> {n_rows:>8,} rows -> copied")


def main():
    conn = get_connection()

    print("Exporting reporting views ...")
    export_views(conn)

    print("\nCopying analysis outputs ...")
    copy_analysis_outputs()

    conn.close()

    print(f"\nAll Power BI-ready files are in: {EXPORT_DIR}")


if __name__ == "__main__":
    main()