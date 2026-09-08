"""
Explodes each production order into individual physical units (VIN-style
unit_id) and assigns a shift. Produces the SKELETON of fact_production_unit --
cost/QC columns are filled in later by finalize_production_units.py.
"""

import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime

from common import load_config , set_global_seed , save_df, get_output_dir


SHIFT_WEIGHTS = {"Morning": 0.40, "Evening": 0.35, "Night": 0.25}

def generate_units(orders: pd.DataFrame, dim_shift: pd.DataFrame) -> pd.DataFrame:
    exploded = orders.loc[orders.index.repeat(orders["planned_quantity"])].reset_index(drop=True)

    n_units = len(exploded)
    unit_id = [f"JP-{i:07d}" for i in range(1, n_units + 1)]

    shift_names = dim_shift["shift_name"].tolist()
    shift_id_by_name = dict(zip(dim_shift["shift_name"], dim_shift["shift_id"]))
    weights = np.array([SHIFT_WEIGHTS[s] for s in shift_names])
    weights = weights / weights.sum()
    assigned_shift_names = np.random.choice(shift_names, size=n_units, p=weights)
    assigned_shift_ids = [shift_id_by_name[s] for s in assigned_shift_names]

    units = pd.DataFrame({
        "unit_id": unit_id,
        "order_id": exploded["order_id"].values,
        "model_id": exploded["model_id"].values,
        "trim_id": exploded["trim_id"].values,
        "color_id": exploded["color_id"].values,
        "upholstery_id": exploded["upholstery_id"].values,
        "production_start_date_id": exploded["order_date_id"].values,
        "shift_id": assigned_shift_ids,
        "production_end_date_id": exploded["order_date_id"].values,
        "total_actual_labor_hours": np.nan,
        "total_actual_cycle_time_minutes": np.nan,
        "total_material_cost": np.nan,
        "total_labor_cost": np.nan,
        "total_rework_cost": np.nan,
        "total_cost": np.nan,
        "final_qc_status": None,
    })
    return units

def main():
    config = load_config()
    set_global_seed(config["project"]["random_seed"])
    out_dir = get_output_dir(config)

    orders = pd.read_csv(out_dir / "fact_production_order.csv")
    dim_shift = pd.read_csv(out_dir / "dim_shift.csv")

    units = generate_units(orders, dim_shift)

    path = save_df(units, "fact_production_unit", config)
    print(f"  fact_production_unit -> {len(units):>7} rows -> {path}")

    return units


if __name__ == "__main__":
    main()