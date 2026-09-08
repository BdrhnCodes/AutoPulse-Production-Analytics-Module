"""
Builds the Bill of Materials (bridge_model_trim_bom): a core set of parts
shared by every trim of a model, plus cumulative extras added by Comfort
and Luxury trims. EV models skip the Engine category and get extra
Powertrain parts instead.
"""

import pandas as pd
from common import get_output_dir,save_df,load_config,set_global_seed

CORE_CATEGORY_COUNTS = {
    "Chassis": 3,
    "Electrical": 2,
    "Interior": 2,
    "Exterior": 3,
    "Safety": 2,
    "Powertrain": 2,
    "Engine": 1,
    
}

TRIM_ADDITIONS = {
    "Base": {},
    "Comfort": {"Interior": 1, "Electrical": 1},
    "Luxury": {"Interior": 2, "Safety": 1, "Exterior": 1},
}

def build_core_bom_for_model(model_row, dim_part: pd.DataFrame) -> pd.DataFrame:
    is_ev = model_row["engine_type"] == "Electric"

    rows = []
    for category, qty_distinct in CORE_CATEGORY_COUNTS.items():
        if category == "Engine" and is_ev:
            continue

        category_parts = dim_part[dim_part["part_category"] == category]

        n_pick = qty_distinct + 2 if (category == "Powertrain" and is_ev) else qty_distinct
        n_pick = min(n_pick, len(category_parts))

        chosen = category_parts.sample(n=n_pick, random_state=model_row["model_id"])
        for _, part in chosen.iterrows():
            rows.append({"part_id": part["part_id"], "quantity_required": 1})

    return pd.DataFrame(rows)

def build_trim_additions(model_row, trim_name: str, core_part_ids: set,
                          dim_part: pd.DataFrame) -> pd.DataFrame:
    additions = TRIM_ADDITIONS[trim_name]
    rows = []
    seed_offset = {"Base": 0, "Comfort": 1, "Luxury": 2}[trim_name]

    for category, n_extra in additions.items():
        category_parts = dim_part[
            (dim_part["part_category"] == category)
            & (~dim_part["part_id"].isin(core_part_ids))
        ]
        n_pick = min(n_extra, len(category_parts))
        if n_pick == 0:
            continue
        chosen = category_parts.sample(n=n_pick, random_state=model_row["model_id"] * 10 + seed_offset)
        for _, part in chosen.iterrows():
            rows.append({"part_id": part["part_id"], "quantity_required": 1})

    return pd.DataFrame(rows)

def generate_bom(dim_car_model: pd.DataFrame, dim_trim_level: pd.DataFrame,
                  dim_part: pd.DataFrame) -> pd.DataFrame:
    bom_rows = []
    bom_id = 1

    for _, model in dim_car_model.iterrows():
        core_bom = build_core_bom_for_model(model, dim_part)
        core_part_ids = set(core_bom["part_id"])

        model_trims = dim_trim_level[dim_trim_level["model_id"] == model["model_id"]]

        cumulative_extra_ids = set()

        for _, trim in model_trims.sort_values("trim_id").iterrows():
            trim_name = trim["trim_name"]

            extras = build_trim_additions(model, trim_name, core_part_ids | cumulative_extra_ids, dim_part)
            cumulative_extra_ids |= set(extras["part_id"]) if not extras.empty else set()

            full_part_ids = core_part_ids | cumulative_extra_ids

            for part_id in full_part_ids:
                bom_rows.append({
                    "bom_id": bom_id,
                    "model_id": model["model_id"],
                    "trim_id": trim["trim_id"],
                    "part_id": part_id,
                    "quantity_required": 1,
                })
                bom_id += 1

    return pd.DataFrame(bom_rows)

def main():
    config = load_config()
    set_global_seed(config["project"]["random_seed"])
    out_dir = get_output_dir(config)

    dim_car_model = pd.read_csv(out_dir / "dim_car_model.csv")
    dim_trim_level = pd.read_csv(out_dir / "dim_trim_level.csv")
    dim_part = pd.read_csv(out_dir / "dim_part.csv")

    bom = generate_bom(dim_car_model, dim_trim_level, dim_part)

    path = save_df(bom, "bridge_model_trim_bom", config)
    print(f"  bridge_model_trim_bom -> {len(bom):>5} rows -> {path}")

    return bom


if __name__ == "__main__":
    main()