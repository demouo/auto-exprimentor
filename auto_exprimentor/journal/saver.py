from .journals import Journal
from ..config.config import Config
import os


# Define a function to save the best solution and other good solutions to files.
def save_run(cfg: Config, journal: Journal):
    # Save dir for generated codes
    save_dir = cfg.code_save_dir
    os.makedirs(save_dir, exist_ok=True)

    # Retrieve and save the best found solution.
    best_node = journal.get_best_node(only_good=False)
    best_solution_save_path = os.path.join(save_dir, "best_solution.py")
    with open(best_solution_save_path, "w") as f:
        f.write(best_node.code)
    # Retrieve all good solution nodes.
    good_nodes = journal.good_nodes
    for i, node in enumerate(good_nodes):
        solution_i_save_path = os.path.join(save_dir, f"good_solution_{i}.py")
        with open(solution_i_save_path, "w") as f:
            f.write(node.code)
