"""
Generates all 10 dimension tables (dim_date, dim_car_model, dim_trim_level,
dim_color, dim_upholstery, dim_supplier, dim_part, dim_workstation,
dim_worker, dim_shift) from config.yaml. Workstation cycle times are
built around a calculated takt time, not pure random.
"""


import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime

from common import load_config , set_global_seed , save_df

fake = Faker()

def generate_dim_car_model(config: dict) -> pd.DataFrame:
    rows = []
    for i, m in enumerate(config["models"]["definitions"], start=1):
        row = {"model_id" : i ,**m}
        rows.append(row)
    return pd.DataFrame(rows)


def generate_dim_trim_level(config: dict, dim_car_model: pd.DataFrame) -> pd.DataFrame:
    trim_names = config["trims"]["levels"]
    multipliers = config["trims"]["price_premium_multiplier"]
    rows=[]
    trim_id=1
    for _ , model in dim_car_model.iterrows():
        for trim_name, mult in zip(trim_names,multipliers):
            rows.append({
                "trim_id":trim_id ,
                "model_id": model["model_id"],
                "trim_name": trim_name,
                "price_premium": round(model["base_price"]*mult, 2),
            })
            trim_id +=1
    return pd.DataFrame(rows)


def generate_dim_date(config: dict) -> pd.DataFrame:
    start = pd.to_datetime(config["date_range"]["start_date"])
    end = pd.to_datetime(config["date_range"]["end_date"])
    dates = pd.date_range(start, end, freq="D")

    df = pd.DataFrame({"full_date": dates})
    df["date_id"] = df["full_date"].dt.strftime("%Y%m%d").astype(int)
    df["year"] = df["full_date"].dt.year
    df["quarter"] = df["full_date"].dt.quarter
    df["month"] = df["full_date"].dt.month
    df["month_name"] = df["full_date"].dt.strftime("%B")
    df["week"] = df["full_date"].dt.isocalendar().week.astype(int)
    df["day_of_week"] = df["full_date"].dt.strftime("%A")
    df["is_weekend"] = df["full_date"].dt.dayofweek.isin([5, 6])

    colum_names = ["date_id", "full_date", "year", "quarter", "month",
            "month_name", "week", "day_of_week", "is_weekend"]
    return df[colum_names]


def generate_dim_color(config: dict) -> pd.DataFrame:
    rows = []
    for i, c in enumerate(config["colors"]["definitions"], start=1):
        rows.append({"color_id": i, **c})
    return pd.DataFrame(rows)


def generate_dim_upholstery(config: dict) -> pd.DataFrame:
    rows = []
    for i, u in enumerate(config["upholstery"]["definitions"], start=1):
        rows.append({"upholstery_id": i, **u})
    return pd.DataFrame(rows)


def generate_dim_shift(config: dict) -> pd.DataFrame:
    rows = []
    for i, s in enumerate(config["shifts"]["definitions"], start=1):
        rows.append({"shift_id": i, **s})
    return pd.DataFrame(rows)

def generate_dim_supplier(config: dict) -> pd.DataFrame:
    n = config["suppliers"]["count"]
    rel_lo, rel_hi = config["suppliers"]["reliability_score_range"]
    lead_lo, lead_hi = config["suppliers"]["lead_time_days_range"]

    rows = []
    for i in range(1, n + 1):
        rows.append({
            "supplier_id": i,
            "supplier_name": fake.unique.company(),
            "country": fake.country(),
            "reliability_score": round(np.clip(np.random.normal(loc=82, scale=12), rel_lo, rel_hi), 1),
            "avg_lead_time_days": int(np.random.randint(lead_lo, lead_hi + 1)),
            "contract_start_date": fake.date_between(start_date="-8y", end_date="-1y"),
        })
    return pd.DataFrame(rows)

