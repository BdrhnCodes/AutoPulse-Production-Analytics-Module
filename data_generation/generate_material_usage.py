# The material costs do not stay the same over two years. In this file, inflation mechanics are added to have more realistic data.
import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime

from common import load_config , set_global_seed , save_df, get_output_dir

def generate_material_usage(units: pd.DataFrame, bom: pd.DataFrame, dim_part: pd.DataFrame,
                             dim_date: pd.DataFrame, config: dict) -> pd.DataFrame:
    cfg = config["material_usage"]

    print("  Merging units with BOM (model_id, trim_id) ...")
    usage = units[["unit_id", "model_id", "trim_id", "production_start_date_id"]].merge(
        bom[["model_id", "trim_id", "part_id", "quantity_required"]],
        on=["model_id", "trim_id"], how="left",
    )
    print(f"    -> {len(usage):,} material usage rows")

    usage = usage.merge(
        dim_part[["part_id", "unit_cost", "primary_supplier_id"]],
        on="part_id", how="left",
    )
    usage = usage.rename(columns={"unit_cost": "base_unit_cost", "primary_supplier_id": "supplier_id"})

    print("  Applying time-based inflation + noise ...")
    date_lookup = dim_date.set_index("date_id")["full_date"]
    start_date = pd.to_datetime(dim_date["full_date"].min())
    unit_dates = pd.to_datetime(usage["production_start_date_id"].map(date_lookup))
    days_elapsed = (unit_dates - start_date).dt.days
    total_days = (pd.to_datetime(dim_date["full_date"].max()) - start_date).days

    inflation_factor = 1 + cfg["annual_inflation_rate"] * (days_elapsed / 365.0)
    noise = np.random.normal(loc=1.0, scale=cfg["cost_noise_std"], size=len(usage))

    usage["unit_cost_at_time"] = np.round(usage["base_unit_cost"] * inflation_factor.values * noise, 2)
    usage["quantity_used"] = usage["quantity_required"]
    usage["total_cost"] = np.round(usage["unit_cost_at_time"] * usage["quantity_used"], 2)

    usage.insert(0, "usage_id", range(1, len(usage) + 1))

    final_cols = ["usage_id", "unit_id", "part_id", "supplier_id",
                  "quantity_used", "unit_cost_at_time", "total_cost"]
    return usage[final_cols]

# The function for calculating the cost of each part at the time that vehicle was manufactured.

def main():
    config = load_config()
    set_global_seed(config["project"]["random_seed"])
    out_dir = get_output_dir(config)

    print("Loading inputs ...")
    units = pd.read_csv(out_dir / "fact_production_unit.csv")
    bom = pd.read_csv(out_dir / "bridge_model_trim_bom.csv")
    dim_part = pd.read_csv(out_dir / "dim_part.csv")
    dim_date = pd.read_csv(out_dir / "dim_date.csv")

    print("Generating fact_material_usage ...")
    usage = generate_material_usage(units, bom, dim_part, dim_date, config)

    path = save_df(usage, "fact_material_usage", config)
    print(f"  fact_material_usage -> {len(usage):,} rows -> {path}")
    print(f"  Total material spend -> ${usage['total_cost'].sum():,.2f}")

    return usage


if __name__ == "__main__":
    main()