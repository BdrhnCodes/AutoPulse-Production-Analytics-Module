"""
Shared utilities for every data_generation script: loads config.yaml,
seeds all three RNG sources (random, numpy, Faker) for reproducibility,
and saves DataFrames to data/raw/ as CSV.
"""


import random
from pathlib import Path
import numpy as np
import yaml
from faker import Faker

project_root = Path(__file__).resolve().parent.parent
config_path= project_root / "config" / "config.yaml"

def load_config() -> dict:
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    Faker.seed(seed)


def get_output_dir(config: dict) -> Path:
    out_dir = project_root / config["output"]["directory"]
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def save_df(df , name : str, config:dict) -> Path:
    out_dir=get_output_dir(config)
    path= out_dir / f"{name}.csv"
    df.to_csv(path, index=False)
    return path
