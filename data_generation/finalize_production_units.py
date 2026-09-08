# This is the "roll-up" step that was necessary
# !!Requires generate_production_units.py, generate_station_operations.py,
# generate_defects.py and generate_material_usage.py to have all been run.
import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime

from common import load_config , set_global_seed , save_df, get_output_dir

def compute_labor_rollup(station_ops: pd.DataFrame, dim_worker: pd.DataFrame, burden_multiplier: float) -> pd.DataFrame:
    ops = station_ops.merge(dim_worker[["worker_id", "hourly_wage"]], on="worker_id", how="left")
    ops["operation_labor_cost"] = (ops["actual_cycle_time_minutes"] / 60) * ops["hourly_wage"] * burden_multiplier
    ops["elapsed_minutes"] = ops["actual_cycle_time_minutes"] + ops["downtime_minutes"]

    rollup = ops.groupby("unit_id").agg(
        total_actual_labor_hours=("actual_cycle_time_minutes", lambda s: s.sum() / 60),
        total_actual_cycle_time_minutes=("elapsed_minutes", "sum"),
        total_labor_cost=("operation_labor_cost", "sum"),
    ).reset_index()
    return rollup

def compute_material_rollup(material_usage: pd.DataFrame) -> pd.DataFrame:
    return material_usage.groupby("unit_id").agg(
        total_material_cost=("total_cost", "sum")
    ).reset_index()

def compute_qc_rollup(defects: pd.DataFrame) -> pd.DataFrame:
    rework_cost = defects.groupby("unit_id").agg(total_rework_cost=("rework_cost", "sum")).reset_index()

    has_scrap = defects[defects["resolution"] == "scrap"]["unit_id"].unique()
    has_rework = defects[defects["resolution"] == "rework"]["unit_id"].unique()

    status = pd.DataFrame({"unit_id": defects["unit_id"].unique()})
    status["final_qc_status"] = np.where(
        status["unit_id"].isin(has_scrap), "Fail",
        np.where(status["unit_id"].isin(has_rework), "Rework", "Pass")
    )
    return rework_cost.merge(status, on="unit_id", how="outer")

SHIFT_MINUTES = 480 # 8 hours shift

def compute_production_end_date(units: pd.DataFrame, labor_rollup: pd.DataFrame,
                                 dim_date: pd.DataFrame) -> pd.Series:
    sorted_dates = dim_date.sort_values("date_id").reset_index(drop=True)
    date_id_list = sorted_dates["date_id"].values
    index_by_date_id = {d: i for i, d in enumerate(date_id_list)}

    merged = units[["unit_id", "production_start_date_id"]].merge(
        labor_rollup[["unit_id", "total_actual_cycle_time_minutes"]], on="unit_id", how="left"
    )
    spillover_days = np.ceil(
        np.maximum(0, merged["total_actual_cycle_time_minutes"].fillna(0) - SHIFT_MINUTES) / SHIFT_MINUTES
    ).astype(int)

    start_idx = merged["production_start_date_id"].map(index_by_date_id)
    end_idx = np.minimum(start_idx + spillover_days, len(date_id_list) - 1)
    end_date_id = date_id_list[end_idx.values]

    return pd.Series(end_date_id, index=merged.index)

def finalize(units: pd.DataFrame, station_ops: pd.DataFrame, dim_worker: pd.DataFrame,
             defects: pd.DataFrame, material_usage: pd.DataFrame, dim_date: pd.DataFrame,
             config: dict) -> pd.DataFrame:
    burden_multiplier = config["costing"]["labor_burden_multiplier"]
    labor_rollup = compute_labor_rollup(station_ops, dim_worker, burden_multiplier)
    material_rollup = compute_material_rollup(material_usage)
    qc_rollup = compute_qc_rollup(defects)
    end_dates = compute_production_end_date(units, labor_rollup, dim_date)

    base = units.drop(columns=[
        "production_end_date_id", "total_actual_labor_hours", "total_actual_cycle_time_minutes",
        "total_material_cost", "total_labor_cost", "total_rework_cost", "total_cost", "final_qc_status",
    ])

    result = base.merge(labor_rollup, on="unit_id", how="left")
    result = result.merge(material_rollup, on="unit_id", how="left")
    result = result.merge(qc_rollup, on="unit_id", how="left")
    result["production_end_date_id"] = end_dates.values

    result["total_rework_cost"] = result["total_rework_cost"].fillna(0.0)
    result["final_qc_status"] = result["final_qc_status"].fillna("Pass")
    result["total_cost"] = np.round(
        result["total_material_cost"] + result["total_labor_cost"] + result["total_rework_cost"], 2
    )

    final_cols = [
        "unit_id", "order_id", "model_id", "trim_id", "color_id", "upholstery_id",
        "production_start_date_id", "production_end_date_id", "shift_id",
        "total_actual_labor_hours", "total_actual_cycle_time_minutes",
        "total_material_cost", "total_labor_cost", "total_rework_cost", "total_cost",
        "final_qc_status",
    ]
    return result[final_cols]

def main():
    config = load_config()
    set_global_seed(config["project"]["random_seed"])
    out_dir = get_output_dir(config)

    units = pd.read_csv(out_dir / "fact_production_unit.csv")
    station_ops = pd.read_csv(out_dir / "fact_station_operation.csv")
    dim_worker = pd.read_csv(out_dir / "dim_worker.csv")
    defects = pd.read_csv(out_dir / "fact_defect.csv")
    material_usage = pd.read_csv(out_dir / "fact_material_usage.csv")
    dim_date = pd.read_csv(out_dir / "dim_date.csv")

    finalized = finalize(units, station_ops, dim_worker, defects, material_usage, dim_date, config)

    path = save_df(finalized, "fact_production_unit", config)
    print(f"  fact_production_unit (finalized) -> {len(finalized):,} rows -> {path}")
    print()
    print("  final_qc_status breakdown:")
    print(finalized["final_qc_status"].value_counts())
    print()
    print("  total_cost summary:")
    print(finalized["total_cost"].describe())

    return finalized


if __name__ == "__main__":
    main()