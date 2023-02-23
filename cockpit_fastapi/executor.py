import os

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor, CellExecutionError

processor = ExecutePreprocessor(timeout=600, kernel_name="python")

with open(os.environ.get("SCRIPT_PATH", "script.ipynb")) as f:
    notebook = nbformat.read(f, as_version=4)


def execute_notebook() -> str:
    try:
        processor.preprocess(notebook)
        return nbformat.writes(notebook)
    except CellExecutionError:
        raise


if __name__ == "__main__":
    execute_notebook()