def generate_dim_part(config: dict, dim_supplier: pd.DataFrame) -> pd.DataFrame:
    n = config["parts"]["count"]
    categories = config["parts"]["categories"]
    cost_ranges = config["parts"]["unit_cost_range_by_category"]
    comp_lo, comp_hi = config["parts"]["complexity_score_range"]

    name_pools = {
        "Engine": ["Engine Block", "Piston Set", "Cylinder Head", "Crankshaft", "Camshaft", "Turbocharger"],
        "Chassis": ["Front Subframe", "Rear Subframe", "Suspension Arm", "Shock Absorber", "Brake Caliper", "Wheel Hub"],
        "Electrical": ["Wiring Harness", "ECU Module", "Alternator", "Battery Pack", "Sensor Array", "Fuse Box"],
        "Interior": ["Dashboard Panel", "Seat Frame", "Door Trim", "Center Console", "Headliner", "Carpet Set"],
        "Exterior": ["Front Bumper", "Rear Bumper", "Side Mirror", "Door Handle", "Roof Rail", "Grille"],
        "Powertrain": ["Transmission Unit", "Drive Shaft", "Differential", "Electric Motor", "Battery Module", "Inverter"],
        "Safety": ["Airbag Module", "Seatbelt Assembly", "ABS Unit", "Crash Sensor", "Backup Camera", "Parking Sensor"],
    }

    rows = []
    for i in range(1, n + 1):
        category = categories[(i - 1) % len(categories)]
        pool = name_pools[category]
        base_name = pool[(i - 1) % len(pool)]
        variant = (i - 1) // len(pool)
        part_name = base_name if variant == 0 else f"{base_name} v{variant + 1}"

        cost_lo, cost_hi = cost_ranges[category]
        supplier_id = int(np.random.choice(dim_supplier["supplier_id"]))

        rows.append({
            "part_id": i,
            "part_name": part_name,
            "part_category": category,
            "primary_supplier_id": supplier_id,
            "unit_cost": round(np.random.uniform(cost_lo, cost_hi), 2),
            "complexity_score": int(np.random.randint(comp_lo, comp_hi + 1)),
        })
    return pd.DataFrame(rows)

SHIFT_MINUTES = 480  
def generate_dim_workstation(config: dict) -> pd.DataFrame:
    type_sequence = config["workstations"]["type_sequence"]

    n_shifts = len(config["shifts"]["definitions"])
    daily_target = config["production"]["daily_target_mean"]
    takt_time = (n_shifts * SHIFT_MINUTES) / daily_target

    std_dev = config["workstations"]["cycle_time_balance_std_minutes"]
    min_cycle = config["workstations"]["min_cycle_time_minutes"]

    rows = []
    for i, station_type in enumerate(type_sequence, start=1):
        std_cycle = max(min_cycle, round(np.random.normal(loc=takt_time, scale=std_dev), 1))
        max_capacity = int((8 * 60) // std_cycle)
        rows.append({
            "station_id": i,
            "station_name": f"{station_type} - Station {i:02d}",
            "station_sequence_order": i,
            "station_type": station_type,
            "standard_cycle_time_minutes": std_cycle,
            "max_capacity_per_shift": max_capacity,
        })
    return pd.DataFrame(rows)

def generate_dim_worker(config: dict, dim_workstation: pd.DataFrame) -> pd.DataFrame:
    n = config["workers"]["count"]
    skill_levels = config["workers"]["skill_levels"]
    weights = config["workers"]["skill_level_weights"]
    wage_ranges = config["workers"]["hourly_wage_range"]
    hire_lo = config["workers"]["hire_date_range"][0]
    hire_hi = config["workers"]["hire_date_range"][1]

    rows = []
    for i in range(1, n + 1):
        skill = np.random.choice(skill_levels, p=weights)
        wage_lo, wage_hi = wage_ranges[skill]
        rows.append({
            "worker_id": i,
            "worker_name": fake.name(),
            "skill_level": skill,
            "hire_date": fake.date_between(start_date=datetime.strptime(hire_lo, "%Y-%m-%d"),
                                            end_date=datetime.strptime(hire_hi, "%Y-%m-%d")),
            "default_station_id": int(np.random.choice(dim_workstation["station_id"])),
            "hourly_wage": round(np.random.uniform(wage_lo, wage_hi), 2),
        })
    return pd.DataFrame(rows)

def main():
    config = load_config()
    set_global_seed(config["project"]["random_seed"])

    dim_date = generate_dim_date(config)
    dim_car_model = generate_dim_car_model(config)
    dim_trim_level = generate_dim_trim_level(config, dim_car_model)
    dim_color = generate_dim_color(config)
    dim_upholstery = generate_dim_upholstery(config)
    dim_supplier = generate_dim_supplier(config)
    dim_part = generate_dim_part(config, dim_supplier)
    dim_workstation = generate_dim_workstation(config)
    dim_worker = generate_dim_worker(config, dim_workstation)
    dim_shift = generate_dim_shift(config)

    tables = {
        "dim_date": dim_date,
        "dim_car_model": dim_car_model,
        "dim_trim_level": dim_trim_level,
        "dim_color": dim_color,
        "dim_upholstery": dim_upholstery,
        "dim_supplier": dim_supplier,
        "dim_part": dim_part,
        "dim_workstation": dim_workstation,
        "dim_worker": dim_worker,
        "dim_shift": dim_shift,
    }

    for name, df in tables.items():
        path = save_df(df, name, config)
        print(f"  {name:<20} -> {len(df):>5} rows -> {path}")

    return tables


if __name__ == "__main__":
    main()