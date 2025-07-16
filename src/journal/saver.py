from .journals import Journal
import os


# Define a function to save the best solution and other good solutions to files.
def save_run(cfg, journal: Journal):
    # Retrieve and save the best found solution.
    best_node = journal.get_best_node(only_good=False)  # Get the best node.
    save_dir = cfg.code_save_dir
    best_solution_save_path = os.path.join(save_dir, "best_solution.py")
    os.makedirs(os.path.dirname(best_solution_save_path), exist_ok=True)
    with open(best_solution_save_path, "w") as f:
        f.write(best_node.code)

    good_nodes = journal.get_good_nodes()  # Retrieve all good solution nodes.
    for i, node in enumerate(good_nodes):
        filename = os.path.join(save_dir, f"good_solution_{i}.py")
        with open(filename, "w") as f:
            f.write(node.code)
