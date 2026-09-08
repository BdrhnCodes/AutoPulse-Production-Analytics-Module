import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime

from common import load_config , set_global_seed , save_df, get_output_dir

def build_station_part_lookup(bom: pd.DataFrame, dim_part: pd.DataFrame,
                               part_tied_categories: dict) -> pd.DataFrame:
    bom_with_part = bom.merge(dim_part, on="part_id", how="left")

    rows = []
    for (model_id, trim_id), group in bom_with_part.groupby(["model_id", "trim_id"]):
        for category in set(part_tied_categories.values()):
            candidates = group[group["part_category"] == category]
            if candidates.empty:
                continue
            chosen = candidates.loc[candidates["unit_cost"].idxmax()]
            rows.append({
                "model_id": model_id,
                "trim_id": trim_id,
                "part_category": category,
                "part_id": chosen["part_id"],
                "part_complexity_score": chosen["complexity_score"],
                "primary_supplier_id": chosen["primary_supplier_id"],
            })
    return pd.DataFrame(rows)
# This function will compare the value of each parts and decide the priority list of them.

def compute_defect_probability(ops: pd.DataFrame, cfg: dict) -> np.ndarray:
    base = cfg["base_rate"]

    skill_mult = ops["skill_level"].map(cfg["skill_multiplier"]).astype(float).values
    shift_mult = ops["shift_name"].map(cfg["shift_multiplier"]).astype(float).values
    downtime_mult = np.where(ops["downtime_minutes"].values > 0, cfg["downtime_multiplier"], 1.0)

    reliability = ops["reliability_score"].values
    complexity = ops["part_complexity_score"].values

    has_part = ~np.isnan(reliability)
    supplier_mult = np.where(has_part, 1 + (100 - np.nan_to_num(reliability)) / 100 * cfg["supplier_reliability_scale"], 1.0)
    complexity_mult = np.where(has_part, 1 + (np.nan_to_num(complexity) - 1) / 9 * cfg["complexity_scale"], 1.0)

    qc_mult = np.where(ops["station_type"].values == "Quality Check", cfg["qc_station_dampener"], 1.0)

    p = base * skill_mult * shift_mult * downtime_mult * supplier_mult * complexity_mult * qc_mult
    return np.clip(p, 0, cfg["max_probability_cap"])
# The function for the calculations and computing the probs.

def assign_severity(defect_type: np.ndarray, complexity: np.ndarray, cfg: dict) -> np.ndarray:
    base_weights = cfg["severity_weights_base"]
    n = len(defect_type)
    severities = np.empty(n, dtype=object)

    for i in range(n):
        w = dict(base_weights)
        comp = complexity[i]
        if not np.isnan(comp):
            shift_amount = (comp - 1) / 9 * 0.25
            w["minor"] = max(0.05, w["minor"] - shift_amount)
            w["major"] += shift_amount * 0.7
            w["critical"] += shift_amount * 0.3
        if defect_type[i] == "functional":
            w["critical"] += 0.05
            w["minor"] = max(0.05, w["minor"] - 0.05)

        total = sum(w.values())
        probs = [w["minor"] / total, w["major"] / total, w["critical"] / total]
        severities[i] = np.random.choice(["minor", "major", "critical"], p=probs)

    return severities
# This function for rating the severities of defects.

def assign_resolution(severity: np.ndarray) -> np.ndarray:
    n = len(severity)
    resolution = np.empty(n, dtype=object)

    weights = {
        "minor":    {"rework": 0.90, "accepted_with_deviation": 0.10, "scrap": 0.00},
        "major":    {"rework": 0.87, "accepted_with_deviation": 0.05, "scrap": 0.08},
        "critical": {"rework": 0.65, "accepted_with_deviation": 0.05, "scrap": 0.30},
    }
    for sev in ["minor", "major", "critical"]:
        mask = severity == sev
        n_sev = mask.sum()
        if n_sev == 0:
            continue
        w = weights[sev]
        resolution[mask] = np.random.choice(list(w.keys()), size=n_sev, p=list(w.values()))
    return resolution
# This function for deciding what the company will do about the defective parts.

def compute_rework_cost(row_df: pd.DataFrame, avg_hourly_wage: float) -> pd.DataFrame:
    n = len(row_df)
    severity_time_range = {"minor": (10, 30), "major": (30, 75), "critical": (60, 150)}

    rework_time = np.zeros(n)
    for sev, (lo, hi) in severity_time_range.items():
        mask = row_df["severity"].values == sev
        rework_time[mask] = np.random.uniform(lo, hi, size=mask.sum())

    part_cost_component = np.nan_to_num(row_df["part_unit_cost"].values) * np.where(
        row_df["resolution"].values == "scrap", 1.0,
        np.where(row_df["resolution"].values == "rework", 0.25, 0.0)
    )
    labor_cost_component = (rework_time / 60) * avg_hourly_wage

    rework_cost = np.round(part_cost_component + labor_cost_component, 2)
    rework_cost = np.where(row_df["resolution"].values == "accepted_with_deviation",
                            np.round(labor_cost_component * 0.2, 2), rework_cost)

    row_df = row_df.copy()
    row_df["rework_time_minutes"] = np.round(rework_time, 1)
    row_df["rework_cost"] = rework_cost
    return row_df
