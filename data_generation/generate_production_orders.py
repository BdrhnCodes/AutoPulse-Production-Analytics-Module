import pandas as pd
from common import get_output_dir,save_df,load_config,set_global_seed
import numpy as np

SEASONAL_FACTOR_BY_MONTH = {
    1: 0.95, 2: 0.95, 3: 1.10, 4: 1.10, 5: 1.10,
    6: 1.00, 7: 0.80, 8: 0.80, 9: 1.05, 10: 1.10,
    11: 1.05, 12: 0.90,
}

PRIORITY_LEVELS = ["Low", "Medium", "High"]
PRIORITY_WEIGHTS = [0.20, 0.60, 0.20]

TRIM_WEIGHTS = {"Base": 0.55, "Comfort": 0.32, "Luxury": 0.13}

def compute_model_weights(model_names: list, day_fraction: float) -> np.ndarray:
    base_popularity = {
        "Jungle Fennec": 0.38,
        "Jungle Lynx": 0.28,
        "Jungle Tiger": 0.24,
        "Jungle Owl": 0.10,
    }
    ev_start_share, ev_end_share = 0.10, 0.30
    ev_share_now = ev_start_share + (ev_end_share - ev_start_share) * day_fraction

    remaining_share = 1 - ev_share_now
    non_ev_models = [m for m in model_names if m != "Jungle Owl"]
    non_ev_base_total = sum(base_popularity[m] for m in non_ev_models)

    weights = []
    for m in model_names:
        if m == "Jungle Owl":
            weights.append(ev_share_now)
        else:
            weights.append(remaining_share * (base_popularity[m] / non_ev_base_total))
    return np.array(weights)

def generate_orders(config: dict, dim_car_model: pd.DataFrame, dim_trim_level: pd.DataFrame,
                     dim_color: pd.DataFrame, dim_upholstery: pd.DataFrame,
                     dim_date: pd.DataFrame) -> pd.DataFrame:
    daily_mean = config["production"]["daily_target_mean"]
    daily_std = config["production"]["daily_target_std"]
    weekend_factor = config["production"]["weekend_reduction_factor"]

    model_names = dim_car_model["model_name"].tolist()
    model_id_by_name = dict(zip(dim_car_model["model_name"], dim_car_model["model_id"]))

    color_ids = dim_color["color_id"].values
    upholstery_ids = dim_upholstery["upholstery_id"].values

    total_days = len(dim_date)
    order_rows = []
    order_id = 1

    for i, date_row in enumerate(dim_date.itertuples()):
        day_fraction = i / max(total_days - 1, 1)
        seasonal = SEASONAL_FACTOR_BY_MONTH[date_row.month]
        weekend_mult = weekend_factor if date_row.is_weekend else 1.0

        target_units = max(0, np.random.normal(daily_mean, daily_std)) * seasonal * weekend_mult
        remaining = int(round(target_units))

        if remaining == 0:
            continue

        model_weights = compute_model_weights(model_names, day_fraction)

        while remaining > 0:
            qty = min(remaining, np.random.randint(1, 5))
            model_name = np.random.choice(model_names, p=model_weights)
            model_id = model_id_by_name[model_name]

            trims_for_model = dim_trim_level[dim_trim_level["model_id"] == model_id]
            trim_p = np.array([TRIM_WEIGHTS[t] for t in trims_for_model["trim_name"]])
            trim_p = trim_p / trim_p.sum()
            trim_id = np.random.choice(trims_for_model["trim_id"].values, p=trim_p)

            color_id = np.random.choice(color_ids)
            upholstery_id = np.random.choice(upholstery_ids)
            priority = np.random.choice(PRIORITY_LEVELS, p=PRIORITY_WEIGHTS)

            order_rows.append({
                "order_id": order_id,
                "model_id": model_id,
                "trim_id": int(trim_id),
                "color_id": int(color_id),
                "upholstery_id": int(upholstery_id),
                "order_date_id": date_row.date_id,
                "planned_quantity": qty,
                "priority_level": priority,
            })
            order_id += 1
            remaining -= qty

    return pd.DataFrame(order_rows)

def main():
    config = load_config()
    set_global_seed(config["project"]["random_seed"])
    out_dir = get_output_dir(config)

    dim_car_model = pd.read_csv(out_dir / "dim_car_model.csv")
    dim_trim_level = pd.read_csv(out_dir / "dim_trim_level.csv")
    dim_color = pd.read_csv(out_dir / "dim_color.csv")
    dim_upholstery = pd.read_csv(out_dir / "dim_upholstery.csv")
    dim_date = pd.read_csv(out_dir / "dim_date.csv")

    orders = generate_orders(config, dim_car_model, dim_trim_level, dim_color, dim_upholstery, dim_date)

    path = save_df(orders, "fact_production_order", config)
    print(f"  fact_production_order -> {len(orders):>7} rows -> {path}")
    print(f"  Total planned units   -> {orders['planned_quantity'].sum():>7}")

    return orders


if __name__ == "__main__":
    main()
