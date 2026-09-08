import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime

from common import load_config , set_global_seed , save_df, get_output_dir

def assign_workers_per_station(cross: pd.DataFrame, dim_worker: pd.DataFrame,
                                dim_workstation: pd.DataFrame) -> pd.DataFrame:
    cross = cross.copy()
    cross["worker_id"] = -1

    for station_id in dim_workstation["station_id"]:
        mask = cross["station_id"] == station_id
        n = mask.sum()
        if n == 0:
            continue

        pool = dim_worker.loc[dim_worker["default_station_id"] == station_id, "worker_id"].values
        if len(pool) == 0:
            print(f"  [warning] station {station_id} had no dedicated workers -- using full workforce")
            pool = dim_worker["worker_id"].values

        cross.loc[mask, "worker_id"] = np.random.choice(pool, size=n)

    return cross

def simulate_cycle_times(cross: pd.DataFrame, dim_worker: pd.DataFrame, config: dict) -> pd.DataFrame:
    cfg = config["station_operations"]
    cross = cross.merge(dim_worker[["worker_id", "skill_level"]], on="worker_id", how="left")

    factor_cfg = cfg["cycle_time_factor_by_skill"]
    means = cross["skill_level"].map(lambda s: factor_cfg[s]["mean"]).astype(float)
    stds = cross["skill_level"].map(lambda s: factor_cfg[s]["std"]).astype(float)

    n = len(cross)
    factors = np.random.normal(loc=means.values, scale=stds.values, size=n)
    factors = np.clip(factors, 0.5, 2.5)

    cross["actual_cycle_time_minutes"] = np.round(cross["standard_cycle_time_minutes"].values * factors, 2)
    return cross

def compute_color_changeover(cross: pd.DataFrame) -> pd.DataFrame:
    cross = cross.sort_values(["station_id", "unit_id"]).reset_index(drop=True)
    cross["prev_color_id"] = cross.groupby("station_id")["color_id"].shift(1)
    cross["color_changed"] = (cross["color_id"] != cross["prev_color_id"]) & cross["prev_color_id"].notna()
    return cross

def simulate_downtime(cross: pd.DataFrame, config: dict, dim_shift: pd.DataFrame) -> pd.DataFrame:
    cfg = config["station_operations"]
    co_cfg = cfg["changeover"]
    cross = cross.merge(dim_shift[["shift_id", "shift_name"]], on="shift_id", how="left")

    is_painting = (cross["station_type"] == "Painting").values

    base_p = cfg["downtime_probability_base"]
    skill_mult = cross["skill_level"].map(cfg["downtime_multiplier_by_skill"]).astype(float).values
    shift_mult = cross["shift_name"].map(cfg["downtime_multiplier_by_shift"]).astype(float).values
    general_p = np.clip(base_p * skill_mult * shift_mult, 0, 0.9)

    painting_p = np.where(cross["color_changed"].values,
                           co_cfg["color_change_downtime_probability"],
                           co_cfg["same_color_downtime_probability"])

    final_p = np.where(is_painting, painting_p, general_p)

    n = len(cross)
    downtime_occurred = np.random.random(n) < final_p

    general_lo, general_hi = cfg["downtime_minutes_range"]
    co_lo, co_hi = co_cfg["changeover_minutes_range"]

    general_mask = downtime_occurred & ~is_painting
    painting_mask = downtime_occurred & is_painting

    downtime_minutes = np.zeros(n)
    downtime_minutes[general_mask] = np.round(np.random.uniform(general_lo, general_hi, size=general_mask.sum()), 1)
    downtime_minutes[painting_mask] = np.round(np.random.uniform(co_lo, co_hi, size=painting_mask.sum()), 1)

    reasons = list(cfg["downtime_reason_weights"].keys())
    reason_p = np.array(list(cfg["downtime_reason_weights"].values()))
    reason_p = reason_p / reason_p.sum()
    general_reason = np.random.choice(reasons, size=n, p=reason_p)

    downtime_reason = np.where(painting_mask, "Changeover",
                                np.where(general_mask, general_reason, None))

    cross["downtime_minutes"] = downtime_minutes
    cross["downtime_reason"] = downtime_reason
    return cross

def generate_station_operations(units: pd.DataFrame, dim_workstation: pd.DataFrame,
                                 dim_worker: pd.DataFrame, dim_shift: pd.DataFrame,
                                 config: dict) -> pd.DataFrame:
    print("  Cross-joining units x workstations ...")
    unit_cols = units[["unit_id", "production_start_date_id", "shift_id", "color_id"]].copy()
    station_cols = dim_workstation[["station_id", "station_sequence_order",
                                     "station_type", "standard_cycle_time_minutes"]].copy()

    cross = unit_cols.merge(station_cols, how="cross")
    print(f"    -> {len(cross):,} operation rows")

    print("  Computing color changeover (Painting stations) ...")
    cross = compute_color_changeover(cross)

    print("  Assigning workers per station ...")
    cross = assign_workers_per_station(cross, dim_worker, dim_workstation)

    print("  Simulating actual cycle times ...")
    cross = simulate_cycle_times(cross, dim_worker, config)

    print("  Simulating downtime events (incl. color changeover) ...")
    cross = simulate_downtime(cross, config, dim_shift)

    cross = cross.sort_values(["unit_id", "station_sequence_order"]).reset_index(drop=True)
    cross.insert(0, "operation_id", range(1, len(cross) + 1))

    cross = cross.rename(columns={"production_start_date_id": "date_id"})

    final_cols = [
        "operation_id", "unit_id", "station_id", "worker_id", "shift_id", "date_id",
        "actual_cycle_time_minutes", "standard_cycle_time_minutes",
        "downtime_minutes", "downtime_reason",
    ]
    return cross[final_cols]

def main():
    config = load_config()
    set_global_seed(config["project"]["random_seed"])
    out_dir = get_output_dir(config)

    print("Loading inputs ...")
    units = pd.read_csv(out_dir / "fact_production_unit.csv")
    dim_workstation = pd.read_csv(out_dir / "dim_workstation.csv")
    dim_worker = pd.read_csv(out_dir / "dim_worker.csv")
    dim_shift = pd.read_csv(out_dir / "dim_shift.csv")

    print("Generating fact_station_operation ...")
    station_ops = generate_station_operations(units, dim_workstation, dim_worker, dim_shift, config)

    path = save_df(station_ops, "fact_station_operation", config)
    print(f"  fact_station_operation -> {len(station_ops):,} rows -> {path}")
    print(f"  Downtime events        -> {(station_ops['downtime_minutes'] > 0).sum():,} "
          f"({(station_ops['downtime_minutes'] > 0).mean()*100:.1f}%)")

    return station_ops


if __name__ == "__main__":
    main()