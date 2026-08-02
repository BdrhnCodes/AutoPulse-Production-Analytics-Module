import random
from pathlib import Path
import numpy as np
import yaml
from faker import Faker


project_root = Path(__file__).resolve().parent.parent
config_path= project_root / "config" / "config.yaml"
# The config path is defined.


def load_config() -> dict:
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)
# The data will be loaded without any errors thanks to "utf-8".


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    Faker.seed(seed)
# We need a constant seed number to do find the same answers.


def get_output_dir(config: dict) -> Path:
    out_dir = project_root / config["output"]["directory"]
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
# The file that output will be put into is created.


def save_df(df , name : str, config:dict) -> Path:
    out_dir=get_output_dir(config)
    path= out_dir / f"{name}.csv"
    df.to_csv(path, index=False)
    return path
# Useful for saving csv files faster.