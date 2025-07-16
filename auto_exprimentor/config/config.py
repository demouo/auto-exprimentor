import datetime
from typing import Dict
from pathlib import Path


# ================  TODO: config ================
config = {
    # experiment configurations
    "exp_name": "ML2025_HW2",
    "data_dir": Path("data/ML2025Spring-hw2-public").resolve(),
    "code_save_dir": Path(f"data/codes/{datetime.datetime.now()}").resolve(),
    # the description of the task
    "task_goal": "Given the survey results from the past two days in a specific state in the U.S.,\
                  predict the probability of testing positive on day 3. \
                  The evaluation metric is Mean Squared Error (MSE).",
    "agent": {
        # the number of iterations
        "steps": 1,
        "search": {
            # decide whether to debug or improve
            "debug_prob": 0.5,
            # the number of draft generated before improving/debugging
            "num_drafts": 1,
        },
    },
}


def set_random(seed=42):
    import random

    random.seed(seed)


set_random()


class Config:
    """
    A recursive configuration class that converts a dict into an object
    with attribute accessible using dot notation.
    """

    def __init__(self, dict_cfg: Dict):
        for k, v in dict_cfg.items():
            if isinstance(v, dict):
                v = Config(v)
            setattr(self, k, v)


cfg = Config(config)
