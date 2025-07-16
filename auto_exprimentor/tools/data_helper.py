from pathlib import Path
import pandas as pd


def preview_csv(p: Path) -> str:
    """Generate a textual preview of a csv file."""

    df = pd.read_csv(p)

    preview = []

    preview.append(f"-> {str(p)} has {df.shape[0]} rows and {df.shape[1]} columns.")

    # ================  TODO: Tell LLM agents which feature is useful for prediction ================

    cols = df.columns.tolist()
    cols_str = ", ".join(cols)
    preview.append(f"The columns are: {cols_str}")

    return "\n".join(preview)


def data_preview_generate(base_path):
    """Generate a textual preview of a directory."""

    previews = []
    files = [p for p in Path(base_path).iterdir()]
    for f in sorted(files):
        previews.append(preview_csv(f))

    return "\n\n".join(previews)