# In this function, the cost of reworkings and scraps are computed.

def generate_defects(config: dict, station_ops: pd.DataFrame, units: pd.DataFrame,
                      dim_worker: pd.DataFrame, dim_shift: pd.DataFrame,
                      dim_workstation: pd.DataFrame, bom: pd.DataFrame,
                      dim_part: pd.DataFrame, dim_supplier: pd.DataFrame) -> pd.DataFrame:
    cfg = config["defects"]
    part_tied_categories = cfg["part_tied_station_categories"]

    print("  Building station->part lookup from BOM ...")
    station_part_lookup = build_station_part_lookup(bom, dim_part, part_tied_categories)

    print("  Joining operations with unit/worker/station context ...")
    ops = station_ops.merge(units[["unit_id", "model_id", "trim_id"]], on="unit_id", how="left")
    ops = ops.merge(dim_worker[["worker_id", "skill_level"]], on="worker_id", how="left")
    ops = ops.merge(dim_shift[["shift_id", "shift_name"]], on="shift_id", how="left")
    ops = ops.merge(dim_workstation[["station_id", "station_type"]], on="station_id", how="left")

    ops["part_category"] = ops["station_type"].map(part_tied_categories)
    ops = ops.merge(station_part_lookup, on=["model_id", "trim_id", "part_category"], how="left")
    ops = ops.merge(dim_supplier[["supplier_id", "reliability_score"]],
                     left_on="primary_supplier_id", right_on="supplier_id", how="left")

    print("  Computing defect probabilities ...")
    p = compute_defect_probability(ops, cfg)
    defect_occurred = np.random.random(len(ops)) < p

    defects = ops.loc[defect_occurred].copy()
    print(f"    -> {len(defects):,} defects out of {len(ops):,} operations "
          f"({len(defects) / len(ops) * 100:.2f}%)")

    print("  Assigning defect type, severity, resolution ...")
    defects["defect_type"] = defects["station_type"].map(cfg["station_type_defect_type"])
    defects["severity"] = assign_severity(defects["defect_type"].values, defects["part_complexity_score"].values, cfg)
    defects["resolution"] = assign_resolution(defects["severity"].values)

    defects = defects.rename(columns={"part_id": "part_id_final", "date_id": "detected_date_id"})
    defects = defects.merge(
        dim_part[["part_id", "unit_cost"]].rename(columns={"part_id": "part_id_final", "unit_cost": "part_unit_cost"}),
        on="part_id_final", how="left",
    )

    avg_hourly_wage = dim_worker["hourly_wage"].mean()
    defects = compute_rework_cost(defects, avg_hourly_wage)

    defects.insert(0, "defect_id", range(1, len(defects) + 1))
    defects = defects.rename(columns={"part_id_final": "part_id"})

    final_cols = [
        "defect_id", "operation_id", "unit_id", "part_id", "station_id",
        "defect_type", "severity", "detected_date_id", "resolution",
        "rework_cost", "rework_time_minutes",
    ]
    return defects[final_cols]
# Thanks to this function, all the necessary parts are merged.

def main():
    config = load_config()
    set_global_seed(config["project"]["random_seed"])
    out_dir = get_output_dir(config)

    print("Loading inputs ...")
    station_ops = pd.read_csv(out_dir / "fact_station_operation.csv")
    units = pd.read_csv(out_dir / "fact_production_unit.csv")
    dim_worker = pd.read_csv(out_dir / "dim_worker.csv")
    dim_shift = pd.read_csv(out_dir / "dim_shift.csv")
    dim_workstation = pd.read_csv(out_dir / "dim_workstation.csv")
    bom = pd.read_csv(out_dir / "bridge_model_trim_bom.csv")
    dim_part = pd.read_csv(out_dir / "dim_part.csv")
    dim_supplier = pd.read_csv(out_dir / "dim_supplier.csv")

    print("Generating fact_defect ...")
    defects = generate_defects(config, station_ops, units, dim_worker, dim_shift,
                                dim_workstation, bom, dim_part, dim_supplier)

    path = save_df(defects, "fact_defect", config)
    print(f"  fact_defect -> {len(defects):,} rows -> {path}")

    return defects


if __name__ == "__main__":
    main()